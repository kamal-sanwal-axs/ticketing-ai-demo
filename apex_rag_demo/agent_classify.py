from __future__ import annotations

import json
import re
from typing import Any

from apex_rag_demo.clients.llama import chat_completion
from apex_rag_demo.config import CHAT_TEMPERATURE_ROUTING
from apex_rag_demo.intent_helpers import is_greeting
from apex_rag_demo.intent_semantic import is_conversational_message, reconcile_classified_intent
from apex_rag_demo.planning import INTENTS, _parse_json_object
from apex_rag_demo.response_formatters import strip_ui_region

_CLASSIFY_AGENT_SYSTEM = f"""You are the routing agent for the APEX ticketing assistant.
Choose exactly one API intent and whether internal KB documentation must be retrieved.

Return JSON only with keys:
- intent: one of {", ".join(INTENTS)}
- need_kb_retrieval: boolean — true only when the user needs product/help documentation
  (how something works, definitions, workflows). false for live API lookups (events, venues, users, mutations).

Mandatory: You are the only authority on intent. Chroma collections (agent_roles, session memory, KB excerpts)
in the system message are hints from prior turns — NEVER copy a hinted intent without validating the current user message.
Regex or catalog matchers do not run; your JSON is the routing decision.

Session context below is hints only — always decide from the current user message.
Prior turns in the message list (user / assistant / tool) are the live chat history for this tab; use them for follow-ups like "publish it" or "same filter".

Rules:
- Client venues registry ≠ ticketed events list (marketing_events / search_events).
- get_event requires an event UUID unless session focus supplies eventId for a clear follow-up.
- Date-based event lists (e.g. after this month) → marketing_events.
- show me events / list events / all events (no event UUID) → marketing_events, not explain or get_event.
- create_event ONLY when the user explicitly asks to create/add/schedule a NEW event — never for show/list/all events.
- publish / publish event / publish AINV-#### / publish with event UUID → publish_event (need_kb_retrieval false).
- Weather/jokes → explain with need_kb_retrieval false unless they ask how APEX works.
- buy/purchase/book a seat or ticket for a fan → explain (fan checkout is not a live API in this assistant; need_kb_retrieval false).
- search/find orders, order number, customer email on orders → search_orders (search-api POST /v1/orders).
- order payment statuses → search_order_payment_statuses.
- search/find customers, fan email, account lookup → search_customers.
- best available on an event → inventory_zones; best available for a customer name → search_customers first.
- show/list fans or customers → search_customers; fan buy/purchase seat → explain (no live checkout).
- published/on-sale events plus price codes, ticket types, seats sold, or seat-level inventory → marketing_events (orchestrator chains get_event+inventory)."""


def _session_context_block(
    session_focus: dict[str, Any] | None,
    session_snippets: list[str] | None,
    *,
    topic_shift: bool = False,
) -> str:
    if topic_shift:
        return (
            "Session context: (suppressed — current message is a new topic per "
            "sentence-transformer analysis; do not use prior intents or API errors.)"
        )
    lines: list[str] = []
    focus = session_focus or {}
    if focus:
        lines.append(f"Session focus: {json.dumps(focus, default=str)[:800]}")
    snippets = session_snippets or []
    if snippets:
        lines.append("Similar past turns (non-binding):")
        for i, snip in enumerate(snippets[:3], start=1):
            lines.append(f"{i}. {str(snip)[:400]}")
    if not lines:
        return "Session context: (none)"
    return "\n".join(lines)


def classify_with_routing(
    question: str,
    *,
    session_focus: dict[str, Any] | None = None,
    session_snippets: list[str] | None = None,
    chroma_system_context: str | None = None,
    semantic_context_block: str | None = None,
    topic_shift: bool = False,
    chat_history: list[dict[str, Any]] | None = None,
) -> tuple[str, bool]:
    """LLM-only intent + whether to run KB vector retrieval (never heuristic routing)."""
    bare = strip_ui_region(question)
    from apex_rag_demo.compound_request import is_compound_operational_request

    if is_compound_operational_request(question):
        print("--- AGENT CLASSIFY compound operational → marketing_events (no LLM) ---", flush=True)
        return "marketing_events", False

    from apex_rag_demo.rag.intent_chroma import resolve_pre_llm_routing

    pre_llm = resolve_pre_llm_routing(question)
    if pre_llm and pre_llm.skip_llm_classify and pre_llm.intent != "explain":
        print(f"--- AGENT CLASSIFY semantic/Chroma → {pre_llm.intent} (no LLM) ---", flush=True)
        return pre_llm.intent, False
    if is_greeting(bare) or is_conversational_message(question):
        print("--- AGENT CLASSIFY conversational → explain (no LLM) ---", flush=True)
        return "explain", False
    from apex_rag_demo.fan_purchase import looks_like_fan_purchase_request

    if looks_like_fan_purchase_request(bare):
        print("--- AGENT CLASSIFY fan purchase → explain (MFE guidance, no LLM) ---", flush=True)
        return "explain", False
    user = (
        f"{_session_context_block(session_focus, session_snippets, topic_shift=topic_shift)}\n\n"
        f"User message:\n{bare}"
    )
    print("--- AGENT CLASSIFY (LLM) ---", flush=True)
    raw = chat_completion(
        _CLASSIFY_AGENT_SYSTEM,
        user,
        temperature=CHAT_TEMPERATURE_ROUTING,
        chroma_system_context=chroma_system_context,
        semantic_turn_context=semantic_context_block,
        history=chat_history,
        routing=True,
    ).strip()
    intent = "explain"
    need_kb = False
    try:
        data = _parse_json_object(raw)
        intent = str(data.get("intent") or "explain").strip().lower()
        need_kb = bool(data.get("need_kb_retrieval"))
    except (json.JSONDecodeError, TypeError, ValueError):
        lowered = raw.lower()
        for candidate in INTENTS:
            if candidate in lowered:
                intent = candidate
                break
        need_kb = "need_kb_retrieval" in lowered and "true" in lowered

    if intent not in INTENTS:
        intent = "explain"
    intent = reconcile_classified_intent(intent, question)
    if intent != "explain" and need_kb:
        need_kb = False
    if intent == "explain" and not need_kb and re.search(
        r"\b(how|what is|help|explain|documentation|workflow)\b",
        bare,
        re.I,
    ):
        need_kb = True
    print(f"--- AGENT CLASSIFY result intent={intent} need_kb={need_kb} ---", flush=True)
    return intent, need_kb


def classify_intent(
    question: str,
    *,
    session_focus: dict[str, Any] | None = None,
    session_snippets: list[str] | None = None,
    chat_history: list[dict[str, Any]] | None = None,
) -> str:
    intent, _ = classify_with_routing(
        question,
        session_focus=session_focus,
        session_snippets=session_snippets,
        chat_history=chat_history,
    )
    return intent
