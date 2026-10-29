# Docker sandbox toolkit (Python + React in disposable containers)

The **sandbox toolkit** runs user-supplied **multi-file Python** or **React (Recharts)** inside a throwaway Docker container (`--network none`, memory/CPU/pids limits). It is **not** the same as script plugins ([EXTENSIONS.md](./EXTENSIONS.md)): toolkit jobs can ship full `App.jsx` bundles and return rendered HTML for the chat UI.

## Build the image

```bash
./scripts/build-sandbox-toolkit.sh
# or: docker compose --profile sandbox build sandbox-toolkit
```

Default tag: `ticketing-ai-demo-sandbox-toolkit:local` (`SANDBOX_TOOLKIT_IMAGE`).

## Configuration

| Variable | Default | Purpose |
|----------|---------|---------|
| `SANDBOX_TOOLKIT_ENABLED` | `true` | Off → orchestrator skips sandbox; API returns error |
| `SANDBOX_TOOLKIT_IMAGE` | `ticketing-ai-demo-sandbox-toolkit:local` | Docker image name |
| `SANDBOX_TOOLKIT_TIMEOUT_SEC` | `120` | Job timeout |
| `SANDBOX_PIP_ALLOWLIST` | see `.env.example` | Names allowed in `pip_packages` |
| `SANDBOX_NPM_ALLOWLIST` | `react,react-dom,recharts` | Names allowed in `npm_packages` |
| `SANDBOX_MAX_SOURCE_BYTES` | `65536` | Cap on total `files` payload |

Full table: [CONFIG.md](./CONFIG.md).

## Readiness

```bash
curl -s http://localhost:8080/api/runtime/status | python3 -c "import sys,json; print(json.load(sys.stdin)['sandbox_toolkit'])"
```

Expect `docker_cli: true` and `image_ready: true` before chat sandbox steps succeed.

## REST API

| Method | Path | Auth |
|--------|------|------|
| POST | `/api/sandbox/run` | Bearer JWT (same as chat) |

Request body:

```json
{
  "job": {
    "runtime": "python",
    "files": {
      "main.py": "def handler(input):\n    return {\"ok\": True, \"keys\": list(input.keys())}\n"
    },
    "input": { "hello": "world" },
    "entry": "handler",
    "pip_packages": [],
    "npm_packages": []
  }
}
```

| Field | Notes |
|-------|--------|
| `runtime` | `python` or `react` |
| `files` | Map of path → source; Python default entry file `main.py` with `def handler(input):` |
| `input` | JSON passed into handler / React `App` props as `{ input }` |
| `pip_packages` / `npm_packages` | Must be subset of allowlists; deps are preinstalled in the image |

Response (`SandboxResult`): `ok`, `runtime`, `result` (Python JSON), `html` (React), `error`, `container_id`.

Example:

```bash
curl -s -X POST http://localhost:8080/api/sandbox/run \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "job": {
      "runtime": "python",
      "files": {"main.py": "def handler(input):\n    return {\"ok\": True, \"keys\": list(input.keys())}\n"},
      "input": {"hello": "world"}
    }
  }'
```

## LangGraph (chat)

```text
orchestrator_decide
  → action run_sandbox → sandbox_tool_run → extract_api_facts → orchestrator_decide (loop) or synthesize_answer
```

- Orchestrator JSON: `"action": "run_sandbox"` plus a `"sandbox"` block (same shape as `job` above). The LLM prompt includes `orchestrator_sandbox_catalog_block()` with preinstalled packages.
- **Deterministic path:** before the orchestrator LLM, `try_sandbox_orchestrator_step` matches phrases like “build a react chart”, “custom python”, “sandbox react”, etc. It seeds a sample job using recent `api_trace` rows as `input`.
- Progress label in stream UI: `Docker sandbox (Python / React)…`
- State: `sandbox_display` → UI article or **`type: sandbox`** with `sandbox_html` (React).

React output renders in a sandboxed iframe (`allow-scripts` only) in the React display panel.

## Security

- Each run: `docker run --rm --network none` with resource limits.
- Extra packages must appear in `SANDBOX_PIP_ALLOWLIST` / `SANDBOX_NPM_ALLOWLIST`; runtime install only works for allowlisted names baked into the image.
- No host filesystem or network from job code — same isolation model as plugin script workers, different image and job format.

## Related

- [EXTENSIONS.md](./EXTENSIONS.md) — HTTP/script plugins, `call_plugin`, plugin worker image
- [ARCHITECTURE.md](./ARCHITECTURE.md) — full agent graph
- [SETUP.md](./SETUP.md) — Docker profiles `sandbox` / `plugins`
