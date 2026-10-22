# Intent routing vs MCP (per-service tools)

## What the demo does today

```text
User message → heuristics (fast, deterministic)
            → optional small LLM classify (one token)
            → single intent → one HTTP client call
```

| User idea | Intent | API |
|-----------|--------|-----|
| all events / list events | `marketing_events` | Marketing `GET /v1/events` |
| search events matching X | `search_events` | Search `POST /v1/events/suggest` |
| list client venues | `list_client_venues` | Search `POST /v1/client-venues` |
| get event `{uuid}` | `get_event` | Events `GET /{eventId}` |

**Client venues** are venue/org configuration in Search/Admin — not the same as **ticketed events** (Marketing list or Search index).

Heuristics run **before** the classifier so short phrases like `all events` do not get sent to `list_client_venues`.

## Would MCP help?

**Yes, for a production assistant** where users speak freely and you want the model to pick among many operations:

- One MCP server (or tool bundle) per bounded API: Search, Events, Inventory, Marketing, Admin.
- Each tool exposes OpenAPI-shaped actions with typed parameters.
- The agent loop chooses tools from descriptions instead of a fixed intent enum.

**Tradeoffs**

| Approach | Pros | Cons |
|----------|------|------|
| **Intents (this demo)** | Predictable, testable, cheap on small models | Must maintain rules; edge phrases need updates |
| **MCP / tool calling** | Flexible; model sees real tool schemas | Needs stronger model, auth per tool, latency, guardrails for writes |

**Practical path**

1. Keep deterministic routing for high-traffic, safety-critical paths (list events vs venues, dry-run creates).
2. Add MCP tools incrementally (e.g. Search suggest + Marketing list first).
3. Use MCP for exploration; keep Admin writes behind explicit dry-run + human review.

This repo can grow MCP servers later without removing the intent layer — use MCP inside `execute_action` when `AGENT_MODE=mcp` is set.
