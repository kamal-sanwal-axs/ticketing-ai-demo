# APEX ticketing AI demo (LangGraph + llama.cpp)

Small demo: **RAG** over internal KB + routed calls to:

| Intent | API | Method |
|--------|-----|--------|
| Event search | apex-search-api | `POST /v1/events/suggest` (read-only) |
| Create organization | apex-admin-api | `POST /v1/organizations` |
| Create client venue | apex-admin-api | `POST /v1/client-venues` |

**Writes default to dry-run** (preview JSON only). Pass `--execute` or `DEMO_EXECUTE_WRITES=true` for live creates (dev JWT required).

## Architecture

```text
question → retrieve_kb → detect_intent → plan_action → execute_action → synthesize_answer
              embed          chat            chat          search-api / admin-api
```

## Prerequisites

1. **Chat** llama.cpp server (generative), e.g. port **8000**
2. **Embedding** llama.cpp server (`--embedding`), e.g. port **8001** — use a GGUF embedding model (not the instruct model), e.g. `nomic-embed-text-v1.5-GGUF`
3. Optional: **apex-search-api** running locally (`APEX-DEV` profile → `http://localhost:5005`) with a valid JWT

## Setup

```bash
cd /Users/kamals/models/ticketing-ai-demo
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# edit .env: CHAT_MODEL, EMBED_MODEL, APEX_BEARER_TOKEN
```

### API hosts (apex-dev)

Full catalog: `data/apex_services.json` or:

```bash
python -m apex_rag_demo.main --list-services
```

| Service | OpenAPI |
|---------|---------|
| Admin | https://api.apex-dev.axsdevops.io/admin/swagger/v1/swagger.json |
| Search | https://api.apex-dev.axsdevops.io/search/swagger/v1/swagger.json |
| Events | https://api.apex-dev.axsdevops.io/events/swagger/v1/swagger.json |
| Inventory | https://api.apex-dev.axsdevops.io/inventory/swagger/v1/swagger.json |
| Marketing | https://api.apex-dev.axsdevops.io/marketing/swagger/v1/swagger.json |

**Demo intents → calls**

| Intent | API |
|--------|-----|
| `search_events` | Search `POST /v1/events/suggest` |
| `create_organization` / `create_client_venue` | Admin POST (dry-run default) |
| `get_event` | Events `GET /{eventId}` |
| `inventory_zones` | Inventory `GET /events/{eventId}/zones/primary` |
| `marketing_events` | Marketing `GET /v1/events` |

### Auth

Copy a dev JWT from the browser after logging into [apex-dev](https://apex-dev.axsdevops.io) (same token the Control MFE uses):

```bash
export APEX_BEARER_TOKEN="<jwt>"
export APEX_MOCK=false
```

### Without live APIs

Set `APEX_MOCK=true` or leave `APEX_BEARER_TOKEN` empty — mock JSON responses for offline graph + llama testing.

### Local APIs instead of gateway

```bash
export APEX_SEARCH_BASE_URL=http://localhost:5005
export APEX_ADMIN_BASE_URL=http://localhost:5000
```

## Web UI (token + welcome + chat)

```bash
cd ticketing-ai-demo && source .venv/bin/activate
pip install -r requirements.txt
uvicorn apex_rag_demo.web.app:app --reload --port 8080
```

Open http://localhost:8080 — paste your apex-dev JWT, pick a region, then chat. Token is stored in **sessionStorage** only (not sent to our server except per request as `Authorization`).

## CLI

```bash
python -m apex_rag_demo.main "What events match arena tour?"
python -m apex_rag_demo.main "Create organization Acme Events West"
python -m apex_rag_demo.main "Create client venue Portland Open Arena for client <uuid>"
python -m apex_rag_demo.main "List marketing events"
python -m apex_rag_demo.main "Show inventory zones for event <event-uuid>"
python -m apex_rag_demo.main --json "How does event search work in APEX?"

# Live POST (dev only, with token + apex-admin-api running):
python -m apex_rag_demo.main --execute "Create organization Demo Org $(date +%s)"
```

## Related services (not wired in this demo)

| API | Role |
|-----|------|
| `apex-admin-api` | Client venue config (`/v1/client-venues/{id}`) |
| `apex-inventory-api` | Ticket types / zones |
| `apex-events-api` | Event orchestration (not search) |

Extend `apex_rag_demo/clients/` and add graph nodes for admin venue GET after you have a `clientVenueId` from search.

## Files

- `data/kb.json` — tiny KB for RAG
- `apex_rag_demo/graph.py` — LangGraph workflow
- `apex_rag_demo/clients/apex_search.py` — HTTP client for suggest
