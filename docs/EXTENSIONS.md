# User-defined plugins & LangGraph persistence

Admins/operators can register **HTTP plugins** (declarative URLs) or **script plugins** (sandboxed JavaScript / restricted Python). LangGraph uses a **SQLite checkpointer** and **SQLite store** for thread state and plugin definitions.

## Runtime backends

| Backend | Path (default) | Purpose |
|---------|----------------|---------|
| Checkpointer | `data/langgraph/checkpoints.sqlite` | Resume LangGraph threads per `user_id:session_id` |
| Store | `data/langgraph/store.sqlite` | Plugin definitions (`namespace`: `plugins`, `user:{id}`) |

Env:

```bash
LANGGRAPH_RUNTIME_ENABLED=true
LANGGRAPH_CHECKPOINT_PATH=data/langgraph/checkpoints.sqlite
LANGGRAPH_STORE_PATH=data/langgraph/store.sqlite
PLUGIN_ALLOWED_HOST_SUFFIXES=api.apex-dev.axsdevops.io,localhost,127.0.0.1
```

Health: `GET /api/runtime/status` (no auth).

## Sandbox rules

### HTTP plugins (`kind: "http"`)

- **Allowed:** HTTPS/HTTP calls to hosts matching `PLUGIN_ALLOWED_HOST_SUFFIXES`, `{param}` substitution in URL/body, static headers, JSON/text responses.
- **Blocked:** Disallowed hosts, unknown parameters, header injection (`Host`, etc.).

### Script plugins (`kind: "script"`)

- **True sandbox (recommended):** each invoke runs in a **throwaway Docker container** (`PLUGIN_SANDBOX_BACKEND=auto` or `docker`). Build once: `./scripts/build-plugin-worker.sh` or `docker compose --profile plugins build plugin-worker`. Image default: `ticketing-ai-demo-plugin-worker:local`. Container has **no network**, read-only root, dropped caps, memory/CPU/pids limits.
- **Fallback:** if `auto` and the image is missing, scripts run in a **fresh subprocess** on the app host (weaker — fine for local dev only).
- **JavaScript** runs in an isolated **QuickJS** context (no `import`, `fetch`, `eval`, `require`, …).
- **Python** runs via **RestrictedPython** (no `import`, `open`, `exec`, `subprocess`, …).
- Limits: `PLUGIN_SCRIPT_MAX_BYTES` (default 16 KiB), `PLUGIN_SCRIPT_TIMEOUT_SEC` (default 5s). Disable with `PLUGIN_SCRIPT_ENABLED=false`.
- `GET /api/runtime/status` → `script_sandbox.true_sandbox` and `docker_image_ready`.
- Handler contract: define `entry_function` (default `handler`) as `function handler(input) { … }` or `def handler(input): …` returning JSON-serializable data.
- **No network or filesystem** from script handlers — use HTTP plugins for API calls.

Invoke defaults to **`dry_run: true`** for HTTP (preview request). Script `dry_run` validates source and returns metadata without executing.

## Plugin API (Bearer JWT)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/plugins` | List your plugins |
| POST | `/api/plugins` | Create/replace by id |
| GET | `/api/plugins/{id}` | Get one |
| PUT | `/api/plugins/{id}` | Update |
| DELETE | `/api/plugins/{id}` | Delete |
| POST | `/api/plugins/{id}/invoke` | Run sandbox (`{"parameters": {}, "dry_run": true}`) |

Example body (`POST /api/plugins`):

```json
{
  "id": "search-health",
  "name": "Search OpenAPI",
  "description": "Fetch search swagger JSON",
  "method": "GET",
  "url_template": "https://api.apex-dev.axsdevops.io/search/swagger/v1/swagger.json",
  "parameters": [],
  "headers": {},
  "response_format": "json",
  "enabled": true
}
```

Samples: `data/plugins/example_search_health.json` (HTTP), `data/plugins/example_script_transform.json` (JavaScript).

Script example (`POST /api/plugins`):

```json
{
  "kind": "script",
  "id": "greet-transform",
  "name": "Greet",
  "language": "javascript",
  "source": "function handler(input) { return { hi: input.name }; }\n",
  "parameters": [{ "name": "name", "type": "string" }],
  "enabled": true
}
```

Then: `POST /api/plugins/greet-transform/invoke` with `{"parameters": {"name": "Sam"}, "dry_run": false}`.

## Wiring custom tools into the agent

Registered plugins are included in the orchestrator system prompt (`plugin_catalog_block`). The LLM may return **`action: call_plugin`** with `plugin_id` and `plugin_parameters` (or `parameters`). Execution goes through the same sandbox as `/api/plugins/{id}/invoke` (HTTP allowlist or script worker).

**Deterministic shortcuts** (no classify/orchestrator LLM):

- `run plugin my-plugin-id`, `invoke plugin …`, or `@my-plugin-id` → `call_plugin` when the id exists for the tenant.
- Phrases matching the sandbox hint regex (e.g. “build a react chart”, “run python code”) → **`run_sandbox`** when `SANDBOX_TOOLKIT_ENABLED=true` — see [SANDBOX_TOOLKIT.md](./SANDBOX_TOOLKIT.md).

Built-in apex-dev APIs still use **`call_api`** via dynamic OpenAPI tools ([DYNAMIC_TOOLS.md](./DYNAMIC_TOOLS.md)).

## Security note

With `PLUGIN_SANDBOX_BACKEND=docker` and the worker image built, script plugins get **kernel-level isolation** per invoke. HTTP plugins remain the safest path for calling apex-dev APIs (no user code — server-side allowlisted `httpx` only).

For **on-the-fly Python + React (Recharts) in disposable containers** and a LangGraph `sandbox_tool_run` node, see [SANDBOX_TOOLKIT.md](./SANDBOX_TOOLKIT.md).
