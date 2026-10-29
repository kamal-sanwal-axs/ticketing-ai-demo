# RAG stack (embeddings + ChromaDB)

Knowledge snippets live in `data/kb.json`. Retrieval uses **sentence-transformers** for embeddings and **ChromaDB** (Docker) for vector search.

## Architecture

```text
kb.json
   → sentence-transformers (BAAI/bge-small-en-v1.5, local under models/embeddings/)
   → ChromaDB HTTP (docker compose, host port 8002) — bi-encoder fetch `RAG_RETRIEVE_K`
   → LangGraph nodes `retrieve_bi_encoder` → `rerank_cross_encoder` (cross-encoder `RAG_RERANK_MODEL`, top `RAG_TOP_K`)
   → snippets → LangGraph retrieve_kb
```

Chat uses **llama.cpp** on port **8000**. Embeddings use port **8081** when `RAG_EMBEDDING_BACKEND=http`, or run in-process when `RAG_EMBEDDING_BACKEND=sentence-transformers` — see [SETUP.md](./SETUP.md).

| Port | Service |
|------|---------|
| 8000 | llama.cpp **chat** |
| **8081** | **Embedding** server (`./scripts/run-embed-server.sh`) |
| 8002 | ChromaDB (Docker, `./data/chroma`) |
| 7474 | Neo4j Browser (Docker, optional KG) |
| 7687 | Neo4j Bolt |
| 8080 | Web UI |

## One-time setup

From the project root (`ticketing-ai-demo`):

```bash
cd /Users/kamals/models/ticketing-ai-demo
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

### 1. Download embedding + rerank models

```bash
python scripts/download_embedding_model.py
```

Downloads **BAAI/bge-small-en-v1.5** (embed) and **BAAI/bge-reranker-base** (rerank) by default. Model ids: `SENTENCE_TRANSFORMERS_MODEL`, `RAG_RERANK_MODEL` in `.env`. Files under `LOCAL_MODELS_ROOT/embeddings/` (default: parent of this repo, e.g. `/Users/kamals/models/embeddings`).

**Download weights (RAG + intent router + rerank):**

```bash
python -m apex_rag_demo.download_models
# or: python scripts/download_embedding_model.py
# rerank only: python -m apex_rag_demo.download_models --rerank-only
```

Intent classification uses the **same** sentence-transformers model **in-process** (`intent_semantic.py`), even when `RAG_EMBEDDING_BACKEND=http` points Chroma retrieval at the :8081 embed server.

### 2. Start the embedding server (port 8081)

```bash
./scripts/run-embed-server.sh
```

Health check: [http://localhost:8081/health](http://localhost:8081/health)

Uses **sentence-transformers** with the same model as `SENTENCE_TRANSFORMERS_MODEL`.  
Alternative: `./scripts/run-llama-embed-server.sh` for a **llama.cpp** GGUF embed model (`RAG_EMBEDDING_BACKEND=llama`).

### 3. Start vector + graph stores (Docker)

```bash
docker compose up -d chroma neo4j
```

- Chroma: **http://localhost:8002** (container `8000` → host `8002`), files under **`./data/chroma/`**
- Neo4j Browser: **http://localhost:7474** (login `neo4j` / `NEO4J_PASSWORD` from `.env`), graph files under **`./data/neo4j/`**

**Python Bolt client** (not the Docker image): install deps in the **project** `.venv` (`pip install -r requirements.txt` includes `neo4j`). System `python` without that venv will fail with `No module named 'neo4j'`.

Ontology contract: **`data/kg/ontology/ticketing_apex.json`** (9 entity types, relation schema, GLiNER label map). Full guide: **[KG_NEO4J.md](./KG_NEO4J.md)**.

In `.env`, set `KG_NEO4J_ENABLED=true` and `NEO4J_PASSWORD` to match `NEO4J_AUTH` in `docker-compose.yml`. Batch sync **`python -m apex_rag_demo.rag.sync_kg_index`** writes extracted entities to Neo4j; chat node **`enrich_from_kg`** reads graph context when enabled.

```bash
source .venv/bin/activate
python scripts/neo4j_ping.py
# or: .venv/bin/python scripts/neo4j_ping.py
```

Expected: `Ontology: apex_ticketing_operations v1.0 — entity types: 9` then `Neo4j: connected ok`.

**Sync KB into the graph** (batch GLiNER + regex → Neo4j; skips if KB fingerprint unchanged):

```bash
source .venv/bin/activate
pip install -r requirements.txt   # includes gliner + neo4j
python -m apex_rag_demo.rag.sync_kg_index
python -m apex_rag_demo.rag.sync_kg_index --force   # re-extract all chunks
```

Chat pipeline: after Chroma enrichment, **`enrich_from_kg`** appends matching graph entities to the system context (read-only; does not change routing).

### 4. Sync the knowledge base into Chroma

```bash
python -m apex_rag_demo.rag.sync_index
```

Re-run after editing `data/kb.json`.

OpenAPI path summaries (admin, search, events, inventory, marketing) ship in `data/kb_openapi.json`. To refresh from live swagger:

```bash
python -m apex_rag_demo.rag.sync_openapi_kb
python -m apex_rag_demo.rag.sync_index --store chroma
```

## Daily run (full stack)

Terminal 1 — **llama.cpp chat** (Qwen2.5-3B-Instruct, port 8000):

Use the **llama-cpp-python** venv (e.g. `~/.venv-llama-cpp`), not the project `.venv`:

```bash
python3 -m llama_cpp.server \
  --model ~/models/qwen2.5-3b-instruct-q5_k_m.gguf \
  --n_gpu_layers -1 \
  --port 8000 \
  --n_ctx 4096
