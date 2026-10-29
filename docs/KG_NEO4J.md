# Knowledge graph (Neo4j + ontology)

Structured memory alongside **Chroma** vectors. Same KB text (`data/kb.json`, OpenAPI chunks) can live in both stores:

| Store | What it holds | Query style |
|-------|----------------|-------------|
| **Chroma** | Embedding vectors | Similarity search, intent routes, session memory |
| **Neo4j** | Typed nodes + relations | Term lookup, graph context in system prompt |

Chroma answers “what text is like this question?” Neo4j answers “what **entities** (events, venues, API paths) appear in the corpus and how are they linked?”

## Architecture

```text
data/kb.json (+ openapi KB texts)
   │
   ├─ sync_index ──► Chroma (BGE-small embeddings)
   │
   └─ sync_kg_index ──► extract_entities (GLiNER + regex)
                          └──► Neo4j (ontology-valid types only)

Chat turn (LangGraph):
   enrich_system_from_chroma  →  enrich_from_kg  →  retrieve / classify / …
                                      │
                                      └── kg_enrich.fetch_kg_system_appendix
                                          (Bolt read; appended to chroma_system_context)
```

**Routing is unchanged** — graph hits are **context only** (`Knowledge graph (Neo4j, context only — not routing):` in the system block). Live data still comes from apex-dev HTTP + JWT.

## Ontology contract

File: **`data/kg/ontology/ticketing_apex.json`**

| Field | Purpose |
|-------|---------|
| `domain` | `apex_ticketing_operations` |
| `version` | Schema version (e.g. `1.0`) |
| `entity_types` | Allowed node labels (9 types) |
| `relation_types` | Allowed edge types between those labels |
| `extraction.gliner_label_map` | GLiNER span labels → ontology entity names |
| `extraction.entity_resolution` | `auto_merge_threshold` (0.9), `review_threshold` (0.85) |

### Entity types (summary)

| Type | APEX meaning |
|------|----------------|
| `Event` | Ticketed occurrence (`eventId`) |
| `Organization` | Client / promoter org |
| `ClientVenue` | Venue under a client |
| `InventoryZone` | Admissions / zone from inventory |
| `PriceLevel`, `PriceCode`, `TicketType` | Publish / inventory pricing |
| `ApiEndpoint` | OpenAPI path + method from KB |
| `DocumentChunk` | KB chunk provenance |

### Relation types (summary)

Examples: `HOSTED_AT`, `OWNED_BY`, `HAS_ZONE`, `HAS_PRICE_LEVEL`, `USES_PRICE_CODE`, `OFFERS_TICKET_TYPE`, `MENTIONS`, `DESCRIBES`, `SAME_AS` (entity resolution merges only above threshold).

Loader: `apex_rag_demo.rag.kg_ontology` (`load_ontology`, `entity_type_names`).

**Only types listed in the ontology may be written** during sync — keeps the graph aligned with ticketing domain vocabulary.

## Docker + data on disk

From project root:

```bash
docker compose up -d neo4j
```

| Port | Service |
|------|---------|
| **7474** | Neo4j Browser (HTTP) |
| **7687** | Bolt (Python driver) |

Persistent files (survive `docker compose down`):

| Host path | Contents |
|-----------|----------|
| `./data/neo4j/data` | Graph database |
| `./data/neo4j/logs` | Server logs |
| `./data/neo4j/import` | Optional CSV import dir |

Compose sets `NEO4J_AUTH=neo4j/${NEO4J_PASSWORD:-changeme}` — **`NEO4J_PASSWORD` in `.env` must match**.

## Environment (`.env`)

