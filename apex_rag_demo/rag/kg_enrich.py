"""Runtime knowledge-graph context for the chat system prompt."""

from __future__ import annotations

from typing import Any

from apex_rag_demo.config import KG_ENRICH_MAX_HITS
from apex_rag_demo.rag.kg_entities import lookup_terms
from apex_rag_demo.rag.kg_store import query_chunks_for_terms, query_context_rows
from apex_rag_demo.rag.neo4j_client import neo4j_configured


def fetch_kg_system_appendix(
    question: str,
    session_focus: dict[str, Any] | None = None,
) -> str:
    if not neo4j_configured():
        return ""

    terms = lookup_terms(question, session_focus)
    if not terms:
        return ""

    rows = query_context_rows(terms, KG_ENRICH_MAX_HITS)
    chunk_lines = query_chunks_for_terms(terms, 3)
    if not rows and not chunk_lines:
        return ""

    lines = ["Knowledge graph (Neo4j, context only — not routing):"]
    for row in rows:
        kind = row.get("nodeType") or "Entity"
        name = row.get("name") or ""
        eid = row.get("eventId") or ""
        path = row.get("path") or ""
        extra = eid or path or row.get("clientVenueId") or ""
        lines.append(f"- {kind}: {name}" + (f" ({extra})" if extra else ""))
    for snippet in chunk_lines:
        lines.append(f"- KB mention: {snippet[:350]}")
    return "\n".join(lines)[:4000]
