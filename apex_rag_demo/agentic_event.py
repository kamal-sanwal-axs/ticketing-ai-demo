"""Agentic follow-ups: run live APIs instead of prompting for rephrases."""

from __future__ import annotations

import re
from typing import Any

from apex_rag_demo.event_list import iter_event_dicts
from apex_rag_demo.event_query_helpers import (
    get_event_enrichment_flags,
    looks_like_event_inventory_followup,
)
from apex_rag_demo.id_prompts import resolve_event_id
from apex_rag_demo.inventory_assessment import looks_like_price_code_setup_question
from apex_rag_demo.planning import plan_for_intent
from apex_rag_demo.response_formatters import strip_ui_region

_EVENT_DETAIL_RE = re.compile(
    r"("
    r"\bvenue\s+details?\b|"
    r"\bevent\s+details?\b|"
    r"\bdetails?\s+for\b.*\bevent\b|"
    r"\bget\b.*\b(event|venue)\b"
    r")",
    re.I,
)

_ANY_EVENT_RE = re.compile(
    r"\b(any|some|an?\s+example|a\s+sample)\b.*\bevents?\b|\bevents?\b.*\b(any|example|sample)\b",
    re.I,
)

_SEAT_INVENTORY_RE = re.compile(
    r"("
    r"\bprice\s*codes?\b|\bticket\s+types?\b|"
    r"\bsections?\b|\bprice\s+levels?\b|"
    r"\bseat[- ]lev\w*\b|\binventory\b|\bzones?\b"
    r")",
    re.I,
)


def looks_like_seat_inventory_demo(question: str) -> bool:
    """Price codes / ticket types / sections — with or without a specific event id."""
    bare = strip_ui_region(question)
    return bool(
        _SEAT_INVENTORY_RE.search(bare)
        or looks_like_event_inventory_followup(bare)
        or looks_like_price_code_setup_question(bare)
    )


def looks_like_any_event_inventory_demo(question: str) -> bool:
    bare = strip_ui_region(question)
    if not looks_like_seat_inventory_demo(bare):
        return False
    if resolve_event_id(bare, {}, None):
        return False
    return bool(_ANY_EVENT_RE.search(bare) or re.search(r"\buse\b.*\bevent", bare, re.I))


def looks_like_event_or_venue_detail_with_id(question: str) -> bool:
    bare = strip_ui_region(question)
    return bool(_EVENT_DETAIL_RE.search(bare) and resolve_event_id(bare, {}, None))


def _trace_has_intent(trace: list[dict[str, Any]], intent: str) -> bool:
    return any(step.get("intent") == intent for step in trace)


def _first_event_id_from_payload(payload: dict[str, Any] | None) -> str | None:
    if not payload:
        return None
    for ev in iter_event_dicts(payload):
        eid = str(ev.get("id") or ev.get("eventId") or "").strip()
        if eid and eid != "—":
            return eid
    for key in ("search", "suggest"):
        block = payload.get(key)
        if isinstance(block, dict):
            found = _first_event_id_from_payload(block)
            if found:
                return found
    return None


def _fetched_event_ids(trace: list[dict[str, Any]]) -> set[str]:
    out: set[str] = set()
    for step in trace:
        if step.get("intent") != "get_event":
            continue
        plan = step.get("plan") if isinstance(step.get("plan"), dict) else {}
        eid = str(plan.get("eventId") or "").strip()
        if eid:
            out.add(eid)
    return out


