"""Batch sync KB chunks into Neo4j (GLiNER + regex extraction)."""

from __future__ import annotations

from typing import Any

from apex_rag_demo.rag.kb import load_kb
from apex_rag_demo.rag.kg_entities import extract_entities
from apex_rag_demo.rag.kg_store import (
    ensure_schema,
    get_stored_fingerprint,
    kb_fingerprint,
    set_stored_fingerprint,
    sync_chunk,
)
from apex_rag_demo.rag.neo4j_client import neo4j_configured


def sync_kb_to_graph(*, force: bool = False) -> dict[str, Any]:
    if not neo4j_configured():
        raise RuntimeError("Neo4j is disabled — set KG_NEO4J_ENABLED=true and start docker neo4j")

    chunks = load_kb()
    fingerprint = kb_fingerprint(chunks)
    if not force and get_stored_fingerprint() == fingerprint:
        return {"skipped": True, "chunks": len(chunks), "entities": 0}

    ensure_schema()
    entity_count = 0
    for chunk in chunks:
        entities = extract_entities(chunk.text)
        entity_count += sync_chunk(chunk, entities)

    set_stored_fingerprint(fingerprint, len(chunks))
    return {
        "skipped": False,
        "chunks": len(chunks),
        "entities": entity_count,
        "fingerprint": fingerprint[:16],
    }
