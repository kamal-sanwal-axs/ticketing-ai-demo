# Manual UI display test matrix

Use these after changing `apex_rag_demo/ui_display.py`, enrichment, or the React datatable.  
**Prerequisites:** web app on `:8080`, valid apex-dev JWT, region selected.

Automated fixture checks: `pytest tests/test_ui_display_matrix.py -q`

## How to read results

| `display.type` | UI behavior |
|----------------|-------------|
| `table` | Primary datatable (columns + rows + count) |
| `dashboard` | Table + chart(s) in `charts` |
| `article` | Prose, `fields`, and/or nested `sections` (may include sub-tables) |

Also check: `subtitle`, `footnote`, `paragraphs`, `sections[]`, `level` (`error` / `warning`), `badge` (intent).

---

## A. Marketing events (`marketing_events`)

| # | Chat prompt (example) | API / payload condition | Expected `type` | Verify |
|---|-------------------------|-------------------------|-----------------|--------|
| A1 | `show me events` | Marketing GET returns rows with names | `table` | Title **Events**, catalog columns (Event, Start, End, Status, ID), count matches rows |
| A2 | `show events count` | Same as A1 (count routes to marketing list) | `table` | Answer text includes **Found N result(s)**; table count = named rows only |
| A3 | `show event names only` | Named events in payload | `table` | Only **Event** + **Event ID** columns |
| A4 | `list events with org hierarchy` | Named events | `table` | Org / client / venue columns present |
| A5 | `show on-sale events` | Lifecycle filter applied (`_lifecycle_filter` in payload) | `table` | Subtitle or paragraphs mention on-sale filter; row statuses mostly on-sale/published |
| A6 | `events after October 2026` | `_date_filter` in payload | `table` or `dashboard` | Subtitle includes date filter note; optional timeline chart |
| A7 | `events by month chart` | Rows with `startDate` | `dashboard` | `charts[0].kind` = bar, **Events by start month** |
| A8 | Catalog includes ID-only stubs | Rows missing title/headliners | `table` + `sections` | Main table excludes ID-only; section **Hidden — ID only** with second table |
| A9 | After enrichment run | `_event_enrichment.resolved_names` > 0 | `table` | Paragraph mentions **Hydrated N name(s) from events-api** |
| A10 | Marketing 403, search fallback | `_source` = `search-api-fallback` | `table` | Title **Events (search fallback)**; footnote about token/marketing |
| A11 | Date filter excludes all on page | `_date_filter`, zero named rows | `article` | Paragraph: no events matched date filter |
| A12 | Mock token / `USE_MOCK_API` | `_mock: true` on payload | `table` | Footnote: **Sample data (mock or missing token)** |

---

## B. Event search (`search_events`)

| # | Prompt | Payload condition | Expected `type` | Verify |
|---|--------|-------------------|-----------------|--------|
| B1 | `search events matching Splash House` | Suggest/post returns events | `table` | Subtitle includes suggest or POST path + query |
| B2 | Same, zero matches | Empty `events` | `article` | Empty-state paragraphs (try artist name) |
| B3 | `search events with org hierarchy` | Non-empty events | `table` | Hierarchy columns |

---

## C. Orders & customers

| # | Prompt | Condition | Expected `type` | Verify |
|---|--------|-----------|-----------------|--------|
| C1 | `search orders for fan@example.com` | `orders[]` non-empty | `table` | Order #, customer, email, payment columns |
| C2 | Valid query, empty `orders` | `orders: []` | `article` | **No orders matched** paragraph |
| C3 | `search customers for a@b.com` | `customers[]` | `table` | Customer columns |
| C4 | Vague order query (precheck) | No API call | `article` | Guidance text, no HTTP 500 panel |

---

## D. Registry & users

| # | Prompt | Condition | Expected `type` | Verify |
|---|--------|-----------|-----------------|--------|
| D1 | `list client venues` | Search client-venues payload | `table` | Org → client → venue columns |
| D2 | `list users` | Resources users payload | `article` | `sections` with user tables |

---

## E. Single event & inventory

| # | Prompt | Condition | Expected `type` | Verify |
|---|--------|-----------|-----------------|--------|
| E1 | `get event <uuid>` | Full GET payload | `article` | `fields` (dates, status, venue) |
| E2 | `get event` (no uuid) | Empty plan | `article` | `level: warning`, include UUID hint |
| E3 | `get event <uuid> with inventory` | `_inventory` on payload | `article` | Inventory `sections` (zones, price levels) |
| E4 | `inventory zones for <uuid>` | Inventory snapshot | `article` | Title **Event inventory** |

---

## F. Mutations & confirm

| # | Prompt | Condition | Expected `type` | Verify |
|---|--------|-----------|-----------------|--------|
| F1 | Create org (dry-run) | `_dryRun` / dry-run payload | `article` | `level: warning`, Mode = dry-run |
| F2 | Create client venue (dry-run) | Same | `article` | Fields for name, client id |
| F3 | Update event name (dry-run) | Preview payload | `article` | Previous vs new title fields |
| F4 | Pending confirm mutation | `_pending_confirmation` | `article` | **Confirm before sending**, `pending_confirmation` block |

---

## G. Publish & API errors

| # | Prompt | Condition | Expected `type` | Verify |
|---|--------|-----------|-----------------|--------|
| G1 | Publish conflict | `_mutation_error` + publish context | `article` | `level: warning`, citations to publish GET |
| G2 | `show events` with marketing 403 | `api_error` contains 403 | `article` | `level: error`, extra marketing permission lines |
| G3 | Upstream 500 (e.g. bad orders call) | `pipeline_error` dict | `article` | `badge: error`, fields Error code / HTTP / Endpoint |

---

## H. Explain / conversational (no API table)

| # | Prompt | Expected display |
|---|--------|------------------|
| H1 | `hello` | Welcome article |
| H2 | `help` | Help article + example table section |
| H3 | `what's your name` | Identity article |
| H4 | `what's the weather` | Off-topic article + example prompts table |
| H5 | `buy me a ticket` | Fan purchase guidance article |
| H6 | `tell me about pricing` (vague) | **Need a clearer request** warning article |

---

## I. Compound (multi-step)

| # | Prompt | Condition | Expected |
|---|--------|-----------|----------|
| I1 | `show published events with price codes and ticket types` | `api_trace` with marketing + inventory steps | Compound layout: section **Step 1 — Published / on-sale events** + inventory sections |

---

## Quick smoke (5 minutes)

1. `hello` → welcome article  
2. `show me events` → events table (A1)  
3. `show events count` → table + answer count (A2)  
4. `search events matching <known name>` → search table or empty article (B1/B2)  
5. `list client venues` → venues table (D1)  

## Regression: your tenant (ID-only rows)

After `show me events`, confirm:

- Main table shows only rows with display names (e.g. 15 of 15).  
- If marketing returns ID-only catalog entries, a second section **Hidden — ID only** appears.  
- Enrichment footnote appears when events-api hydrates names.
