# Environment configuration

Defaults live in [`apex_rag_demo/config.py`](../apex_rag_demo/config.py). Copy [`.env.example`](../.env.example) → `.env`. For which services to run and common overrides, see [SETUP.md](./SETUP.md).

**Related:** [SETUP.md](./SETUP.md) (processes & `.env` choices) · [RAG_STACK.md](./RAG_STACK.md) · [EMBEDDINGS.md](./EMBEDDINGS.md) · [CHAT_MODEL.md](./CHAT_MODEL.md) · [KG_NEO4J.md](./KG_NEO4J.md) · [API_LINKS.md](./API_LINKS.md)

## Chat (llama.cpp, port 8000)

**Recommended:** Qwen2.5-3B-Instruct — `CHAT_MODEL=qwen2.5-3b-instruct-q5_k_m.gguf`, server `--n_ctx 4096`. See [CHAT_MODEL.md](./CHAT_MODEL.md).

| Variable | Default | Purpose |
|----------|---------|---------|
| `CHAT_BASE_URL` | `http://localhost:8000/v1` | OpenAI-compatible chat server |
| `CHAT_MODEL` | *(empty)* | GGUF filename; must match `--model` on llama server |
| `CHAT_TEMPERATURE` | `0.2` | Main synthesis / agent turns |
| `CHAT_TEMPERATURE_ROUTING` | `CHAT_TEMPERATURE` | Classify, plan, JSON extraction |
| `CHAT_TOP_P` | `0.9` | llama.cpp sampling |
| `CHAT_TOP_K` | `40` | llama.cpp sampling (**not** Chroma top-k) |
| `CHAT_STREAM` | `true` | Stream tokens from llama (internal) |
| `CHAT_LOGPROBS` | `5` | `top_logprobs`; `0` / `false` to disable |
| `CHAT_HISTORY_MAX_MESSAGES` | `10` | Rolling chat history in prompts |
| `CHAT_HISTORY_MAX_MESSAGES_ROUTING` | `6` | History cap for classify/plan |
| `CHAT_CONTEXT_MAX_TOKENS` | `1700` | Prompt budget (char estimate) for main path |
| `CHAT_CONTEXT_MAX_TOKENS_ROUTING` | `1500` | Budget for routing LLM calls |
| `CHAT_MESSAGE_MAX_CHARS` | `1200` | Per-message trim (main) |
| `CHAT_MESSAGE_MAX_CHARS_ROUTING` | `450` | Per-message trim (routing) |
| `CHAT_CHROMA_MAX_CHARS` | `1400` | Chroma appendix in main prompts |
| `CHAT_CHROMA_MAX_CHARS_ROUTING` | `500` | Chroma appendix when routing |
| `CHAT_SUMMARY_LLM_ENABLED` | `true` | Summarize long threads |
| `CHAT_SUMMARY_MAX_MESSAGES` | `8` | Messages before summary |
| `CHAT_RAW_LOG_MAX_MESSAGES` | `40` | Server-side raw log cap |
| `ORCHESTRATOR_MAX_ROUNDS` | `3` | Max API tool rounds per turn |

## RAG embeddings (port 8081 or in-process)

| Variable | Default | Purpose |
|----------|---------|---------|
| `RAG_EMBEDDING_BACKEND` | `http` | `http` / `llama` → `:8081`; `sentence-transformers` → in-process |
| `EMBED_BASE_URL` | `http://localhost:8081/v1` | Embed server URL |
| `EMBED_SERVER_PORT` | `8081` | Used by `./scripts/run-embed-server.sh` |
| `SENTENCE_TRANSFORMERS_MODEL` | `BAAI/bge-small-en-v1.5` | HF id; intent router uses same model in-process |
| `EMBED_MODEL` | same as `SENTENCE_TRANSFORMERS_MODEL` | Model id sent to embed HTTP server |
| `LOCAL_MODELS_ROOT` | parent of repo | Weights under `{LOCAL_MODELS_ROOT}/embeddings/` |
| `EMBEDDING_EXPECTED_DIMENSION` | `384` | Warn on sync if vector length differs |
| `RAG_VECTOR_STORE` | `chroma` | `chroma` or legacy `numpy` (`.cache/kb_vectors.npz`) |
| `RAG_KEYWORD_FALLBACK` | `true` | Keyword KB match if embed/Chroma fails |

Download embed + rerank + warm intent cache:

```bash
python scripts/download_embedding_model.py
# or: python -m apex_rag_demo.download_models [--rerank-only]
```

## KB retrieval (bi-encoder + rerank)

LangGraph: `retrieve_bi_encoder` → `rerank_cross_encoder` → snippets to agent.

| Variable | Default | Purpose |
|----------|---------|---------|
| `RAG_RETRIEVE_K` | `10` | Chroma `n_results` before cross-encoder |
| `RAG_TOP_K` | `2` | Final KB snippets after rerank |
| `RAG_RERANK_ENABLED` | `true` | Cross-encoder rerank |
| `RAG_RERANK_MODEL` | `BAAI/bge-reranker-base` | sentence-transformers CrossEncoder |

