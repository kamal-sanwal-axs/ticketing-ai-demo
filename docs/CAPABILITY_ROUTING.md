# Capability routing (Cursor-style) vs intent regex

## What Cursor does (roughly)

Cursor does **not** ship a fixed regex per user phrase. It:

1. Exposes **tools** with natural-language descriptions (read file, search repo, run terminal, …).
2. Retrieves **relevant context** (open files, docs, `@` symbols).
3. Lets the **model pick a tool** whose description matches the user goal.
4. Applies **validators** on arguments (sandbox, permissions), not phrase→tool maps.

## What this demo did before

Layers stacked on each other:

| Layer | Role |
|-------|------|
| Regex (`order_intent_helpers`, `intent_helpers`) | Phrase → intent |
| Sentence-transformer exemplars (`intent_semantic`) | Fixed phrase list per intent |
| Chroma intent routes | Harness + exemplar prompts |
| LLM classify + orchestrator | Picks from `INTENTS` enum |
| `guard_api_intent` | Regex overrides |

Adding “show me last 5 search” meant **another regex** — that does not scale to new APIs or tenants.

## Target pattern

```text
User message
    → embed against CAPABILITY statements (JSON + CRUD + OpenAPI KB text)
    → best READ capability (margin + min score)
    → reconcile with LLM intent (correct weak fits)
    → plan enrichment (pageSize, dates) from generic parsers
    → execute HTTP
    → validators (e.g. order search must have email — not routing)
```

**Capabilities** are data, not code:

- `data/capability_statements.json` — operator phrases per intent (easy to edit).
- `CRUD_CATALOG` — auto-injected summaries + HTTP lines.
- `data/kb_openapi.json` — optional; path text mapped to intents heuristically.

New system / new endpoint:

1. Run OpenAPI sync (`python -m apex_rag_demo.rag.sync_openapi_kb`) so KB chunks exist.
2. Add a block to `capability_statements.json` (or rely on OpenAPI text mapping).
3. Restart app (capability index is cached) — **no new Python regex**.

## Code

| Module | Purpose |
|--------|---------|
| `apex_rag_demo/capability_routing.py` | Embed capabilities, score, correct READ intents |
| `guard_api_intent` / `reconcile_classified_intent` | Call `capability_correct_read_intent` |
| `plan_for_intent` path | `enrich_read_plan_from_question` for `pageSize`, etc. |
| `order_search_precheck` | **Validator** only — blocks bad `/v1/orders` bodies |

## Status API

`GET /api/runtime/status` can include `capability_routing` (phrase count, intents covered).

## When LLM still matters

- Mutations, multi-step chains, ambiguous follow-ups (“publish it”) still use **classify + orchestrator LLM**.
- Capability routing **narrows READ mistakes** (orders vs event catalog) where small models and regex fail.

## Contrast with “fix list of intents”

`INTENTS` remains the **execution enum** (each maps to one dispatcher). Capabilities are the **discovery layer** — like tool descriptions — not a growing `if "last 5" in q` list.
