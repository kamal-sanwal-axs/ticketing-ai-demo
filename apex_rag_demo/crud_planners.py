from __future__ import annotations

import re
from typing import Any

from apex_rag_demo.event_update import extract_update_event_name_plan

_UUID_RE = re.compile(
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}",
)


def _extract_event_id(question: str) -> str | None:
    match = _UUID_RE.search(question)
    return match.group(0) if match else None


def _all_uuids(question: str) -> list[str]:
    return [m.group(0) for m in _UUID_RE.finditer(question)]


def _tail_after_to(question: str) -> str | None:
    m = re.search(r"\bto\s+(.+)\s*$", question.strip(), re.I)
    return m.group(1).strip().strip("\"'") if m else None


def plan_for_crud_intent(
    intent: str,
    question: str,
    session_focus: dict[str, Any] | None = None,
) -> dict[str, Any]:
    focus = session_focus or {}
    if intent == "update_event":
        parsed = extract_update_event_name_plan(question)
        return parsed or {"eventId": _extract_event_id(question) or "", "headliners": ""}

    ids = _all_uuids(question)
    if intent == "delete_event":
        return {"eventId": ids[0] if ids else ""}
    if intent == "publish_event":
        from apex_rag_demo.publish_resolve import resolve_publish_event_id

        return resolve_publish_event_id(question, focus)
    if intent == "create_event":
        return {"headliners": _tail_after_to(question) or "New demo event", "clientVenueId": ids[0] if ids else None}
    if intent == "list_marketing_pixels":
        return {"eventId": ids[0] if ids else ""}
    if intent in ("create_marketing_pixel", "update_marketing_pixel"):
        return {"eventId": ids[0] if ids else "", "pixelId": ids[1] if len(ids) > 1 else ""}
    if intent == "delete_marketing_pixel":
        return {"eventId": ids[0] if ids else "", "pixelId": ids[1] if len(ids) > 1 else ""}
    if intent == "update_organization":
        return {"organizationId": ids[0] if ids else "", "name": _tail_after_to(question) or ""}
    if intent == "update_client_venue":
        return {"clientVenueId": ids[0] if ids else "", "name": _tail_after_to(question) or ""}
    if intent == "create_inventory_zone":
        return {"eventId": ids[0] if ids else "", "clientVenueId": ids[1] if len(ids) > 1 else ""}
    if intent in ("reset_inventory_publish", "update_inventory_ticket_types", "update_inventory_ga_manifest"):
        return {"zoneId": ids[0] if ids else "", "eventId": ids[0] if ids else ""}

    return {}