```

Set in `.env`: `CHAT_MODEL=qwen2.5-3b-instruct-q5_k_m.gguf` (filename must match `--model`).

Terminal 2 — **embeddings** (port **8081**):

```bash
cd /Users/kamals/models/ticketing-ai-demo
./scripts/run-embed-server.sh
```

Terminal 3 — **ChromaDB** (if not already up):

```bash
cd /Users/kamals/models/ticketing-ai-demo
docker compose up -d chroma
```

Terminal 4 — **web UI** (port 8080):

```bash
cd /Users/kamals/models/ticketing-ai-demo
source .venv/bin/activate
uvicorn apex_rag_demo.web.app:app --reload --port 8080
```

Open [http://localhost:8080](http://localhost:8080).

## Configuration (`.env`)

Full reference: **[CONFIG.md](./CONFIG.md)**. Summary for this stack:

### Embeddings & vector store

| Variable | Default | Purpose |
|----------|---------|---------|
| `RAG_EMBEDDING_BACKEND` | `http` | `http` / `llama` (call :8081), or `sentence-transformers` (in-process) |
| `EMBED_BASE_URL` | `http://localhost:8081/v1` | Embedding server URL |
| `EMBED_SERVER_PORT` | `8081` | Port for `./scripts/run-embed-server.sh` |
| `SENTENCE_TRANSFORMERS_MODEL` | `BAAI/bge-small-en-v1.5` | Hugging Face model id |
| `EMBED_MODEL` | same as above | HTTP embed server model id |
| `RAG_VECTOR_STORE` | `chroma` | `chroma` or `numpy` (legacy `.cache/kb_vectors.npz`) |
| `CHROMA_HOST` | `localhost` | Chroma HTTP host |
| `CHROMA_PORT` | `8002` | Host port (docker compose) |
| `CHROMA_HNSW_SPACE` | `cosine` | HNSW metric (`cosine` / `l2` / `ip`) — see [EMBEDDINGS.md](./EMBEDDINGS.md) |
| `EMBEDDING_EXPECTED_DIMENSION` | `384` | Sanity check on sync; not chat model size |
| `CHROMA_COLLECTION` | `apex_kb` | Main KB collection |
| `CHROMA_SESSION_COLLECTION` | `apex_session_intents` | Per-user/session intent memory |
| `CHROMA_STATE_COLLECTION` | `apex_graph_state` | LangGraph snapshot metadata |
| `CHROMA_AGENT_ROLES_COLLECTION` | `apex_agent_roles` | Role hints |
| `CHROMA_INTENT_ROUTES_COLLECTION` | `apex_intent_routes` | Pre-LLM route exemplars |
| `RAG_KEYWORD_FALLBACK` | `true` | Keyword match if Chroma/embeddings fail |

### Retrieval top-k (KB path)

