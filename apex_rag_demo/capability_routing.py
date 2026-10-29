"""Capability routing: embed natural-language API affordances (Cursor-style), not regex lists.

Capabilities are loaded from data/capability_statements.json and CRUD_CATALOG summaries.
When OpenAPI/KB sync adds new operations, extend the JSON or regenerate from swagger — no new
Python regex per phrase.
"""

from __future__ import annotations

import json
from functools import lru_cache
from typing import Any

from apex_rag_demo.config import DATA_DIR
from apex_rag_demo.crud_policy import WriteKind, write_kind_for_intent
from apex_rag_demo.crud_registry import CRUD_CATALOG
from apex_rag_demo.planning import INTENTS
from apex_rag_demo.response_formatters import strip_ui_region

CAPABILITY_STATEMENTS_PATH = DATA_DIR / "capability_statements.json"

# Tunables (env optional later)
CAPABILITY_MIN_SCORE = 0.40
CAPABILITY_CORRECT_MARGIN = 0.05


@lru_cache(maxsize=1)
def _capability_rows() -> list[tuple[str, str, list[float]]]:
    """(legacy_intent, phrase, embedding vector)."""
    from apex_rag_demo.dynamic_tools import dynamic_tools_enabled, load_dynamic_tool_catalog
    from apex_rag_demo.rag.embeddings import embed_texts_inprocess

    phrases: list[str] = []
    intents: list[str] = []

    if dynamic_tools_enabled():
        for tool in load_dynamic_tool_catalog().values():
            intents.append(tool.legacy_intent)
            phrases.append(tool.description())

    if CAPABILITY_STATEMENTS_PATH.is_file():
        raw = json.loads(CAPABILITY_STATEMENTS_PATH.read_text(encoding="utf-8"))
        if isinstance(raw, list):
            for block in raw:
                if not isinstance(block, dict):
                    continue
                intent = str(block.get("intent") or "").strip()
                if intent not in INTENTS:
                    continue
                for phrase in block.get("phrases") or []:
                    text = str(phrase).strip()
                    if text:
                        intents.append(intent)
                        phrases.append(text)

    for entry in CRUD_CATALOG:
        if entry.intent not in INTENTS:
            continue
        line = f"{entry.summary}. HTTP {entry.http} ({entry.domain} API)."
        intents.append(entry.intent)
        phrases.append(line)

    openapi_path = DATA_DIR / "kb_openapi.json"
    if openapi_path.is_file():
        try:
            chunks = json.loads(openapi_path.read_text(encoding="utf-8"))
            if isinstance(chunks, list):
                for ch in chunks[:120]:
                    if not isinstance(ch, dict):
                        continue
                    text = str(ch.get("text") or "")[:400]
                    if not text:
                        continue
                    intent = _intent_from_openapi_text(text)
                    if intent:
                        intents.append(intent)
                        phrases.append(text)
        except (json.JSONDecodeError, OSError):
            pass

    if not phrases:
        return []

    vectors = embed_texts_inprocess(phrases, log_call=False)
    return list(zip(intents, phrases, vectors, strict=True))


def _intent_from_openapi_text(text: str) -> str | None:
    lower = text.lower()
    if "/v1/orders" in lower and "customer" not in lower:
        return "search_orders"
    if "/v1/customers" in lower:
        return "search_customers"
    if "/client-venues" in lower or "client venue" in lower:
        return "list_client_venues"
    if "/v1/events/suggest" in lower or "suggest" in lower and "search" in lower:
        return "search_events"
    if "marketing" in lower and "/v1/events" in lower:
        return "marketing_events"
    if "/events/" in lower and "inventory" in lower:
        return "inventory_zones"
    if "/v1/inventory/contexts/" in lower and "report" in lower:
        return "reports_inventory_event"
    if "/v1/sales/" in lower or "/ticketlifecycle/" in lower or "/ticketintransfer/" in lower:
        return "b2b_flash_report"
    if "/timezones/timezones" in lower:
        return "reports_timezones"
    if "get /events" in lower or "events-api" in lower:
        return "get_event"
    return None


def _cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return -1.0
    return sum(x * y for x, y in zip(a, b, strict=True))


def capability_intent_scores(question: str) -> dict[str, float]:
    bare = strip_ui_region(question).strip()
    if len(bare) < 3:
        return {}
    rows = _capability_rows()
    if not rows:
        return {}
    from apex_rag_demo.semantic_message import embed_pooled_message

    q_vec = embed_pooled_message(bare)
    if not q_vec:
        return {}
    scored: dict[str, float] = {}
    for intent, _phrase, vec in rows:
        score = _cosine(q_vec, vec)
        scored[intent] = max(scored.get(intent, -1.0), score)
    return scored


def resolve_capability_intent(question: str) -> str | None:
    from apex_rag_demo.dynamic_tools import dynamic_tools_enabled, legacy_intent_for_tool_id, resolve_dynamic_tool_id

    if dynamic_tools_enabled():
        tool_id = resolve_dynamic_tool_id(question)
        if tool_id:
            legacy = legacy_intent_for_tool_id(tool_id)
            if legacy:
                return legacy

    scored = capability_intent_scores(question)
    if not scored:
        return None
    ranked = sorted(scored.items(), key=lambda item: item[1], reverse=True)
    top_intent, top_score = ranked[0]
    second = ranked[1][1] if len(ranked) > 1 else -1.0
    if top_score < CAPABILITY_MIN_SCORE:
        return None
    if top_score - second < CAPABILITY_CORRECT_MARGIN:
        return None
    return top_intent


def capability_correct_read_intent(proposed: str, question: str) -> str:
    """Prefer best-matching READ capability when LLM/regex chose a poor fit."""
    if write_kind_for_intent(proposed) != WriteKind.READ:
        return proposed
    resolved = resolve_capability_intent(question)
    if not resolved or resolved == proposed:
        return proposed
    if write_kind_for_intent(resolved) != WriteKind.READ:
        return proposed
    scores = capability_intent_scores(question)
    if scores.get(resolved, 0) - scores.get(proposed, 0) < CAPABILITY_CORRECT_MARGIN:
        return proposed
    print(
        f"--- CAPABILITY ROUTING correct {proposed} → {resolved} "
        f"(Δ={scores.get(resolved, 0) - scores.get(proposed, 0):.2f}) ---",
        flush=True,
    )
    return resolved


def enrich_read_plan_from_question(intent: str, plan: dict[str, Any], question: str) -> dict[str, Any]:
    """Generic plan hints from natural language (page size, etc.) — not per-intent regex."""
    from apex_rag_demo.order_intent_helpers import parse_result_limit

    out = dict(plan or {})
    limit = parse_result_limit(question)
    if limit is not None:
        out["pageSize"] = limit
    return out


def capability_routing_status() -> dict[str, Any]:
    from apex_rag_demo.dynamic_tools import dynamic_tools_status

    rows = _capability_rows()
    intents = {r[0] for r in rows}
    return {
        "enabled": bool(rows),
        "dynamic_tools": dynamic_tools_status(),
        "embedding_phrases": len(rows),
        "legacy_intents_covered": sorted(intents),
        "statements_file": str(CAPABILITY_STATEMENTS_PATH),
    }
