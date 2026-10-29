"""Deterministic prompts when API calls need an event UUID (agentic, not generative)."""

from __future__ import annotations

from apex_rag_demo.crud_policy import WriteKind, write_kind_for_intent
from apex_rag_demo.inventory_assessment import looks_like_price_code_setup_question
from apex_rag_demo.planning import _UUID_RE, _extract_event_id
from apex_rag_demo.response_formatters import strip_ui_region

_INTENTS_REQUIRING_EVENT_ID = frozenset(
    {
        "get_event",
        "inventory_zones",
        "update_event",
        "publish_event",
        "delete_event",
        "list_marketing_pixels",
        "create_marketing_pixel",
        "reset_inventory_publish",
        "update_inventory_ticket_types",
        "update_inventory_ga_manifest",
    },
)


def resolve_event_id(
    question: str,
    plan: dict | None,
    session_focus: dict | None,
) -> str:
    plan = plan or {}
    focus = session_focus or {}
    return (
        str(plan.get("eventId") or "").strip()
        or str(focus.get("eventId") or "").strip()
        or (_extract_event_id(question) or "")
    )


def clarify_missing_event_id(
    intent: str,
    question: str,
    *,
    action_plan: dict | None = None,
    session_focus: dict | None = None,
) -> str | None:
    bare = strip_ui_region(question)
    from apex_rag_demo.agentic_event import looks_like_any_event_inventory_demo

    if looks_like_any_event_inventory_demo(question):
        return None
    if looks_like_price_code_setup_question(bare):
        if resolve_event_id(question, action_plan, session_focus):
            return None
        return (
            "I need an **event UUID** to load price codes from inventory (live get_event + inventory).\n\n"
            "Example: `price codes for event 8f0a2f5c-9f45-4a7e-93f2-2f6a3f1f2b10`.\n\n"
            "List events first, or paste the Event ID from a prior table."
        )

    if intent not in _INTENTS_REQUIRING_EVENT_ID:
        return None
    if resolve_event_id(question, action_plan, session_focus):
        return None

    return (
        "I need an **event UUID** to call the live API for that request.\n\n"
        "Example: `get event 8f0a2f5c-9f45-4a7e-93f2-2f6a3f1f2b10` or "
        "`show price codes for event <uuid>`.\n\n"
        "You can copy an Event ID from a prior events table in this chat, or list events first."
    )


def guard_intent_needs_event_id(intent: str, question: str, session_focus: dict | None) -> str:
    """Adjust intent before API orchestration (price codes → get_event when id present)."""
    bare = strip_ui_region(question)
    eid = resolve_event_id(question, {}, session_focus)
    if looks_like_price_code_setup_question(bare) and eid:
        return "get_event"
    return intent