Fetch uses `max(RAG_TOP_K, RAG_RETRIEVE_K)`. Rerank-only changes do **not** require `sync_index`.

## Chroma (Docker, port 8002)

| Variable | Default | Purpose |
|----------|---------|---------|
| `CHROMA_HOST` | `localhost` | HTTP host |
| `CHROMA_PORT` | `8002` | Host port (`docker-compose.yml`) |
| `CHROMA_HNSW_SPACE` | `cosine` | `cosine` / `l2` / `ip` — fixed at collection create |
| `CHROMA_COLLECTION` | `apex_kb` | Main KB vectors |
| `CHROMA_SESSION_COLLECTION` | `apex_session_intents` | Session intent memory |
| `CHROMA_STATE_COLLECTION` | `apex_graph_state` | LangGraph state metadata |
| `CHROMA_AGENT_ROLES_COLLECTION` | `apex_agent_roles` | Role hint vectors |
| `CHROMA_INTENT_ROUTES_COLLECTION` | `apex_intent_routes` | Pre-LLM intent route exemplars |

### Chroma query top-k (per collection)

| Variable | Default | Used in |
|----------|---------|---------|
| `CHROMA_INTENT_ROUTE_TOP_K` | `3` | `query_intent_routes` |
| `CHROMA_INTENT_ROUTE_MIN_SCORE` | `0.72` | Minimum similarity to accept a route |
| `CHROMA_SYSTEM_ENRICH_TOP_K` | `3` | Agent system prompt enrichment |
| `SESSION_MEMORY_TOP_K` | `3` | Similar past turns in session collection |

Session graph JSON (exact replay metadata) also lives under `data/session_graph/{userId}/{sessionId}.json`. Docker data: `./data/chroma/`, `./data/neo4j/`.

## Session memory & topic shift

| Variable | Default | Purpose |
|----------|---------|---------|
| `SESSION_MEMORY_ENABLED` | `true` | Write/read session vectors in Chroma |
| `SESSION_MEMORY_REUSE_MAX_DISTANCE` | `0.55` | Chroma distance gate for reuse (lower = stricter) |
| `INTENT_SEMANTIC_ENABLED` | `true` | NumPy cosine intent exemplars |
| `INTENT_SEMANTIC_MIN_SCORE` | `0.42` | Intent semantic threshold |
| `INTENT_SEMANTIC_MARGIN` | `0.06` | Winner margin vs runner-up |
| `TOPIC_SHIFT_MAX_SIMILARITY` | `0.52` | Below → treat as new topic |
| `TOPIC_HISTORY_MIN_SIMILARITY` | `0.40` | Keep prior turn if similar enough |
| `CONVERSATIONAL_MIN_SCORE` | `0.38` | Small-talk gate |
| `CONVERSATIONAL_VS_OPS_MARGIN` | `0.04` | Conversational vs ops intent |

## Knowledge graph (Neo4j, optional)

Detailed setup, ontology entity/relation list, sync CLI, and LangGraph `enrich_from_kg`: **[KG_NEO4J.md](./KG_NEO4J.md)**.

| Variable | Default | Purpose |
|----------|---------|---------|
| `KG_NEO4J_ENABLED` | `false` | Bolt client + `enrich_from_kg` |
| `NEO4J_URI` | `bolt://localhost:7687` | Bolt URL |
| `NEO4J_USER` | `neo4j` | Username |
| `NEO4J_PASSWORD` | `changeme` | Must match `NEO4J_AUTH` in compose |
| `KG_ONTOLOGY_PATH` | `data/kg/ontology/ticketing_apex.json` | Entity/relation schema |
| `KG_GLINER_ENABLED` | `true` | GLiNER extraction in `sync_kg_index` |
| `KG_GLINER_MODEL` | `urchade/gliner_medium-v2.1` | HF model |
| `KG_GLINER_THRESHOLD` | `0.45` | Mention confidence |
| `KG_ENRICH_MAX_HITS` | `8` | Max graph entities in chat context |

Compose-only (not read by Python): `NEO4J_HTTP_PORT`, `NEO4J_BOLT_PORT`.

**Ontology file:** `data/kg/ontology/ticketing_apex.json` (`KG_ONTOLOGY_PATH`) — domain `apex_ticketing_operations`, 9 entity types, GLiNER `gliner_label_map`, entity-resolution thresholds in JSON.

**Sync:** `python -m apex_rag_demo.rag.sync_kg_index` (requires Neo4j up + `KG_NEO4J_ENABLED=true`). **Ping:** `python scripts/neo4j_ping.py`.

## LangGraph runtime & plugins

