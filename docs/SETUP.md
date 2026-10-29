# Environment and runtime setup

How configuration is loaded, which processes you need, and common `.env` choices for this demo.

**Reference:** every variable and default → [CONFIG.md](./CONFIG.md). RAG details → [RAG_STACK.md](./RAG_STACK.md). Chat GGUF → [CHAT_MODEL.md](./CHAT_MODEL.md). Neo4j → [KG_NEO4J.md](./KG_NEO4J.md).

## How configuration works

1. Copy [`.env.example`](../.env.example) to **`.env`** in the project root (`.env` is gitignored).
2. On startup, `apex_rag_demo/config.py` loads `.env` via `python-dotenv`.
3. Any key **not** in `.env` uses the default in `config.py`.
4. **Duplicate keys** in `.env`: the **last** assignment wins — avoid repeating the same variable.

Secrets (JWT) belong in `.env` or the web UI sessionStorage, not in committed files.

## Processes and ports

| Port | Service | When required |
|------|---------|----------------|
| **8080** | FastAPI web UI | Always |
| **8000** | llama.cpp chat (`CHAT_BASE_URL`) | Always (unless `APEX_MOCK`-only experiments) |
| **8081** | Embedding HTTP server | When `RAG_EMBEDDING_BACKEND=http` or `llama` |
| **8002** | ChromaDB (Docker) | When `RAG_VECTOR_STORE=chroma` (default) |
| **7474 / 7687** | Neo4j Browser / Bolt | When `KG_NEO4J_ENABLED=true` |

```bash
docker compose up -d chroma          # vectors
docker compose up -d neo4j           # optional knowledge graph
```

**Optional Docker images** (one-shot workers — build, do not `up` as services):

```bash
docker compose --profile plugins build plugin-worker    # script plugins (QuickJS / RestrictedPython)
./scripts/build-sandbox-toolkit.sh                      # chat sandbox Python + React
# or: docker compose --profile sandbox build sandbox-toolkit
```

Verify: `curl -s http://localhost:8080/api/runtime/status` → `script_sandbox`, `sandbox_toolkit.image_ready`.

Data persists under `./data/chroma/` and `./data/neo4j/`.

## Embedding backends

Pick **one** approach in `.env`:

| `RAG_EMBEDDING_BACKEND` | Behavior |
|-------------------------|----------|
| **`http`** (common in CI/docs) | `./scripts/run-embed-server.sh` on **8081**; same BGE model as `EMBED_MODEL` |
| **`sentence-transformers`** | Loads BGE **inside the web app**; no 8081 process |
| **`llama`** | GGUF embed model on 8081 via `./scripts/run-llama-embed-server.sh` |

Shared settings:

```bash
SENTENCE_TRANSFORMERS_MODEL=BAAI/bge-small-en-v1.5
EMBED_MODEL=BAAI/bge-small-en-v1.5
EMBEDDING_EXPECTED_DIMENSION=384
CHROMA_HNSW_SPACE=cosine
```

After changing the embed model or `CHROMA_HNSW_SPACE`, run `python -m apex_rag_demo.rag.sync_index`.

Download weights:

```bash
python scripts/download_embedding_model.py   # embed + rerank + intent warm-up
```

## Chat model (llama.cpp)

Recommended instruct GGUF for this repo: **Qwen2.5-3B-Instruct** (`qwen2.5-3b-instruct-q5_k_m.gguf`).

```bash
# Separate venv with llama-cpp-python is typical
python3 -m llama_cpp.server \
  --model /path/to/qwen2.5-3b-instruct-q5_k_m.gguf \
  --n_gpu_layers -1 \
  --port 8000 \
  --n_ctx 4096
```

```bash
CHAT_BASE_URL=http://localhost:8000/v1
CHAT_MODEL=qwen2.5-3b-instruct-q5_k_m.gguf
```

Smaller models (0.5B–1.5B) work for smoke tests; see [CHAT_MODEL.md](./CHAT_MODEL.md).

### Prompt budget vs server context

Defaults in `.env.example` target **~2048** token server context. If you raise llama **`--n_ctx`** (e.g. 4096) and **`CHAT_HISTORY_MAX_MESSAGES`**, also raise:

- `CHAT_CONTEXT_MAX_TOKENS` / `CHAT_CONTEXT_MAX_TOKENS_ROUTING`
- `CHAT_MESSAGE_MAX_CHARS*` / `CHAT_CHROMA_MAX_CHARS*`

