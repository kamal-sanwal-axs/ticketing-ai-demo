"""Neo4j persistence for KB-derived knowledge graph nodes."""

from __future__ import annotations

import hashlib
import json
import re
import time
from typing import Any

from apex_rag_demo.rag.kb import KbChunk, load_kb
from apex_rag_demo.rag.kg_entities import ExtractedEntity
from apex_rag_demo.rag.kg_ontology import entity_type_names
from apex_rag_demo.rag.neo4j_client import get_driver, neo4j_configured

_META_LABEL = "KgMeta"


def kb_fingerprint(chunks: list[KbChunk]) -> str:
    ordered = sorted(chunks, key=lambda c: c.id)
    payload = json.dumps(
        [{"id": c.id, "text": c.text} for c in ordered],
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _safe_label(name: str) -> str:
    if name not in entity_type_names():
        return "Entity"
    return name


def ensure_schema() -> None:
    if not neo4j_configured():
        return
    driver = get_driver()
    try:
        with driver.session() as session:
            session.run(
                f"CREATE CONSTRAINT kgmeta_id IF NOT EXISTS FOR (m:{_META_LABEL}) "
                "REQUIRE m.id IS UNIQUE",
            )
            session.run(
                "CREATE CONSTRAINT docchunk_id IF NOT EXISTS FOR (c:DocumentChunk) "
                "REQUIRE c.chunkId IS UNIQUE",
            )
            for label in entity_type_names():
                if not re.match(r"^[A-Za-z][A-Za-z0-9_]*$", label):
                    continue
                session.run(
                    f"CREATE CONSTRAINT {label.lower()}_canonical IF NOT EXISTS "
                    f"FOR (n:`{label}`) REQUIRE n.canonicalKey IS UNIQUE",
                )
    finally:
        driver.close()


def get_stored_fingerprint() -> str | None:
    if not neo4j_configured():
        return None
    rows = _run_read(
        f"MATCH (m:{_META_LABEL} {{id: 'kb'}}) RETURN m.kbFingerprint AS fp LIMIT 1",
    )
    if not rows:
        return None
    fp = rows[0].get("fp")
    return str(fp) if fp else None


def set_stored_fingerprint(fp: str, chunk_count: int) -> None:
    _run_write(
        f"""
        MERGE (m:{_META_LABEL} {{id: 'kb'}})
        SET m.kbFingerprint = $fp, m.chunkCount = $n, m.updatedAt = $ts
        """,
        {"fp": fp, "n": chunk_count, "ts": int(time.time())},
    )


def _run_read(query: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    driver = get_driver()
    try:
        with driver.session() as session:
            return [dict(r) for r in session.run(query, params or {})]
    finally:
        driver.close()


def _run_write(query: str, params: dict[str, Any] | None = None) -> None:
    driver = get_driver()
    try:
        with driver.session() as session:
            session.run(query, params or {})
    finally:
        driver.close()


def merge_document_chunk(chunk: KbChunk) -> None:
    text_hash = hashlib.sha256(chunk.text.encode("utf-8")).hexdigest()[:32]
    _run_write(
        """
        MERGE (c:DocumentChunk {chunkId: $chunkId})
        SET c.text = $text, c.source = $source, c.textHash = $textHash, c.updatedAt = $ts
        """,
        {
            "chunkId": chunk.id,
            "text": chunk.text[:8000],
            "source": "kb",
            "textHash": text_hash,
            "ts": int(time.time()),
        },
    )


def merge_entity(ent: ExtractedEntity) -> None:
    label = _safe_label(ent.entity_type)
    props: dict[str, Any] = {
        "canonicalKey": ent.canonical_key(),
        "name": ent.text[:500],
        "updatedAt": int(time.time()),
    }
    if label == "Event" and re.fullmatch(
        r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}",
        ent.text.strip(),
    ):
        props["eventId"] = ent.text.strip()
    if label == "ApiEndpoint":
        m = re.search(r"(GET|POST|PUT|PATCH|DELETE)\s+(/\S+)", ent.text, re.I)
        if m:
            props["method"] = m.group(1).upper()
            props["path"] = m.group(2)
        elif ent.text.strip().startswith("/"):
            props["method"] = "GET"
            props["path"] = ent.text.strip()
    _run_write(
        f"""
        MERGE (n:`{label}` {{canonicalKey: $canonicalKey}})
        SET n += $props
        """,
        {"canonicalKey": props["canonicalKey"], "props": props},
    )


def link_chunk_mentions(chunk_id: str, ent: ExtractedEntity) -> None:
    label = _safe_label(ent.entity_type)
    _run_write(
        f"""
        MATCH (c:DocumentChunk {{chunkId: $chunkId}})
        MATCH (e:`{label}` {{canonicalKey: $canonicalKey}})
        MERGE (c)-[r:MENTIONS]->(e)
        SET r.score = $score, r.updatedAt = $ts
        """,
        {
            "chunkId": chunk_id,
            "canonicalKey": ent.canonical_key(),
            "score": ent.score,
            "ts": int(time.time()),
        },
    )


def sync_chunk(chunk: KbChunk, entities: list[ExtractedEntity]) -> int:
    merge_document_chunk(chunk)
    for ent in entities:
        merge_entity(ent)
        link_chunk_mentions(chunk.id, ent)
    return len(entities)


def query_context_rows(terms: list[str], limit: int) -> list[dict[str, Any]]:
    if not terms or not neo4j_configured():
        return []
    allowed = [l for l in entity_type_names() if l != "DocumentChunk"]
    if not allowed:
        return []
    return _run_read(
        """
        UNWIND $terms AS term
        MATCH (n)
        WHERE any(l IN labels(n) WHERE l IN $allowed)
          AND (
            coalesce(n.eventId, '') = term
            OR coalesce(n.clientVenueId, '') = term
            OR coalesce(n.organizationId, '') = term
            OR coalesce(n.path, '') CONTAINS term
            OR toLower(coalesce(n.name, '')) CONTAINS toLower(term)
          )
        RETURN DISTINCT labels(n)[0] AS nodeType, n.name AS name,
               n.eventId AS eventId, n.clientVenueId AS clientVenueId,
               n.method AS method, n.path AS path
        LIMIT $limit
        """,
        {"terms": terms, "allowed": allowed, "limit": limit},
    )


def query_chunks_for_terms(terms: list[str], limit: int) -> list[str]:
    if not terms or not neo4j_configured():
        return []
    rows = _run_read(
        """
        UNWIND $terms AS term
        MATCH (c:DocumentChunk)-[:MENTIONS]->(e)
        WHERE e.eventId = term OR e.path CONTAINS term
           OR toLower(coalesce(e.name, '')) CONTAINS toLower(term)
        RETURN DISTINCT c.chunkId AS id, c.text AS text
        LIMIT $limit
        """,
        {"terms": terms, "limit": limit},
    )
    return [str(r.get("text") or "")[:400] for r in rows if r.get("text")]
