# APEX ticketing AI demo

LangGraph + local **llama.cpp** (chat) with **RAG** (**sentence-transformers** + **ChromaDB**) and routed calls to **apex-dev** APIs.

**Project path:** `/Users/kamals/models/ticketing-ai-demo`

## Quick start (web UI)

```bash
cd /Users/kamals/models/ticketing-ai-demo
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env

# RAG: embedding model + :8081 server + ChromaDB (see docs/RAG_STACK.md)
python scripts/download_embedding_model.py
./scripts/run-embed-server.sh          # keep running (port 8081)
docker compose up -d chroma
python -m apex_rag_demo.rag.sync_index

./scripts/run-web.sh
# or: source .venv/bin/activate && uvicorn apex_rag_demo.web.app:app --reload --port 8080
```

Use the **project** `.venv` here — not `~/.venv-llama-cpp` (that env is only for `llama_cpp.server`).

1. Open [http://localhost:8080](http://localhost:8080)
2. Paste a JWT from [apex-dev](https://apex-dev.axsdevops.io/login)
3. Choose region → chat (“How can I help you today?”)

Token stays in **sessionStorage**; each request sends `Authorization: Bearer …` to this app, which forwards it to APEX APIs.

## What it does

```text
question → retrieve_kb → detect_intent → plan_action → execute_action → synthesize_answer
              embed :8081 + Chroma           llama chat :8000            apex-dev APIs
```

| Intent | Gateway call |
|--------|----------------|
| `search_events` | `POST /search/v1/events/suggest` |
| `list_client_venues` | `POST /search/v1/client-venues` (read-only list) |
| `create_organization` | `POST /admin/v1/organizations` (dry-run unless `--execute`) |
| `create_client_venue` | `POST /admin/v1/client-venues` (dry-run unless `--execute`) |
| `get_event` | `GET /events/{eventId}` |
| `inventory_zones` | `GET /inventory/events/{eventId}/zones/primary` |
| `marketing_events` | `GET /marketing/v1/events` |

**API reference (all swagger links):** [docs/API_LINKS.md](docs/API_LINKS.md)  
**Events vs client venues & MCP:** [docs/ROUTING_AND_MCP.md](docs/ROUTING_AND_MCP.md)

## Prerequisites

### 1. RAG (embeddings + vectors)

| Component | Default | Notes |
|-----------|---------|--------|
| Embeddings | **:8081** OpenAI `/v1/embeddings` | `./scripts/run-embed-server.sh` (after `download_embedding_model.py`) |
| Vector DB | Chroma @ `localhost:8002` | `docker compose up -d chroma` |
| Sync KB | `python -m apex_rag_demo.rag.sync_index` | After editing `data/kb.json` (embed server must be up) |

Full details: **[docs/RAG_STACK.md](docs/RAG_STACK.md)**

### 2. llama.cpp (chat only)

| Role | Default | Example |
|------|---------|---------|
| Chat | `CHAT_BASE_URL` → port 8000 | `~/models/Qwen2.5-0.5B-Instruct-GGUF/qwen2.5-0.5b-instruct-q4_k_m.gguf` |

```bash
python3 -m llama_cpp.server --model ~/models/Qwen2.5-0.5B-Instruct-GGUF/qwen2.5-0.5b-instruct-q4_k_m.gguf --n_gpu_layers -1 --port 8000
```

Ports: **8000** chat · **8081** embed · **8002** Chroma · **8080** web.  
Optional: `RAG_EMBEDDING_BACKEND=sentence-transformers` (no :8081 process) or `run-llama-embed-server.sh` for GGUF embed.

### 3. apex-dev APIs

Default hosts (no local .NET required):

| Service | Base URL | OpenAPI |
|---------|----------|---------|
| Admin | https://api.apex-dev.axsdevops.io/admin | [swagger.json](https://api.apex-dev.axsdevops.io/admin/swagger/v1/swagger.json) |
| **Search** | https://api.apex-dev.axsdevops.io/search | [swagger.json](https://api.apex-dev.axsdevops.io/search/swagger/v1/swagger.json) · [Swagger UI](https://api.apex-dev.axsdevops.io/search/swagger/index.html) |
| Events | https://api.apex-dev.axsdevops.io/events | [swagger.json](https://api.apex-dev.axsdevops.io/events/swagger/v1/swagger.json) |
| Inventory | https://api.apex-dev.axsdevops.io/inventory | [swagger.json](https://api.apex-dev.axsdevops.io/inventory/swagger/v1/swagger.json) |
| Marketing | https://api.apex-dev.axsdevops.io/marketing | [swagger.json](https://api.apex-dev.axsdevops.io/marketing/swagger/v1/swagger.json) |

List from the app:

```bash
python -m apex_rag_demo.main --list-services
```

### Auth

- **Web:** paste JWT on first screen.
- **CLI:** `export APEX_BEARER_TOKEN="<jwt>"` and `APEX_MOCK=false`.
- **Offline:** `APEX_MOCK=true` or empty token → mock JSON (still runs LangGraph + llama).

### Local APIs (optional)

```bash
export APEX_SEARCH_BASE_URL=http://localhost:5005
export APEX_ADMIN_BASE_URL=http://localhost:5000
```

## CLI

```bash
python -m apex_rag_demo.main "Find events matching arena"
python -m apex_rag_demo.main "Create organization Acme West"
python -m apex_rag_demo.main --json "How does event search work?"
python -m apex_rag_demo.main --execute "Create organization Demo $(date +%s)"  # live POST
```

## Configuration

Copy [`.env.example`](.env.example) → `.env`. Important keys:

- `APEX_SEARCH_BASE_URL`, `APEX_SEARCH_SWAGGER_URL`
- `APEX_ADMIN_*`, `APEX_EVENTS_*`, `APEX_INVENTORY_*`, `APEX_MARKETING_*`
- `DEMO_CLIENT_ID` — for client-venue create when UUID not in the message
- `DEMO_EXECUTE_WRITES` — default `false`; web UI has a “Live writes” checkbox

## Project layout

| Path | Purpose |
|------|---------|
| `apex_rag_demo/web/` | FastAPI + static HTML UI |
| `apex_rag_demo/graph.py` | LangGraph workflow |
| `apex_rag_demo/clients/` | HTTP clients per API |
| `data/kb.json` | RAG knowledge snippets |
| `docker-compose.yml` | ChromaDB service |
| `docs/RAG_STACK.md` | Embeddings + Chroma setup |
| `models/embeddings/` | Downloaded sentence-transformers weights (gitignored) |
| `data/apex_services.json` | Service catalog (URLs + swagger) |
| `docs/API_LINKS.md` | Central link index |

After editing `data/kb.json`, run `python -m apex_rag_demo.rag.sync_index` (Chroma) or delete `.cache/kb_vectors.npz` if using `RAG_VECTOR_STORE=numpy`.

## Safety

Create flows default to **dry-run** (preview request body only). Use `--execute` or the web checkbox only in **dev**, with a token that has the right admin permissions.
