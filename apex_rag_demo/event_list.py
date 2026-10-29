from __future__ import annotations

from typing import Any

from apex_rag_demo.org_hierarchy import HierarchyIndex, get_hierarchy_index

EVENT_NAME_ONLY_TABLE_COLUMNS: list[dict[str, str]] = [
    {"key": "name", "label": "Event name"},
]

EVENT_HIERARCHY_TABLE_COLUMNS: list[dict[str, str]] = [
    {"key": "principalOrganization", "label": "Principal org"},
    {"key": "contractualOrganization", "label": "Contractual org"},
    {"key": "client", "label": "Client"},
    {"key": "clientVenue", "label": "Client venue"},
    {"key": "name", "label": "Event"},
    {"key": "startDate", "label": "Start date"},
    {"key": "endDate", "label": "End date"},
    {"key": "status", "label": "Status"},
    {"key": "id", "label": "Event ID"},
    {"key": "clientVenueId", "label": "Client venue ID"},
]

CLIENT_VENUE_HIERARCHY_TABLE_COLUMNS: list[dict[str, str]] = [
    {"key": "principalOrganization", "label": "Principal org"},
    {"key": "contractualOrganization", "label": "Contractual org"},
    {"key": "client", "label": "Client"},
    {"key": "clientVenue", "label": "Client venue"},
    {"key": "venueName", "label": "Venue"},
    {"key": "clientVenueId", "label": "Client venue ID"},
]

# Backward-compatible alias
EVENT_SCHEDULE_TABLE_COLUMNS = EVENT_HIERARCHY_TABLE_COLUMNS


def event_display_name(ev: dict[str, Any]) -> str:
    from apex_rag_demo.event_query_helpers import strip_html_text

    candidates: list[Any] = [
        ev.get("headlinersText"),
        ev.get("headliners"),
        ev.get("name"),
        ev.get("Name"),
        ev.get("eventName"),
        ev.get("title"),
        ev.get("text"),
        ev.get("tour"),
        ev.get("presentedBy"),
    ]
    for raw in candidates:
        if not raw:
            continue
        text = strip_html_text(str(raw)) if "<" in str(raw) else str(raw).strip()
        if not text or text.lower() == "event":
            continue
        return text
    return "—"


def event_has_actionable_name(ev: dict[str, Any]) -> bool:
    return event_display_name(ev) != "—"


def event_state_label(ev: dict[str, Any]) -> str:
    return str(ev.get("state") or ev.get("lifecycle") or ev.get("status") or ev.get("Status") or "—")


def format_api_datetime(value: Any) -> str:
    if not value:
        return "—"
    text = str(value).strip()
    if not text:
        return "—"
    if "T" in text:
        base = text.split(".")[0]
        for marker in ("+", "-"):
            idx = base.rfind(marker)
            if idx > 10:
                base = base[:idx]
                break
        return base.replace("T", " ", 1)
    return text[:10] if len(text) >= 10 else text


def event_start_end_labels(ev: dict[str, Any]) -> tuple[str, str]:
    dates = ev.get("dates") or {}
    if not isinstance(dates, dict):
        return "—", "—"
    start = (dates.get("start") or {}).get("on") if isinstance(dates.get("start"), dict) else None
    end = (dates.get("end") or {}).get("on") if isinstance(dates.get("end"), dict) else None
    return format_api_datetime(start), format_api_datetime(end)


def _venue_label(ev: dict[str, Any]) -> str:
    if ev.get("venueName"):
        return str(ev["venueName"])
    venue = ev.get("venue") or ev.get("Venue")
    if isinstance(venue, dict):
        return str(venue.get("name") or venue.get("Name") or "—")
    if venue:
        return str(venue)
    return "—"


def unwrap_event_payload(payload: dict[str, Any] | None) -> dict[str, Any]:
    if not payload:
        return {}
    event = payload.get("event") or payload.get("Event")
    if isinstance(event, dict):
        return event
    return payload


def iter_event_dicts(payload: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not payload:
        return []
    if isinstance(payload.get("event"), dict):
        return [payload["event"]]
    if isinstance(payload.get("Event"), dict):
        return [payload["Event"]]

    collected: list[dict[str, Any]] = []
    for key in ("events", "Events", "items", "suggestions", "Suggestions"):
        block = payload.get(key)
        if block is None:
            continue
        if isinstance(block, list):
            collected.extend([ev for ev in block if isinstance(ev, dict)])
    return collected


def event_table_rows(
    payload: dict[str, Any] | None,
    *,
    include_state: bool = True,
    hierarchy: HierarchyIndex | None = None,
) -> list[dict[str, str]]:
    h = hierarchy or get_hierarchy_index()
    rows: list[dict[str, str]] = []
    for ev in iter_event_dicts(payload):
        start_date, end_date = event_start_end_labels(ev)
        chain = h.for_event(ev)
        row: dict[str, str] = {
            **chain,
            "name": event_display_name(ev),
            "startDate": start_date,
            "endDate": end_date,
            "status": event_state_label(ev),
            "venue": _venue_label(ev),
            "id": str(ev.get("eventId") or ev.get("id") or ev.get("Id") or "—"),
        }
        if not row["clientVenue"] or row["clientVenue"] == "—":
            row["clientVenue"] = row["venue"]
        if include_state:
            row["state"] = row["status"]
        rows.append(row)
    return rows


def client_venue_table_rows(
    payload: dict[str, Any] | None,
    *,
    hierarchy: HierarchyIndex | None = None,
) -> list[dict[str, str]]:
    h = hierarchy or get_hierarchy_index()
    venues = list((payload or {}).get("clientVenues") or (payload or {}).get("ClientVenues") or [])
    rows: list[dict[str, str]] = []
    for item in venues:
        if not isinstance(item, dict):
            continue
        cv_id = str(item.get("id") or item.get("Id") or "—")
        venue = item.get("venue") or item.get("Venue") or {}
        client = item.get("client") or item.get("Client") or {}
        chain = h.for_client_venue_id(cv_id if cv_id != "—" else None)
        if chain["client"] == "—" and client.get("name"):
            chain["client"] = str(client["name"])
        venue_name = str(venue.get("name") or venue.get("Name") or "—")
        if chain["clientVenue"] == "—":
            chain["clientVenue"] = venue_name
        rows.append(
            {
                **chain,
                "venueName": venue_name,
                "clientVenueId": cv_id,
            },
        )
    return rows


def hierarchy_footnote(hierarchy: HierarchyIndex | None = None) -> str | None:
    h = hierarchy or get_hierarchy_index()
    if h.error:
        return f"Org hierarchy (admin tree) unavailable: {h.error}"
    if h.loaded:
        return (
            "Org columns from Admin GET /v1/organizations/principals/{{id}}/tree "
            f"(principal: {h.principal_org_name})."
        )
    return None
