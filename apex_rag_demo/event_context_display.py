from __future__ import annotations

from typing import Any

from apex_rag_demo.event_list import EVENT_HIERARCHY_TABLE_COLUMNS, event_table_rows


def _events_from_payload(block: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not block:
        return []
    for key in ("events", "Events", "items", "suggestions", "Suggestions"):
        data = block.get(key)
        if isinstance(data, list):
            return [x for x in data if isinstance(x, dict)]
    return []


def build_resolved_id_display(
    payload: dict[str, Any],
    plan: dict[str, Any],
    api_error: str | None,
) -> dict[str, Any] | None:
    resolution = payload.get("_resolution")
    if resolution in (None, "events_get", "events_get_via_search"):
        return None

    rid = payload.get("_requested_id") or plan.get("eventId") or "—"
    paragraphs = [str(n) for n in (payload.get("_notes") or []) if n]
    if api_error:
        paragraphs.append(str(api_error))

    sections: list[dict[str, Any]] = []

    if resolution == "client_venue_context":
        cv = payload.get("clientVenue") or {}
        inner = cv.get("clientVenue") or cv.get("ClientVenue") or cv
        venue = (inner.get("venue") or inner.get("Venue") or {}) if isinstance(inner, dict) else {}
        client = (inner.get("client") or inner.get("Client") or {}) if isinstance(inner, dict) else {}
        sections.append(
            {
                "title": "Client venue (search-api)",
                "fields": [
                    {"label": "Client venue ID", "value": rid},
                    {
                        "label": "Venue",
                        "value": str(venue.get("name") or venue.get("Name") or "—"),
                    },
                    {
                        "label": "Client",
                        "value": str(client.get("name") or client.get("Name") or "—"),
                    },
                ],
                "paragraphs": [
                    "This id is a client venue registry id, not an events-api event id. "
                    "Use an event UUID from the table below for get event / inventory.",
                ],
            },
        )
        search_block = payload.get("search") or payload.get("suggest")
        rows = event_table_rows(search_block)
        if rows:
            sections.append(
                {
                    "title": "Related events (search-api)",
                    "table": {
                        "columns": EVENT_HIERARCHY_TABLE_COLUMNS,
                        "rows": rows,
                    },
                },
            )

    elif resolution in ("search_events_only", "search_suggest"):
        block = payload.get("search") or payload.get("suggest")
        rows = event_table_rows(block)
        if rows:
            sections.append(
                {
                    "title": "Events from search-api",
                    "table": {"columns": EVENT_HIERARCHY_TABLE_COLUMNS, "rows": rows},
                },
            )

    level = "error" if resolution == "not_found" else "warning" if resolution != "search_events_only" else "info"

    return {
        "type": "article",
        "title": "Event id lookup",
        "subtitle": f"Search + events fallback · requested id {rid}",
        "badge": "get event",
        "level": level,
        "paragraphs": paragraphs,
        "sections": sections,
    }
