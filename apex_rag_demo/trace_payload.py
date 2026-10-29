"""Pick the best api_trace step for display when the orchestrator overwrote api_payload."""

from __future__ import annotations

from typing import Any

from apex_rag_demo.agentic_event import looks_like_seat_inventory_demo
from apex_rag_demo.id_prompts import resolve_event_id
from apex_rag_demo.response_formatters import strip_ui_region

_GOOD_EVENT_RESOLUTIONS = frozenset({"events_get", "events_get_via_search"})


def find_best_get_event_from_trace(
    trace: list[dict[str, Any]] | None,
    *,
    event_id: str | None = None,
    need_inventory: bool = False,
) -> tuple[dict[str, Any], dict[str, Any]] | None:
    """Return (plan, payload) from the best get_event trace step."""
    if not trace:
        return None
    best: tuple[dict[str, Any], dict[str, Any]] | None = None
    for step in trace:
        if step.get("intent") != "get_event":
            continue
        plan = step.get("plan") if isinstance(step.get("plan"), dict) else {}
        eid = str(plan.get("eventId") or "").strip()
        if event_id and eid and eid != event_id:
            continue
        payload = step.get("payload")
        if not isinstance(payload, dict):
            continue
        if str(payload.get("_resolution") or "") not in _GOOD_EVENT_RESOLUTIONS:
            continue
        if need_inventory and not payload.get("_inventory"):
            continue
        best = (plan, payload)
        if need_inventory and payload.get("_inventory"):
            return best
    return best


def enrich_state_from_best_trace(state: dict[str, Any]) -> dict[str, Any]:
    """If trace has a stronger get_event payload than state.api_payload, restore it for UI/formatters."""
    trace = state.get("api_trace")
    if not isinstance(trace, list) or not trace:
        return state
    bare = strip_ui_region(state.get("question") or "")
    eid = resolve_event_id(state.get("question") or "", state.get("action_plan") or {}, state.get("session_focus"))
    need_inv = looks_like_seat_inventory_demo(bare)
    hit = find_best_get_event_from_trace(trace, event_id=eid, need_inventory=need_inv)
    if not hit and need_inv and eid:
        hit = find_best_get_event_from_trace(trace, event_id=eid, need_inventory=False)
    if not hit:
        return state
    plan, payload = hit
    current = state.get("api_payload")
    if isinstance(current, dict) and str(current.get("_resolution") or "") in _GOOD_EVENT_RESOLUTIONS:
        if not need_inv or current.get("_inventory"):
            return state
    return {
        **state,
        "intent": "get_event",
        "action_plan": plan,
        "api_payload": payload,
        "api_error": None,
    }
