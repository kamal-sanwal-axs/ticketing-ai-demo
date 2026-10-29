from __future__ import annotations

from typing import Any

import httpx

from apex_rag_demo.clients import apex_admin, apex_events, apex_inventory, apex_marketing
from apex_rag_demo.http_errors import build_mutation_error_payload, format_publish_event_failure
from apex_rag_demo.crud_consent import build_pending_confirmation
from apex_rag_demo.crud_policy import write_kind_for_intent, WriteKind
from apex_rag_demo.event_list import unwrap_event_payload
from apex_rag_demo.event_update import build_update_event_body_from_get


def _plans_match(stored: dict[str, Any], current: dict[str, Any]) -> bool:
    for key, value in (stored or {}).items():
        if current.get(key) != value:
            return False
    return True


def preview_mutation(intent: str, plan: dict[str, Any]) -> dict[str, Any]:
    lines: list[str] = []
    if intent == "update_event":
        eid = plan.get("eventId") or "?"
        lines.append(f"PUT /events/{eid}")
        lines.append(f"New headliners: {plan.get('headliners')}")
    elif intent == "delete_event":
        lines.append(f"DELETE /events/{plan.get('eventId') or '?'}")
    elif intent == "delete_marketing_pixel":
        lines.append(
            f"DELETE /marketing/v1/events/{plan.get('eventId')}/pixels/{plan.get('pixelId')}",
        )
    elif intent == "update_organization":
        lines.append(f"PATCH /admin/v1/organizations/{plan.get('organizationId')}")
        lines.append(f"name: {plan.get('name')}")
    elif intent == "update_client_venue":
        lines.append(f"PUT /admin/v1/client-venues/{plan.get('clientVenueId')}")
        lines.append(f"name: {plan.get('name')}")
    elif intent == "update_marketing_pixel":
        lines.append(
            f"PUT /marketing/v1/events/{plan.get('eventId')}/pixels/{plan.get('pixelId')}",
        )
    else:
        lines.append(f"{intent}: {plan}")
    return {"summary": "\n".join(lines), "plan": plan}


def execute_crud_intent(
    intent: str,
    plan: dict[str, Any],
    *,
    dry_run: bool,
    blocked_reason: str | None,
) -> tuple[dict[str, Any] | None, str | None]:
    if blocked_reason == "confirmation_required":
        return build_pending_confirmation(intent, plan, preview_mutation(intent, plan)), None
    if blocked_reason:
        return None, f"Mutation blocked: {blocked_reason}"

    kind = write_kind_for_intent(intent)

    try:
        if intent == "update_event":
            return _update_event(plan, dry_run=dry_run)
        if intent == "delete_event":
            return apex_events.delete_event(plan.get("eventId") or "", dry_run=dry_run), None
        if intent == "create_event":
            return apex_events.create_event(plan, dry_run=dry_run), None
        if intent == "publish_event":
            eid = str(plan.get("eventId") or "").strip()
            if not eid:
                detail = str(plan.get("_resolveError") or "Missing event UUID for publish.")
                return (
                    {
                        "_mutation_error": True,
                        "plan": plan,
                        "detail": detail,
                        "httpStatus": 0,
                    },
                    detail,
                )
            return apex_events.publish_event(eid, dry_run=dry_run), None
        if intent == "list_marketing_pixels":
            return apex_marketing.list_pixels(plan.get("eventId") or ""), None
        if intent == "create_marketing_pixel":
            return apex_marketing.create_pixel(plan.get("eventId") or "", plan, dry_run=dry_run), None
        if intent == "update_marketing_pixel":
            return apex_marketing.update_pixel(
                plan.get("eventId") or "",
                plan.get("pixelId") or "",
                plan,
                dry_run=dry_run,
            ), None
        if intent == "delete_marketing_pixel":
            return apex_marketing.delete_pixel(
                plan.get("eventId") or "",
                plan.get("pixelId") or "",
                dry_run=dry_run,
            ), None
        if intent == "update_organization":
            return apex_admin.patch_organization(
                plan.get("organizationId") or "",
                {"name": plan.get("name")},
                dry_run=dry_run,
            ), None
        if intent == "update_client_venue":
            return apex_admin.update_client_venue(
                plan.get("clientVenueId") or "",
                {"name": plan.get("name")},
                dry_run=dry_run,
            ), None
        if intent == "create_inventory_zone":
            return apex_inventory.create_zone(plan, dry_run=dry_run), None
        if intent == "reset_inventory_publish":
            zone_id = plan.get("zoneId") or ""
            if not zone_id and plan.get("eventId"):
                primary = apex_inventory.get_event_primary_zones(plan["eventId"])
                zone = (primary or {}).get("zone") or {}
                zone_id = str(zone.get("id") or "")
            return apex_inventory.reset_zone_publish(zone_id, dry_run=dry_run), None
        if intent in ("update_inventory_ticket_types", "update_inventory_ga_manifest"):
            return {
                "_note": "Pass a JSON body in a follow-up or use Inventory UI.",
                "intent": intent,
                "plan": plan,
                "endpoint": "inventory-api (POST)",
            }, None
    except httpx.HTTPStatusError as exc:
        snapshot = None
        eid = str(plan.get("eventId") or "")
        if intent == "publish_event" and eid:
            try:
                snapshot = apex_events.get_event(eid)
            except Exception:  # noqa: BLE001
                snapshot = None
        payload = build_mutation_error_payload(intent, plan, exc, event_snapshot=snapshot)
        if intent == "publish_event":
            return payload, format_publish_event_failure(payload, str(exc))
        parsed_detail = payload.get("detail") or str(exc)
        return payload, f"{intent} failed: HTTP {payload.get('httpStatus')} — {parsed_detail}"
    except Exception as exc:  # noqa: BLE001
        return None, str(exc)

    if kind != WriteKind.READ:
        return {"_note": f"Intent {intent} is catalogued but not wired in this demo build."}, None
    return None, f"Unhandled mutation intent: {intent}"


def _update_event(plan: dict[str, Any], *, dry_run: bool) -> tuple[dict[str, Any] | None, str | None]:
    event_id = plan.get("eventId") or ""
    new_name = (plan.get("headliners") or "").strip()
    if not event_id or not new_name:
        return None, "Include an event UUID and a new name (e.g. update event name for event id <uuid> to My Show)."
    current = apex_events.get_event(event_id)
    ev = unwrap_event_payload(current)
    previous = str(ev.get("headlinersText") or ev.get("headliners") or "")
    body = build_update_event_body_from_get(current, headliners=new_name)
    body["_previousHeadliners"] = previous
    payload = apex_events.update_event(event_id, body, dry_run=dry_run)
    if not dry_run and payload.get("_updated"):
        payload = {**payload, "eventAfter": apex_events.get_event(event_id)}
    return payload, None