def try_agentic_orchestrator_step(
    question: str,
    *,
    api_trace: list[dict[str, Any]] | None,
    session_focus: dict[str, Any] | None,
    chroma_system_context: str | None = None,
    semantic_context_block: str | None = None,
    chat_history: list[dict[str, Any]] | None = None,
) -> dict[str, Any] | None:
    """Run catalog → event+inventory, or recover from failed id lookup via search/marketing."""
    from apex_rag_demo.reports_intent_helpers import looks_like_b2b_reports_question

    if looks_like_b2b_reports_question(question) and not api_trace:
        return None

    from apex_rag_demo.compound_request import (
        _event_ids_from_marketing_payload,
        try_compound_orchestrator_step,
    )

    compound = try_compound_orchestrator_step(
        question,
        api_trace=api_trace,
        session_focus=session_focus,
        chroma_system_context=chroma_system_context,
        semantic_context_block=semantic_context_block,
        chat_history=chat_history,
    )
    if compound:
        return compound

    bare = strip_ui_region(question)
    trace = list(api_trace or [])
    eid = resolve_event_id(question, {}, session_focus)

    # Open-ended: "use any event to show price codes…"
    if looks_like_any_event_inventory_demo(question) and not trace:
        plan = plan_for_intent(
            "marketing_events",
            question,
            session_focus,
            chroma_system_context=chroma_system_context,
            semantic_context_block=semantic_context_block,
            chat_history=chat_history,
        )
        plan["_compound"] = True
        plan["_agentic"] = True
        print("--- ORCHESTRATOR agentic: list events then inventory (any event) ---", flush=True)
        return {
            "orchestrator_action": "call_api",
            "intent": "marketing_events",
            "action_plan": plan,
            "orchestrator_reason": "agentic_any_event_inventory",
        }

    # Explicit uuid: venue/event details or inventory phrasing
    if eid and looks_like_seat_inventory_demo(bare) and not _trace_has_intent(trace, "get_event"):
        flags = get_event_enrichment_flags(bare)
        flags.setdefault("includeInventory", True)
        flags.setdefault("includeTicketTypes", True)
        print(f"--- ORCHESTRATOR agentic: get_event+inventory {eid[:8]}… ---", flush=True)
        return {
            "orchestrator_action": "call_api",
            "intent": "get_event",
            "action_plan": {"eventId": eid, **flags, "_agentic": True},
            "orchestrator_reason": "agentic_event_inventory",
        }

    if eid and looks_like_event_or_venue_detail_with_id(bare) and not _trace_has_intent(trace, "get_event"):
        from apex_rag_demo.reports_intent_helpers import looks_like_b2b_reports_question

        if looks_like_b2b_reports_question(bare):
            return None
        flags = get_event_enrichment_flags(bare)
        print(f"--- ORCHESTRATOR agentic: get_event {eid[:8]}… ---", flush=True)
        return {
            "orchestrator_action": "call_api",
            "intent": "get_event",
            "action_plan": {"eventId": eid, **flags, "_agentic": True},
            "orchestrator_reason": "agentic_event_detail",
        }

    if not trace:
        return None

    last = trace[-1]
    if last.get("intent") != "get_event":
        return None
    payload = last.get("payload") if isinstance(last.get("payload"), dict) else {}
    resolution = str(payload.get("_resolution") or "")

    if resolution == "not_found" and not _trace_has_intent(trace, "marketing_events"):
        plan = plan_for_intent(
            "marketing_events",
            question,
            session_focus,
            chroma_system_context=chroma_system_context,
            semantic_context_block=semantic_context_block,
            chat_history=chat_history,
        )
        plan["pageSize"] = min(int(plan.get("pageSize") or 10), 5)
        plan["_agentic"] = True
        plan["_compound"] = True
        print("--- ORCHESTRATOR agentic recovery: marketing list after 404 ---", flush=True)
        return {
            "orchestrator_action": "call_api",
            "intent": "marketing_events",
            "action_plan": plan,
            "orchestrator_reason": "agentic_recovery_marketing_after_404",
        }

    if resolution in ("search_events_only", "search_suggest", "client_venue_context"):
        alt_id = _first_event_id_from_payload(payload)
        fetched = _fetched_event_ids(trace)
        if alt_id and alt_id not in fetched:
            flags = get_event_enrichment_flags(bare)
            flags.setdefault("includeInventory", looks_like_seat_inventory_demo(bare))
            flags.setdefault("includeTicketTypes", True)
            print(f"--- ORCHESTRATOR agentic recovery: get_event {alt_id[:8]}… from search ---", flush=True)
            return {
                "orchestrator_action": "call_api",
                "intent": "get_event",
                "action_plan": {
                    "eventId": alt_id,
                    **flags,
                    "_agentic": True,
                    "_recovered_from": resolution,
                },
                "orchestrator_reason": "agentic_recovery_search_hit",
            }

    if _trace_has_intent(trace, "marketing_events") and looks_like_seat_inventory_demo(bare):
        marketing_steps = [s for s in trace if s.get("intent") == "marketing_events"]
        last_list = marketing_steps[-1].get("payload") if marketing_steps else None
        fetched = _fetched_event_ids(trace)
        for candidate in _event_ids_from_marketing_payload(
            last_list if isinstance(last_list, dict) else None,
        ):
            if candidate in fetched:
                continue
            print(f"--- ORCHESTRATOR agentic: inventory for {candidate[:8]}… ---", flush=True)
            return {
                "orchestrator_action": "call_api",
                "intent": "get_event",
                "action_plan": {
                    "eventId": candidate,
                    "includeInventory": True,
                    "includeTicketTypes": True,
                    "_agentic": True,
                    "_compound": True,
                },
                "orchestrator_reason": "agentic_marketing_pick_event",
            }

    return None
