# RAG stack (embeddings + ChromaDB)

Knowledge snippets live in `data/kb.json`. Retrieval uses **sentence-transformers** for embeddings and **ChromaDB** (Docker) for vector search.

## Architecture

```text
kb.json
   → sentence-transformers (all-MiniLM-L6-v2, local under models/embeddings/)
   → ChromaDB HTTP (docker compose, host port 8002)
   → top-k snippets → LangGraph retrieve_kb
```

Chat uses **llama.cpp** on port **8000**. Embeddings use a separate service on port **8081** (OpenAI-compatible `/v1/embeddings`).

| Port | Service |
|------|---------|
| 8000 | llama.cpp **chat** |
| **8081** | **Embedding** server (`./scripts/run-embed-server.sh`) |
| 8002 | ChromaDB (Docker) |
| 8080 | Web UI |

## One-time setup

From the project root (`ticketing-ai-demo`):

```bash
cd /Users/kamals/models/ticketing-ai-demo
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

### 1. Download the embedding model (~90 MB)

```bash
python scripts/download_embedding_model.py
```

Model id defaults to `sentence-transformers/all-MiniLM-L6-v2` (override with `SENTENCE_TRANSFORMERS_MODEL` in `.env`). Files are stored under `models/embeddings/`.

### 2. Start the embedding server (port 8081)

```bash
./scripts/run-embed-server.sh
```

Health check: [http://localhost:8081/health](http://localhost:8081/health)

Uses **sentence-transformers** with the same model as `SENTENCE_TRANSFORMERS_MODEL`.  
Alternative: `./scripts/run-llama-embed-server.sh` for a **llama.cpp** GGUF embed model (`RAG_EMBEDDING_BACKEND=llama`).

### 3. Start ChromaDB

```bash
docker compose up -d chroma
```

Chroma listens on **http://localhost:8002** (maps container `8000` → host `8002`).

### 4. Sync the knowledge base into Chroma

```bash
python -m apex_rag_demo.rag.sync_index
```

Re-run after editing `data/kb.json`.

## Daily run (full stack)

Terminal 1 — **llama.cpp chat** (intent / planning, port 8000):

```bash
python3 -m llama_cpp.server \
  --model ~/models/Qwen2.5-0.5B-Instruct-GGUF/qwen2.5-0.5b-instruct-q4_k_m.gguf \
  --port 8000
```

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

| Variable | Default | Purpose |
|----------|---------|---------|
| `RAG_EMBEDDING_BACKEND` | `http` | `http` / `llama` (call :8081), or `sentence-transformers` (in-process) |
| `EMBED_BASE_URL` | `http://localhost:8081/v1` | Embedding server URL |
| `EMBED_SERVER_PORT` | `8081` | Port for `./scripts/run-embed-server.sh` |
| `SENTENCE_TRANSFORMERS_MODEL` | `sentence-transformers/all-MiniLM-L6-v2` | Hugging Face model id |
| `RAG_VECTOR_STORE` | `chroma` | `chroma` or `numpy` (legacy `.cache/kb_vectors.npz`) |
| `CHROMA_HOST` | `localhost` | Chroma HTTP host |
| `CHROMA_PORT` | `8002` | Host port (docker compose) |
| `CHROMA_COLLECTION` | `apex_kb` | Collection name |
| `RAG_KEYWORD_FALLBACK` | `true` | Keyword match if Chroma/embeddings fail |
| `RAG_TOP_K` | `2` | Snippets per query |

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `Connection refused` on 8002 | `docker compose up -d chroma` |
| Stale KB after edit | `python -m apex_rag_demo.rag.sync_index` |
| No GPU / slow first embed | Normal; MiniLM runs on CPU |
| Connection refused on 8081 | `./scripts/run-embed-server.sh` |
| Use llama GGUF embeddings | `./scripts/run-llama-embed-server.sh` + `RAG_EMBEDDING_BACKEND=llama` |
| No separate embed process | `RAG_EMBEDDING_BACKEND=sentence-transformers` in `.env` |
| Offline vectors only | `RAG_VECTOR_STORE=numpy` and delete `.cache/kb_vectors.npz` to rebuild |

## Docker files

- `docker/chroma/Dockerfile` — Chroma server image
- `docker-compose.yml` — `chroma` service + persistent volume `chroma_data`
