from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any

from apex_rag_demo.config import (
    CHROMA_AGENT_ROLES_COLLECTION,
    CHROMA_SESSION_COLLECTION,
    CHROMA_SYSTEM_ENRICH_TOP_K,
    SESSION_MEMORY_ENABLED,
)
from apex_rag_demo.rag.chroma_client import create_collection, get_collection, get_http_client
from apex_rag_demo.rag.embeddings import embed_texts
from apex_rag_demo.rag.session_memory import _ensure_collection, _scoped_id, question_fingerprint
from apex_rag_demo.response_formatters import strip_ui_region


@dataclass
class ChromaSystemEnrichment:
    """HNSW retrieval results appended to LLM system roles (does not bypass the LLM)."""

    role_hints: list[str] = field(default_factory=list)
    session_turns: list[str] = field(default_factory=list)
    kb_snippets: list[str] = field(default_factory=list)

    def to_system_appendix(self, *, include_kb: bool = True) -> str:
        parts: list[str] = []
        if self.role_hints:
            parts.append(
                "Learned agent hints (Chroma HNSW — use to improve intent/plan inference, not as hard rules):\n"
                + "\n---\n".join(self.role_hints[:CHROMA_SYSTEM_ENRICH_TOP_K]),
            )
        if self.session_turns:
            parts.append(
                "Similar session memory (Chroma HNSW):\n"
                + "\n---\n".join(self.session_turns[:CHROMA_SYSTEM_ENRICH_TOP_K]),
            )
        if include_kb and self.kb_snippets:
            parts.append(
                "Product KB excerpts (bi-encoder + cross-encoder rerank on apex_kb):\n"
                + "\n---\n".join(self.kb_snippets[:CHROMA_SYSTEM_ENRICH_TOP_K]),
            )
        return "\n\n".join(parts).strip()


def append_kb_to_system_context(base_appendix: str, kb_snippets: list[str]) -> str:
    enrichment = ChromaSystemEnrichment(kb_snippets=kb_snippets)
    kb_block = enrichment.to_system_appendix(include_kb=True)
    if not kb_block:
        return base_appendix
    if not base_appendix.strip():
        return kb_block
    return f"{base_appendix.strip()}\n\n{kb_block}"


def merge_system_role(base_system: str, chroma_appendix: str | None) -> str:
    appendix = (chroma_appendix or "").strip()
    if not appendix:
        return base_system
    return (
        f"{base_system.rstrip()}\n\n"
        "--- Chroma HNSW context (informs your reasoning; you must still decide) ---\n"
        f"{appendix}"
    )


def _query_collection_docs(
    collection_name: str,
    description: str,
    question: str,
    *,
    top_k: int,
    where: dict[str, Any] | None = None,
) -> tuple[list[str], list[dict[str, Any]]]:
    client = get_http_client()
    try:
        collection = get_collection(client, collection_name)
    except Exception:
        collection = create_collection(client, collection_name, metadata={"description": description})
    if collection.count() == 0:
        return [], []
    vectors = embed_texts([question])
    kwargs: dict[str, Any] = {
        "query_embeddings": vectors,
        "n_results": min(top_k, max(collection.count(), 1)),
        "include": ["documents", "metadatas", "distances"],
    }
    if where:
        kwargs["where"] = where
    result = collection.query(**kwargs)
    docs = [str(d) for d in (result.get("documents") or [[]])[0] if d]
    metas = list((result.get("metadatas") or [[]])[0])
    return docs, metas


def fetch_chroma_system_enrichment(
    user_id: str,
    session_id: str,
    question: str,
) -> ChromaSystemEnrichment:
    print(
        "--- CHROMA HNSW SYSTEM ENRICH (hints only → LLM classify/plan always follows) ---",
        flush=True,
    )
    bare = strip_ui_region(question)
    enrichment = ChromaSystemEnrichment()

    where: dict[str, Any] | None = None
    if user_id:
        clauses: list[dict[str, Any]] = [{"user_id": {"$eq": user_id}}]
        if session_id:
            clauses.append({"session_id": {"$eq": session_id}})
        where = {"$and": clauses} if len(clauses) > 1 else clauses[0]

    role_docs, role_metas = _query_collection_docs(
        CHROMA_AGENT_ROLES_COLLECTION,
        "Agent system-role hints from prior successful turns",
        bare,
        top_k=CHROMA_SYSTEM_ENRICH_TOP_K,
        where=where,
    )
    for doc, meta in zip(role_docs, role_metas, strict=False):
        intent = (meta or {}).get("intent") or "?"
        enrichment.role_hints.append(f"[intent={intent}] {doc[:320]}")

    # Session dialogue is fed as user/assistant/tool summary messages (see chat_summary.py),
    # not duplicated here in the system prompt.

    print(
        f"--- CHROMA enrich roles={len(enrichment.role_hints)} "
        f"(session history via role-summary messages; KB via retrieve→rerank) ---",
        flush=True,
    )
    return enrichment


def persist_agent_role_hint(
    user_id: str,
    session_id: str,
    question: str,
    intent: str,
    plan: dict[str, Any],
    answer_summary: str,
) -> None:
    """Upsert a compact hint into Chroma for future system-role enrichment (HNSW)."""
    if not SESSION_MEMORY_ENABLED:
        return
    bare = strip_ui_region(question)
    fp = question_fingerprint(question)
    doc = (
        f"Similar user asks: {bare[:300]}\n"
        f"Successful intent: {intent}\n"
        f"Plan: {json.dumps(plan, default=str)[:800]}\n"
        f"Outcome summary: {answer_summary[:400]}"
    )[:4000]
    try:
        collection = _ensure_collection(
            CHROMA_AGENT_ROLES_COLLECTION,
            "Agent system-role hints from prior successful turns",
        )
        uid = user_id or "global"
        sid = session_id or "global"
        doc_id = _scoped_id(uid, sid, f"role-{fp}")
        collection.upsert(
            ids=[doc_id],
            documents=[doc],
            embeddings=embed_texts([doc]),
            metadatas=[
                {
                    "user_id": uid,
                    "session_id": sid,
                    "intent": intent,
                    "question_fp": fp,
                    "record_type": "system_role_hint",
                    "ts": int(time.time()),
                },
            ],
        )
        print(f"--- CHROMA upsert system_role_hint id={doc_id[:8]}... ---", flush=True)
    except Exception:
        pass
