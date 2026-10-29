# APEX ticketing AI demo

LangGraph + local **llama.cpp** (chat) with **RAG** (BGE embeddings + **ChromaDB**, optional **Neo4j**) and routed calls to **apex-dev** APIs.

## Quick start (web UI)

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env

./scripts/setup-stack.sh             # or manual steps in docs/SETUP.md
python scripts/download_embedding_model.py
./scripts/run-embed-server.sh          # when RAG_EMBEDDING_BACKEND=http (default in .env.example)
docker compose up -d chroma            # neo4j optional: KG_NEO4J_ENABLED=true
python -m apex_rag_demo.rag.sync_index

./scripts/build-frontend.sh   # React 19 UI → static/dist (first time / after UI changes)
./scripts/run-web.sh
# or: source .venv/bin/activate && uvicorn apex_rag_demo.web.app:app --reload --port 8080
```

**UI dev (Vite, proxies `/api` to :8080):** `cd frontend && npm install && npm run dev` → [http://localhost:5173](http://localhost:5173)

Use the **project** `.venv` here — not `~/.venv-llama-cpp` (that env is only for `llama_cpp.server`).

1. Open [http://localhost:8080](http://localhost:8080)
2. Paste a JWT from [apex-dev](https://apex-dev.axsdevops.io/login)
3. Choose region → chat (“How can I help you today?”)

Token stays in **sessionStorage**; each request sends `Authorization: Bearer …` to this app, which forwards it to APEX APIs. Expired JWTs return to the login screen with an optional **re-run last question** prompt (see [SETUP.md](docs/SETUP.md)).

## What it does

```text
question → retrieve_kb → detect_intent → plan_action → execute_action → synthesize_answer
              BGE embed (Chroma) + optional Neo4j context
              llama chat :8000                         apex-dev APIs
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
| Embeddings | **BAAI/bge-small-en-v1.5** @ **:8081** | `./scripts/run-embed-server.sh` (after `download_embedding_model.py`) |
| Rerank | **BAAI/bge-reranker-base** | In-process on first KB rerank; `RAG_RERANK_MODEL` |
| Vector DB | Chroma @ `localhost:8002` | `docker compose up -d chroma` → `./data/chroma` |
| Knowledge graph | Neo4j @ `localhost:7687` | `docker compose up -d neo4j` → `./data/neo4j`; **[KG_NEO4J.md](docs/KG_NEO4J.md)** |
| Ontology | `data/kg/ontology/ticketing_apex.json` | Entity/relation contract for graph sync + GLiNER |
| Neo4j check | `scripts/neo4j_ping.py` | With venv active: `KG_NEO4J_ENABLED=true` in `.env`, password matches compose |
| Sync graph | `python -m apex_rag_demo.rag.sync_kg_index` | After Chroma KB sync; GLiNER + regex → Neo4j (`--force` to re-run) |
| Sync KB | `python -m apex_rag_demo.rag.sync_index` | After editing `data/kb.json` (embed server must be up) |

Full details: **[docs/RAG_STACK.md](docs/RAG_STACK.md)**

### 2. llama.cpp (chat — Qwen2.5-3B)

| Role | Default | Example |
|------|---------|---------|
| Chat | `CHAT_BASE_URL` → port **8000** | `~/models/qwen2.5-3b-instruct-q5_k_m.gguf` |

Run **`llama_cpp.server`** from your **llama-cpp venv** (e.g. `~/.venv-llama-cpp`), not `ticketing-ai-demo/.venv`:

```bash
python3 -m llama_cpp.server \
  --model ~/models/qwen2.5-3b-instruct-q5_k_m.gguf \
  --n_gpu_layers -1 \
  --port 8000 \
  --n_ctx 4096
```

In `.env`: `CHAT_MODEL=qwen2.5-3b-instruct-q5_k_m.gguf`.

Smaller/faster options (0.5B–1.5B) still work — see **[docs/CHAT_MODEL.md](docs/CHAT_MODEL.md)**.

Ports: **8000** chat · **8081** embed (if `RAG_EMBEDDING_BACKEND=http`) · **8002** Chroma · **7474/7687** Neo4j (optional) · **8080** web. Details: [docs/SETUP.md](docs/SETUP.md).

### 3. apex-dev APIs

