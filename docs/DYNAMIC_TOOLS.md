# Dynamic OpenAPI tools

## Model

| Layer | What it is |
|-------|------------|
| **Tool catalog** | Built from `data/openapi_cache/*.json` + `data/apex_services.json` |
| **tool_id** | e.g. `marketing.get.v1-events` |
| **parameters** | JSON body/path fields (`pageSize`, `query`, `keyword`, `eventId`, …) |
| **legacy_intent** | Maps tool → existing client + UI formatters (`marketing_events`, …) |

Routing embeds **tool descriptions** (summary + HTTP line from swagger), not a static phrase list in Python.

**Orchestrator LLM:** only a **ranked subset** (~14 tools) is injected into the routing prompt (`tool_catalog_for_orchestrator`), plus legacy intents — not the full OpenAPI catalog. Full list: `GET /api/tools`. Catalog + plugins live in the **system** role; the user turn stays short so trimming does not drop the authoritative question.

## Cursor-like flow

```text
User message
  → embed vs all OpenAPI tool descriptions
  → pick tool_id (+ parameters from plan enrichers)
  → legacy_intent → execute_intent_api (existing HTTP clients)
  → UI display unchanged
```

Orchestrator LLM returns **`tool_id` + `parameters`** when possible; fast path skips LLM when embedding confidence is high.

## New API surface

After swagger changes:

1. Refresh cache: `python -m apex_rag_demo.rag.sync_openapi_kb` (or fetch into `data/openapi_cache/`).
2. Restart app (catalog is `@lru_cache`’d).
3. Optional: add `demo_operations` in `data/apex_services.json` for POST/PUT routes to expose.

No code change for each new phrase.

## Endpoints

- `GET /api/tools` — full catalog + status
- `GET /api/runtime/status` — `capability_routing.dynamic_tools`

## Config

```bash
DYNAMIC_TOOLS_ENABLED=true
```

## Static JSON

`data/capability_statements.json` remains optional **extra embedding phrases** layered on top of OpenAPI tools (harness prompts, edge wording).

See also [CAPABILITY_ROUTING.md](./CAPABILITY_ROUTING.md).
