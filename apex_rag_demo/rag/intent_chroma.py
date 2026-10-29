"""Chroma HNSW index of operator prompts → intents (visible before LLM classify)."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from apex_rag_demo.config import (
    CHROMA_INTENT_ROUTE_MIN_SCORE,
    CHROMA_INTENT_ROUTE_TOP_K,
    CHROMA_INTENT_ROUTES_COLLECTION,
    DATA_DIR,
)
from apex_rag_demo.planning import INTENTS
from apex_rag_demo.rag.chroma_client import create_collection, get_collection, get_http_client
from apex_rag_demo.rag.chroma_metrics import distance_to_similarity
from apex_rag_demo.rag.embeddings import embed_texts
from apex_rag_demo.response_formatters import strip_ui_region


@dataclass(frozen=True)
class IntentRouteHit:
    intent: str
    score: float
    prompt: str
    source: str
    compound: bool = False


@dataclass(frozen=True)
class PreLlmRouting:
    intent: str
    score: float
    label: str
    skip_llm_classify: bool
    hits: tuple[IntentRouteHit, ...]
    compound: bool


def _intent_route_rows() -> list[dict[str, Any]]:
    """Harness + in-process exemplars for Chroma (operator prompts only)."""
    rows: list[dict[str, Any]] = []
    harness_path = DATA_DIR / "ai_harness_prompts.json"
    if harness_path.is_file():
        for item in json.loads(harness_path.read_text(encoding="utf-8")):
            prompt = str(item.get("prompt") or "").strip()
            intent = str(item.get("expected_intent") or "").strip()
            if prompt and intent in INTENTS:
                rows.append(
                    {
                        "id": f"harness-{item.get('id', len(rows))}",
                        "prompt": prompt,
                        "intent": intent,
                        "source": "harness",
                        "compound": bool(item.get("note") and "chains" in str(item.get("note"))),
                    },
                )

    from apex_rag_demo.intent_semantic import _INTENT_EXEMPLARS

    for intent, phrases in _INTENT_EXEMPLARS.items():
        if intent not in INTENTS:
            continue
        for i, phrase in enumerate(phrases):
            rows.append(
                {
                    "id": f"exemplar-{intent}-{i}",
                    "prompt": phrase,
                    "intent": intent,
                    "source": "exemplar",
                    "compound": False,
                },
            )

    compound_prompts = [
        (
            "show published events with seat sold price codes ticket types and seat level inventory",
            "marketing_events",
        ),
        (
            "list on sale events then show inventory price levels and ticket types per event",
            "marketing_events",
        ),
    ]
    for i, (prompt, intent) in enumerate(compound_prompts):
        rows.append(
            {
                "id": f"compound-{i}",
                "prompt": prompt,
                "intent": intent,
                "source": "compound",
                "compound": True,
            },
        )
    return rows


def sync_intent_routes_collection() -> int:
    """Upsert operator prompts into Chroma (run after harness / exemplar changes)."""
    rows = _intent_route_rows()
    if not rows:
        return 0
    client = get_http_client()
    try:
        collection = get_collection(client, CHROMA_INTENT_ROUTES_COLLECTION)
    except Exception:
        collection = create_collection(
            client,
            CHROMA_INTENT_ROUTES_COLLECTION,
            metadata={"description": "Operator prompt → intent (pre-LLM semantic routing)"},
        )

    ids = [str(r["id"]) for r in rows]
    documents = [
        f"Operator prompt: {r['prompt']}\nIntent: {r['intent']}\nSource: {r['source']}"
        for r in rows
    ]
    metadatas = [
        {
            "intent": r["intent"],
            "source": r["source"],
            "compound": bool(r.get("compound")),
            "prompt": r["prompt"][:500],
            "ts": int(time.time()),
        }
        for r in rows
    ]
    collection.upsert(
        ids=ids,
        documents=documents,
        embeddings=embed_texts(documents),
        metadatas=metadatas,
    )
    print(f"--- CHROMA intent routes synced: {len(ids)} docs ---", flush=True)
    return len(ids)


@lru_cache(maxsize=1)
def _ensure_routes_synced() -> bool:
    try:
        client = get_http_client()
        try:
            collection = get_collection(client, CHROMA_INTENT_ROUTES_COLLECTION)
        except Exception:
            sync_intent_routes_collection()
            return True
        if collection.count() == 0:
            sync_intent_routes_collection()
        return True
    except Exception as exc:
        print(f"--- CHROMA intent routes unavailable: {exc} ---", flush=True)
        return False


def query_intent_routes(question: str, *, top_k: int | None = None) -> list[IntentRouteHit]:
    bare = strip_ui_region(question).strip()
    if len(bare) < 4:
        return []
    if not _ensure_routes_synced():
        return []
    k = top_k or CHROMA_INTENT_ROUTE_TOP_K
    try:
        client = get_http_client()
        collection = get_collection(client, CHROMA_INTENT_ROUTES_COLLECTION)
        if collection.count() == 0:
            return []
        from apex_rag_demo.semantic_message import embed_pooled_message

        pooled = embed_pooled_message(bare)
        query_vec = pooled if pooled else embed_texts([bare])[0]
        result = collection.query(
            query_embeddings=[query_vec],
            n_results=min(k, collection.count()),
            include=["documents", "metadatas", "distances"],
        )
        docs = (result.get("documents") or [[]])[0]
        metas = (result.get("metadatas") or [[]])[0]
        dists = (result.get("distances") or [[]])[0]
        hits: list[IntentRouteHit] = []
        for doc, meta, dist in zip(docs, metas, dists, strict=False):
            if not meta:
                continue
            intent = str(meta.get("intent") or "")
            if intent not in INTENTS:
                continue
            score = distance_to_similarity(float(dist or 1.0))
            hits.append(
                IntentRouteHit(
                    intent=intent,
                    score=score,
                    prompt=str(meta.get("prompt") or doc or "")[:200],
                    source=str(meta.get("source") or "chroma"),
                    compound=bool(meta.get("compound")),
                ),
            )
        hits.sort(key=lambda h: h.score, reverse=True)
        return hits
    except Exception as exc:
        print(f"--- CHROMA intent route query failed: {exc} ---", flush=True)
        return []


def resolve_pre_llm_routing(question: str) -> PreLlmRouting | None:
    """Combine Chroma + compound rules + local embeddings; may skip LLM classify."""
    from apex_rag_demo.compound_request import is_compound_operational_request
    from apex_rag_demo.intent_semantic import semantic_intent_hint, semantic_intent_scores
    from apex_rag_demo.config import INTENT_SEMANTIC_MIN_SCORE

    compound = is_compound_operational_request(question)
    if compound:
        label = "Semantic (pre-LLM): compound → marketing_events + inventory chain"
        return PreLlmRouting(
            intent="marketing_events",
            score=1.0,
            label=label,
            skip_llm_classify=True,
            hits=(),
            compound=True,
        )

    chroma_hits = query_intent_routes(question)
    embed_hint = semantic_intent_hint(question)
    scores = semantic_intent_scores(question)
    embed_score = max(scores.values()) if scores else 0.0

    best_chroma = chroma_hits[0] if chroma_hits else None
    chosen_intent = "explain"
    chosen_score = 0.0
    skip = False

    if best_chroma and best_chroma.score >= CHROMA_INTENT_ROUTE_MIN_SCORE:
        chosen_intent = best_chroma.intent
        chosen_score = best_chroma.score
        if embed_hint == chosen_intent and embed_score >= INTENT_SEMANTIC_MIN_SCORE:
            skip = True
        elif best_chroma.score >= CHROMA_INTENT_ROUTE_MIN_SCORE + 0.08:
            skip = True
    elif embed_hint and embed_score >= INTENT_SEMANTIC_MIN_SCORE:
        chosen_intent = embed_hint
        chosen_score = embed_score
        skip = chosen_intent != "explain"

    if chosen_intent == "explain" and not skip:
        return None

    chroma_part = (
        f"Chroma≈{best_chroma.intent} ({best_chroma.score:.2f})"
        if best_chroma
        else "Chroma—"
    )
    embed_part = f"embed≈{embed_hint or '—'} ({embed_score:.2f})"
    label = f"Semantic route (pre-LLM): {chosen_intent.replace('_', ' ')} · {chroma_part} · {embed_part}"

    return PreLlmRouting(
        intent=chosen_intent,
        score=chosen_score,
        label=label,
        skip_llm_classify=skip and chosen_intent != "explain",
        hits=tuple(chroma_hits),
        compound=False,
    )


def format_progress_phase(routing: PreLlmRouting | None) -> str:
    """Encoded phase for SSE → human label in chat_handlers.phase_label."""
    if not routing:
        return "semantic_turn"
    return f"semantic_route|{routing.intent}|{routing.score:.2f}|{'compound' if routing.compound else 'chroma'}"