Default hosts (no local .NET required):

| Service | Base URL | OpenAPI |
|---------|----------|---------|
| Admin | https://api.apex-dev.axsdevops.io/admin | [swagger.json](https://api.apex-dev.axsdevops.io/admin/swagger/v1/swagger.json) |
| **Search** | https://api.apex-dev.axsdevops.io/search | [swagger.json](https://api.apex-dev.axsdevops.io/search/swagger/v1/swagger.json) · [Swagger UI](https://api.apex-dev.axsdevops.io/search/swagger/index.html) |
| Events | https://api.apex-dev.axsdevops.io/events | [swagger.json](https://api.apex-dev.axsdevops.io/events/swagger/v1/swagger.json) |
| Inventory | https://api.apex-dev.axsdevops.io/inventory | [swagger.json](https://api.apex-dev.axsdevops.io/inventory/swagger/v1/swagger.json) |
| Marketing | https://api.apex-dev.axsdevops.io/marketing | [swagger.json](https://api.apex-dev.axsdevops.io/marketing/swagger/v1/swagger.json) |
| Manifest | https://api.apex-dev.axsdevops.io/manifest | [swagger.json](https://api.apex-dev.axsdevops.io/manifest/swagger/v1/swagger.json) · repo `axs-inventory-manifest-api` |
| B2B Reports | https://api.apex-dev.axsdevops.io/reports | [swagger.json](https://api.apex-dev.axsdevops.io/reports/swagger/v1/swagger.json) · repo `unified-api-reports` / MFE `axs-b2b-reports` |

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

Copy [`.env.example`](.env.example) → `.env`. [docs/CONFIG.md](docs/CONFIG.md) lists every variable; [docs/SETUP.md](docs/SETUP.md) explains runtime choices (embed backend, Neo4j, prompt budget).

Highlights:

- **Chat:** `CHAT_BASE_URL`, `CHAT_MODEL` (**3B** default in `.env.example`), `CHAT_CONTEXT_MAX_TOKENS*` — [CHAT_MODEL.md](docs/CHAT_MODEL.md)
- **RAG:** `SENTENCE_TRANSFORMERS_MODEL`, `RAG_RETRIEVE_K`, `RAG_TOP_K`, `RAG_RERANK_*`, `CHROMA_*` — [RAG_STACK.md](docs/RAG_STACK.md), [EMBEDDINGS.md](docs/EMBEDDINGS.md)
- **Graph:** `KG_NEO4J_ENABLED`, `KG_ONTOLOGY_PATH`, `KG_GLINER_*`, `KG_ENRICH_MAX_HITS` — [KG_NEO4J.md](docs/KG_NEO4J.md)
- **APIs:** `APEX_*_BASE_URL`, `APEX_*_SWAGGER_URL`, `REPORTS_*`, `APEX_MANIFEST_*` — [API_LINKS.md](docs/API_LINKS.md)
- **Safety:** `DEMO_CLIENT_ID`, `DEMO_MUTATIONS_DRY_RUN` — mutations preview vs live + UI Confirm

## Project layout

| Path | Purpose |
|------|---------|
| `apex_rag_demo/web/` | FastAPI + static HTML UI |
| `apex_rag_demo/graph.py` | LangGraph workflow |
| `apex_rag_demo/clients/` | HTTP clients per API |
| `data/kb.json` | RAG knowledge snippets |
| `docker-compose.yml` | ChromaDB service |
| `docs/SETUP.md` | Processes, `.env` patterns, bring-up |
| `docs/CONFIG.md` | All `.env` defaults |
| `docs/KG_NEO4J.md` | Neo4j, ontology, GLiNER sync |
| `docs/RAG_STACK.md` | Embeddings + Chroma setup |
| `models/embeddings/` | Downloaded sentence-transformers weights (gitignored) |
| `data/apex_services.json` | Service catalog (URLs + swagger) |
| `docs/API_LINKS.md` | Central link index |

After editing `data/kb.json`, run `python -m apex_rag_demo.rag.sync_index` (Chroma) or delete `.cache/kb_vectors.npz` if using `RAG_VECTOR_STORE=numpy`.

## Safety

Create flows default to **dry-run** (preview request body only). Use `--execute` or the web checkbox only in **dev**, with a token that has the right admin permissions.