| Variable | Default | Purpose |
|----------|---------|---------|
| `KG_NEO4J_ENABLED` | `false` | Enable Bolt client + runtime `enrich_from_kg` |
| `NEO4J_URI` | `bolt://localhost:7687` | Bolt URL |
| `NEO4J_USER` | `neo4j` | Username |
| `NEO4J_PASSWORD` | `changeme` | Password (match compose) |
| `KG_ONTOLOGY_PATH` | `data/kg/ontology/ticketing_apex.json` | Schema + GLiNER map |
| `KG_GLINER_ENABLED` | `true` | Use GLiNER in batch sync |
| `KG_GLINER_MODEL` | `urchade/gliner_medium-v2.1` | HF model (first sync downloads) |
| `KG_GLINER_THRESHOLD` | `0.45` | Mention confidence |
| `KG_ENRICH_MAX_HITS` | `8` | Max entity rows in chat appendix |

Compose-only (not read by Python): `NEO4J_HTTP_PORT`, `NEO4J_BOLT_PORT`.

Full env index: [CONFIG.md](./CONFIG.md).

## Setup checklist

1. **Project venv** (not the llama-cpp venv):

   ```bash
   cd ticketing-ai-demo && source .venv/bin/activate
   pip install -r requirements.txt   # neo4j + gliner
   ```

2. **Start Neo4j** and enable in `.env`:

   ```bash
   docker compose up -d neo4j
   # KG_NEO4J_ENABLED=true
   # NEO4J_PASSWORD=changeme
   ```

3. **Connectivity + ontology load**:

   ```bash
   python scripts/neo4j_ping.py
   ```

   Expected: `Ontology: apex_ticketing_operations v1.0 — entity types: 9` then `Neo4j: connected ok`.

4. **Sync KB into the graph** (after Chroma KB sync is optional but recommended for same corpus):

   ```bash
   python -m apex_rag_demo.rag.sync_kg_index
   python -m apex_rag_demo.rag.sync_kg_index --force   # re-extract all chunks
   ```

   Skips work when KB fingerprint unchanged (unless `--force`). Extraction: `kg_entities.extract_entities` → `kg_store.sync_chunk`.

5. **Restart web app** so `KG_NEO4J_ENABLED` is picked up.

## Runtime behavior

- LangGraph node **`enrich_from_kg`** runs after Chroma system enrichment (skipped on `topic_shift`).
- **`kg_enrich.fetch_kg_system_appendix`**: tokenizes question + `session_focus`, queries Neo4j (`kg_store.query_context_rows`, chunk mentions), caps at `KG_ENRICH_MAX_HITS`.
- If Neo4j is down or disabled, enrichment is a no-op (chat still works on Chroma + APIs).

Stream progress label: **`kg_enrich`**.

## Code map

| Module | Role |
|--------|------|
| `rag/neo4j_client.py` | Bolt driver, `neo4j_configured()`, connectivity |
| `rag/kg_ontology.py` | Load JSON schema |
| `rag/kg_entities.py` | GLiNER + regex extraction |
| `rag/kg_store.py` | Schema, sync, Cypher queries |
| `rag/kg_sync.py` | Batch `sync_kb_to_graph` |
| `rag/sync_kg_index.py` | CLI entry |
| `rag/kg_enrich.py` | Chat-time appendix |
| `graph.py` | `enrich_from_kg` node |

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `No module named 'neo4j'` | Activate **project** `.venv`; `pip install -r requirements.txt` |
| `KG_NEO4J_ENABLED=false` | Set `true` in `.env`, restart app |
| Bolt auth failed | Match `NEO4J_PASSWORD` to `docker-compose.yml` |
| Empty graph in Browser | Run `sync_kg_index` after Neo4j is up |
| Slow first sync | GLiNER model download; or `KG_GLINER_ENABLED=false` for regex/UUID paths only |
| `Neo4j is disabled` on sync | Same as enabling flag + running container |

## Related

- [SETUP.md](./SETUP.md) — environment and bring-up  
- [RAG_STACK.md](./RAG_STACK.md) — Chroma + dual-store quick start  
- [ARCHITECTURE.md](./ARCHITECTURE.md) — full LangGraph flow  
- [CONFIG.md](./CONFIG.md) — all environment variables  