| Variable | Default | Purpose |
|----------|---------|---------|
| `LANGGRAPH_RUNTIME_ENABLED` | `true` | SQLite checkpointer + store |
| `LANGGRAPH_CHECKPOINT_PATH` | `data/langgraph/checkpoints.sqlite` | Thread checkpoints |
| `LANGGRAPH_STORE_PATH` | `data/langgraph/store.sqlite` | Plugin / store KV |
| `DYNAMIC_TOOLS_ENABLED` | `true` | OpenAPI tool catalog + orchestrator |
| `PLUGIN_ALLOWED_HOST_SUFFIXES` | `api.apex-dev.axsdevops.io,…` | HTTP plugin allowlist |
| `PLUGIN_HTTP_TIMEOUT_SEC` | `30` | Plugin HTTP timeout |
| `PLUGIN_SCRIPT_ENABLED` | `true` | Sandboxed script plugins |
| `PLUGIN_SCRIPT_MAX_BYTES` | `16384` | Script size limit |
| `PLUGIN_SCRIPT_TIMEOUT_SEC` | `5` | Script CPU time |
| `PLUGIN_SANDBOX_BACKEND` | `auto` | `auto` / `docker` / `subprocess` / `inprocess` |
| `PLUGIN_DOCKER_IMAGE` | `ticketing-ai-demo-plugin-worker:local` | Worker image |
| `PLUGIN_TENANT_STRICT` | `true` | Tenant scoping for plugins |

### Docker sandbox toolkit (Python + React)

Separate from script plugins: disposable containers for **multi-file Python** or **React + Recharts** jobs (chat orchestrator `run_sandbox` or `POST /api/sandbox/run`). See [SANDBOX_TOOLKIT.md](./SANDBOX_TOOLKIT.md).

| Variable | Default | Purpose |
|----------|---------|---------|
| `SANDBOX_TOOLKIT_ENABLED` | `true` | Master switch; when false, sandbox node and API reject runs |
| `SANDBOX_TOOLKIT_IMAGE` | `ticketing-ai-demo-sandbox-toolkit:local` | Image from `./scripts/build-sandbox-toolkit.sh` |
| `SANDBOX_TOOLKIT_TIMEOUT_SEC` | `120` | Per-job wall clock (Docker run) |
| `SANDBOX_PIP_ALLOWLIST` | `pandas,numpy,matplotlib,httpx,pillow` | Extra `pip_packages` names (preinstalled in image) |
| `SANDBOX_NPM_ALLOWLIST` | `react,react-dom,recharts` | Extra `npm_packages` names |
| `SANDBOX_MAX_SOURCE_BYTES` | `65536` | Max total bytes of `files` in a job |

`GET /api/runtime/status` → `sandbox_toolkit`: `enabled`, `image`, `docker_cli`, `image_ready`, allowlists.

See [EXTENSIONS.md](./EXTENSIONS.md), [DYNAMIC_TOOLS.md](./DYNAMIC_TOOLS.md), [SANDBOX_TOOLKIT.md](./SANDBOX_TOOLKIT.md).

## apex-dev API bases

All `*_BASE_URL` and `*_SWAGGER_URL` keys are in `.env.example`. Catalog: `data/apex_services.json` and [API_LINKS.md](./API_LINKS.md).

| Variable | Default | Purpose |
|----------|---------|---------|
| `APEX_BEARER_TOKEN` | *(empty)* | CLI / server-side JWT; web uses pasted token |
| `APEX_MOCK` | `false` | Mock JSON when no token |
| `RESOURCES_CLIENT_ID` | `11` | B2B users list |
| `RESOURCES_AXS_CLIENT_ID` | `4` | B2B users list |
| `RESOURCES_USERS_PAGE_SIZE` | `50` | Users page size |
| `REPORTS_DEFAULT_CONTEXT_ID` | *(empty)* | Reports when message has no context id |
| `REPORTS_DEFAULT_REGION_ID` | `1` | Reports region fallback |
| `MARKETING_LIST_PAGE_SIZE` | `25` | Marketing list |
| `MARKETING_EVENT_ENRICH_MAX` | `24` | Enrich cap |
| `MARKETING_FALLBACK_SEARCH_QUERY` | `event` | Search fallback when marketing 403 |

Services include **Search**, **Admin**, **Resources**, **Events**, **Inventory**, **Marketing**, **Manifest**, **Reports**.

## Demo / safety

| Variable | Default | Purpose |
|----------|---------|---------|
| `DEMO_CLIENT_ID` | *(empty)* | UUID for create client venue |
| `DEMO_MUTATIONS_DRY_RUN` | `false` | `true` = all mutations preview-only |

Legacy: `DEMO_EXECUTE_WRITES` (inverted) still honored if `DEMO_MUTATIONS_DRY_RUN` unset.

## Web UI (no env vars)

- JWT in **sessionStorage**; forwarded as `Authorization: Bearer` on `/api/*`.
- Expired tokens redirect to login; the UI can offer to **re-run the last message** after re-authentication (`apex_ai_last_query`, `apex_ai_pending_rerun` in sessionStorage).
- Failed upstream API calls log **debug curl** on the **server console** only (not in the chat transcript).

Build UI: `./scripts/build-frontend.sh` → `apex_rag_demo/web/static/dist/`.