| Variable | Default | Purpose |
|----------|---------|---------|
| `RAG_RETRIEVE_K` | `10` | Vectors fetched from Chroma before rerank |
| `RAG_TOP_K` | `2` | Snippets kept after cross-encoder |
| `RAG_RERANK_ENABLED` | `true` | Enable rerank step |
| `RAG_RERANK_MODEL` | `BAAI/bge-reranker-base` | Pairs with bge-small embedder |

### Other Chroma top-k

| Variable | Default | Purpose |
|----------|---------|---------|
| `CHROMA_INTENT_ROUTE_TOP_K` | `3` | Intent route hits |
| `CHROMA_INTENT_ROUTE_MIN_SCORE` | `0.72` | Min score for route match |
| `CHROMA_SYSTEM_ENRICH_TOP_K` | `3` | System-prompt enrichment snippets |
| `SESSION_MEMORY_TOP_K` | `3` | Similar session turns retrieved |
| `SESSION_MEMORY_ENABLED` | `true` | Recall/persist turns in Chroma |
| `SESSION_MEMORY_REUSE_MAX_DISTANCE` | `0.55` | Distance gate (lower = stricter) |

Session graph JSON (exact question replay) is stored under `data/session_graph/{userId}/{sessionId}.json` on the app host. Chroma and Neo4j persist under **`./data/chroma`** and **`./data/neo4j`** (survive `docker compose down`).

### Neo4j (optional)

| Variable | Default | Purpose |
|----------|---------|---------|
| `KG_NEO4J_ENABLED` | `false` | Enable Bolt client (`neo4j_client`); set `true` for `neo4j_ping` and KG sync |
| `NEO4J_URI` | `bolt://localhost:7687` | Neo4j Bolt URL |
| `NEO4J_PASSWORD` | `changeme` | Must match `NEO4J_AUTH` in docker-compose |
| `KG_ONTOLOGY_PATH` | `data/kg/ontology/ticketing_apex.json` | Entity/relation schema for extraction |

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `Connection refused` on 8002 | `docker compose up -d chroma` |
| Stale KB after edit | `python -m apex_rag_demo.rag.sync_index` |
| No GPU / slow first embed | Normal; bge-small runs on CPU |
| Connection refused on 8081 | `./scripts/run-embed-server.sh` |
| Use llama GGUF embeddings | `./scripts/run-llama-embed-server.sh` + `RAG_EMBEDDING_BACKEND=llama` |
| No separate embed process | `RAG_EMBEDDING_BACKEND=sentence-transformers` in `.env` |
| Offline vectors only | `RAG_VECTOR_STORE=numpy` and delete `.cache/kb_vectors.npz` to rebuild |
| `No module named 'neo4j'` | `source .venv/bin/activate && pip install -r requirements.txt`; do not use bare `python` outside `.venv` |
| `Neo4j: not available` / Bolt errors | `docker compose up -d neo4j`; `KG_NEO4J_ENABLED=true`; `NEO4J_PASSWORD` matches compose |
| Empty graph in Browser | Run `python -m apex_rag_demo.rag.sync_kg_index` after Neo4j is up |
| GLiNER model download slow | First `sync_kg_index` pulls `KG_GLINER_MODEL`; set `KG_GLINER_ENABLED=false` to use UUID/API-path regex only |

## Hybrid memory (Chroma + Neo4j)

Same KB corpus, two representations:

```text
kb.json / OpenAPI chunks
   ├─ embeddings → Chroma (semantic similarity, intent routes, session memory)
   └─ GLiNER + regex (ontology labels) → Neo4j (typed entities + relations)
```

1. **Ontology** — `data/kg/ontology/ticketing_apex.json` — see [KG_NEO4J.md](./KG_NEO4J.md).
2. **Chroma sync** — `python -m apex_rag_demo.rag.sync_index` (BGE-small vectors).
3. **Graph sync** — `python -m apex_rag_demo.rag.sync_kg_index` (requires `KG_NEO4J_ENABLED=true`).
4. **Chat** — `enrich_system_from_chroma` then `enrich_from_kg` before retrieve/classify.

Loader: `kg_ontology`. Driver: `neo4j_client`. Batch: `sync_kg_index` / `kg_sync.py`. Runtime: `kg_enrich.py` → LangGraph `enrich_from_kg`.

## Docker files

- `docker/chroma/Dockerfile` — Chroma server image
- `docker-compose.yml` — `chroma` + `neo4j` with bind mounts under `./data/`