Routing JSON is usually more stable at **`CHAT_TEMPERATURE` / `CHAT_TEMPERATURE_ROUTING` ≈ 0.2**; higher values increase answer variety but can hurt classify/plan accuracy.

## KB retrieval (vectors + rerank)

| Variable | Default | Meaning |
|----------|---------|---------|
| `RAG_RETRIEVE_K` | `10` | Chroma candidates before rerank |
| `RAG_TOP_K` | `2` | Snippets after cross-encoder |
| `RAG_RERANK_MODEL` | `BAAI/bge-reranker-base` | Pairs with BGE-small embedder |

`CHAT_TOP_K` controls **llama sampling**, not Chroma.

Other Chroma limits: `CHROMA_INTENT_ROUTE_TOP_K`, `CHROMA_SYSTEM_ENRICH_TOP_K`, `SESSION_MEMORY_TOP_K` — see [CONFIG.md](./CONFIG.md).

## Knowledge graph (optional)

```bash
KG_NEO4J_ENABLED=true
NEO4J_URI=bolt://localhost:7687
NEO4J_PASSWORD=changeme   # match docker-compose NEO4J_AUTH
KG_ONTOLOGY_PATH=data/kg/ontology/ticketing_apex.json
```

```bash
python scripts/neo4j_ping.py
python -m apex_rag_demo.rag.sync_kg_index
```

Runtime enrichment is **context-only** (does not replace API calls). Details: [KG_NEO4J.md](./KG_NEO4J.md).

## apex-dev APIs

Gateway URLs and swagger links live in `.env.example` (`APEX_*_BASE_URL`, Manifest, Reports, Resources). CLI token: `APEX_BEARER_TOKEN`. Web UI uses a pasted JWT per session.

Mutation safety: `DEMO_MUTATIONS_DRY_RUN=true` previews all writes; `false` allows live creates/resets with UI confirmation for update/delete.

## Minimal bring-up

**Automated (recommended):**

```bash
cd ticketing-ai-demo
./scripts/setup-stack.sh
```

Checks Python 3.10+, creates **`.venv`**, copies **`.env`**, prepares **data/** (Chroma, Neo4j, LangGraph SQLite), starts **Docker** when available (warns and continues without Docker), downloads embed/rerank models, **`sync_index`** when Chroma is up, optional **`sync_kg_index`** when `KG_NEO4J_ENABLED=true`, and checks **llama.cpp** venv (`LLAMA_VENV`, default `~/.venv-llama-cpp`). Options: `--skip-docker`, `--skip-models`, `--skip-sync`, `--setup-llama-venv`, `--help`.

**Manual** (same end state):

```bash
cd ticketing-ai-demo
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python scripts/download_embedding_model.py
docker compose up -d chroma
python -m apex_rag_demo.rag.sync_index
uvicorn apex_rag_demo.web.app:app --reload --port 8080
```

**Plus llama on 8000** (see above). If using **`RAG_EMBEDDING_BACKEND=http`**, also run `./scripts/run-embed-server.sh`. If **`KG_NEO4J_ENABLED=true`**, start Neo4j and run `sync_kg_index`.

## Troubleshooting `.env`

| Symptom | Check |
|---------|--------|
| Wrong Chroma metric | Single `CHROMA_HNSW_SPACE=cosine`; re-sync collections after change |
| Unexpected RAG snippet count | One `RAG_TOP_K` line (last wins) |
| Logprobs ignored | Use `CHAT_LOGPROBS=5` — `TOP_LOGPROBS` is not used |
| Neo4j auth errors | `NEO4J_PASSWORD` matches compose |
| Missing features | Keys only in `.env.example` still apply via `config.py` defaults |
| `resource_tracker: leaked semaphore` on exit (Python 3.14) | Harmless shutdown noise from **sentence-transformers / joblib (loky)** after embedding work. App calls `shutdown_embedding_workers()` on FastAPI shutdown; **`uvicorn --reload`** killing workers abruptly can still print it once. Set `LOKY_MAX_CPU_COUNT=1` (default in code) or ignore if the process exited cleanly. |

## Related

- [CONFIG.md](./CONFIG.md) — complete variable table  
- [SANDBOX_TOOLKIT.md](./SANDBOX_TOOLKIT.md) — sandbox Docker image and chat `run_sandbox`  
- [README.md](../README.md) — quick start  
