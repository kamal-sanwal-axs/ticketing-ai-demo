from __future__ import annotations

import json
from typing import Any

from apex_rag_demo.clients.llama import chat_completion
from apex_rag_demo.config import CHAT_TEMPERATURE_ROUTING
from apex_rag_demo.crud_planners import plan_for_crud_intent
from apex_rag_demo.event_date_filters import plan_marketing_date_filter
from apex_rag_demo.event_query_helpers import get_event_enrichment_flags
from apex_rag_demo.planning import (
    INTENTS,
    _PLAN_ORG_SYSTEM,
    _PLAN_SEARCH_SYSTEM,
    _PLAN_VENUE_SYSTEM,
    _UUID_RE,
    _extract_admin_user_id,
    _extract_event_id,
    _extract_user_directory_search,
    _parse_json_object,
)
from apex_rag_demo.response_formatters import strip_ui_region

_PLAN_AGENT_SYSTEM = """You are the planning agent for APEX API calls.
Given the classified intent and user message, return JSON only — the request plan object for that intent.

Examples:
- search_events: {"query": "short search string"}
- marketing_events: may include dateFilter with startAfter/startBefore ISO dates and pageSize
- list_client_venues: {"pageSize": 25, "organizationIds": []}
- list_users: {"search": "", "limit": 50, "offset": 0}
- get_event: {"eventId": "uuid-or-empty", "includeInventory": false, ...}
- create_organization / create_client_venue: fields for admin POST bodies

Use session focus eventId when the user refers to "this event" without a UUID."""


def _crud_plan_intents() -> frozenset[str]:
    return frozenset(
        {
            "update_event",
            "delete_event",
            "create_event",
            "publish_event",
            "update_organization",
            "update_client_venue",
            "create_inventory_zone",
            "reset_inventory_publish",
            "update_inventory_ticket_types",
            "update_inventory_ga_manifest",
            "list_marketing_pixels",
            "create_marketing_pixel",
            "update_marketing_pixel",
            "delete_marketing_pixel",
        },
    )


def plan_for_intent_agentic(
    intent: str,
    question: str,
    session_focus: dict[str, Any] | None = None,
    *,
    chroma_system_context: str | None = None,
    semantic_context_block: str | None = None,
    chat_history: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """LLM planning step — no heuristic routing shortcuts."""
    focus = session_focus or {}
    bare = strip_ui_region(question)
    print(f"--- AGENT PLAN (LLM) intent={intent} ---", flush=True)

    if intent in _crud_plan_intents():
        return plan_for_crud_intent(intent, question, session_focus)

    if intent == "search_events":
        raw = chat_completion(
            _PLAN_SEARCH_SYSTEM,
            bare,
            temperature=CHAT_TEMPERATURE_ROUTING,
            chroma_system_context=chroma_system_context,
            semantic_turn_context=semantic_context_block,
            history=chat_history,
            routing=True,
        )
        try:
            data = _parse_json_object(raw)
            query = str(data.get("query", "")).strip()
        except json.JSONDecodeError:
            query = bare[:80]
        if len(query) < 2:
            query = bare[:80]
        return {"query": query}

    if intent == "create_organization":
        raw = chat_completion(
            _PLAN_ORG_SYSTEM,
            bare,
            temperature=CHAT_TEMPERATURE_ROUTING,
            chroma_system_context=chroma_system_context,
            semantic_turn_context=semantic_context_block,
            history=chat_history,
            routing=True,
        )
        try:
            return _parse_json_object(raw)
        except json.JSONDecodeError:
            return {"name": bare[:120] or "Demo Organization"}

    if intent == "create_client_venue":
        raw = chat_completion(
            _PLAN_VENUE_SYSTEM,
            bare,
            temperature=CHAT_TEMPERATURE_ROUTING,
            chroma_system_context=chroma_system_context,
            semantic_turn_context=semantic_context_block,
            history=chat_history,
            routing=True,
        )
        try:
            return _parse_json_object(raw)
        except json.JSONDecodeError:
            return {"name": bare[:120] or "Demo Client Venue"}

    if intent in ("search_orders", "search_order_payment_statuses", "search_customers"):
        from apex_rag_demo.order_intent_helpers import extract_search_keyword

        q = extract_search_keyword(question)
        return {"keyword": q, "searchValues": q}

    if intent == "marketing_events":
        return plan_marketing_date_filter(
            question,
            chroma_system_context=chroma_system_context,
            semantic_context_block=semantic_context_block,
            chat_history=chat_history,
        )

    if intent == "get_event":
        event_id = _extract_event_id(question) or str(focus.get("eventId") or "")
        flags = get_event_enrichment_flags(bare)
        return {"eventId": event_id, **flags}

    if intent == "inventory_zones":
        event_id = _extract_event_id(question) or str(focus.get("eventId") or "")
        return {"eventId": event_id}

    if intent in ("list_client_venues", "list_users", "explain") or intent not in INTENTS:
        focus_json = json.dumps(focus, default=str)[:600]
        user = f"Intent: {intent}\nSession focus: {focus_json}\n\nUser message:\n{bare}"
        raw = chat_completion(
            _PLAN_AGENT_SYSTEM,
            user,
            temperature=CHAT_TEMPERATURE_ROUTING,
            chroma_system_context=chroma_system_context,
            semantic_turn_context=semantic_context_block,
            history=chat_history,
            routing=True,
        )
        try:
            plan = _parse_json_object(raw)
            if isinstance(plan, dict):
                return plan
        except json.JSONDecodeError:
            pass

    if intent == "list_client_venues":
        org_ids = [m.group(0) for m in _UUID_RE.finditer(question)]
        return {"pageSize": 25, "organizationIds": org_ids[:5]}

    if intent == "list_users":
        from apex_rag_demo.config import RESOURCES_USERS_PAGE_SIZE

        return {
            "adminUserId": _extract_admin_user_id(question) or "",
            "search": _extract_user_directory_search(question) or "",
            "limit": RESOURCES_USERS_PAGE_SIZE,
            "offset": 0,
        }

    return {}
