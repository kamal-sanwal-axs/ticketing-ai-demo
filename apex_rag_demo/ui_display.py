from __future__ import annotations

from typing import Any

from apex_rag_demo.help_content import (
    HELP_EXAMPLE_TABLE,
    build_help_display,
    build_identity_display,
    build_welcome_display,
    is_general_help_question,
)
from apex_rag_demo.intent_helpers import is_assistant_meta_question, is_greeting, is_off_topic
from apex_rag_demo.response_formatters import parse_ui_region, strip_ui_region


def _badge(intent: str) -> str:
    return intent.replace("_", " ")


def _note_mock(payload: dict[str, Any] | None) -> str | None:
    if payload and payload.get("_mock"):
        return "Sample data (mock or missing token)."
    return None


def build_ui_display(state: dict[str, Any]) -> dict[str, Any] | None:
    intent = state.get("intent") or "explain"
    payload = state.get("api_payload")
    api_error = state.get("api_error")
    question = state.get("question") or ""
    plan = state.get("action_plan") or {}
    kb = state.get("kb_snippets") or []
    execute_writes = state.get("execute_writes", False)

    if api_error:
        return {
            "type": "article",
            "title": "Request failed",
            "badge": _badge(intent),
            "level": "error",
            "paragraphs": [str(api_error)],
        }

    if intent == "list_client_venues":
        venues = list((payload or {}).get("clientVenues") or (payload or {}).get("ClientVenues") or [])
        region = parse_ui_region(question) or "US-West"
        rows = []
        for v in venues:
            venue = v.get("venue") or v.get("Venue") or {}
            client = v.get("client") or v.get("Client") or {}
            rows.append(
                {
                    "venueName": str(venue.get("name") or venue.get("Name") or "—"),
                    "clientName": str(client.get("name") or client.get("Name") or "—"),
                    "clientVenueId": str(v.get("id") or v.get("Id") or "—"),
                },
            )
        return {
            "type": "table",
            "title": "Client venues",
            "subtitle": f"Search API · UI region {region} (preference only, not an API filter)",
            "badge": _badge(intent),
            "footnote": _note_mock(payload),
            "count": len(rows),
            "columns": [
                {"key": "venueName", "label": "Venue"},
                {"key": "clientName", "label": "Client"},
                {"key": "clientVenueId", "label": "Client venue ID"},
            ],
            "rows": rows,
        }

    if intent == "search_events":
        query = plan.get("query") or "—"
        suggestions = (payload or {}).get("suggestions") or (payload or {}).get("Suggestions") or []
        rows = []
        for item in suggestions if isinstance(suggestions, list) else []:
            if isinstance(item, dict):
                rows.append(
                    {
                        "name": str(item.get("name") or item.get("Name") or item.get("text") or "—"),
                        "venue": str(item.get("venueName") or item.get("venue") or "—"),
                        "id": str(item.get("id") or item.get("Id") or "—"),
                    },
                )
        if not rows:
            events = (payload or {}).get("events") or (payload or {}).get("Events") or []
            for ev in events if isinstance(events, list) else []:
                if isinstance(ev, dict):
                    rows.append(
                        {
                            "name": str(ev.get("name") or ev.get("Name") or "—"),
                            "venue": "—",
                            "id": str(ev.get("id") or ev.get("Id") or "—"),
                        },
                    )
        return {
            "type": "table" if rows else "article",
            "title": "Event search",
            "subtitle": f'Suggest API · query: "{query}"',
            "badge": _badge(intent),
            "footnote": _note_mock(payload),
            "count": len(rows),
            "columns": [
                {"key": "name", "label": "Event"},
                {"key": "venue", "label": "Venue"},
                {"key": "id", "label": "ID"},
            ],
            "rows": rows,
            "paragraphs": (
                [
                    "No events matched that query in suggest search.",
                    "Try an artist, festival, or venue name (e.g. Splash House). "
                    "Date phrases like “this month” are not filters on this API—use a name instead.",
                ]
                if not rows
                else []
            ),
        }

    if intent == "marketing_events":
        events = (payload or {}).get("events") or (payload or {}).get("Events") or []
        rows = []
        for ev in events if isinstance(events, list) else []:
            if isinstance(ev, dict):
                rows.append(
                    {
                        "name": str(ev.get("name") or ev.get("Name") or ev.get("eventName") or "—"),
                        "id": str(ev.get("eventId") or ev.get("id") or ev.get("Id") or "—"),
                    },
                )
        return {
            "type": "table" if rows else "article",
            "title": "Events (marketing list)",
            "subtitle": (
                "Marketing API GET /v1/events — ticketed events, not client-venue registry "
                "(use “list client venues” for venues)"
            ),
            "badge": _badge(intent),
            "footnote": _note_mock(payload),
            "count": len(rows),
            "columns": [
                {"key": "name", "label": "Event"},
                {"key": "id", "label": "ID"},
            ],
            "rows": rows,
            "paragraphs": ["No events returned."] if not rows else [],
        }

    if intent == "inventory_zones":
        eid = plan.get("eventId") or "—"
        zones = (payload or {}).get("zones") or (payload or {}).get("Zones") or []
        rows = []
        for z in zones if isinstance(zones, list) else []:
            if isinstance(z, dict):
                rows.append(
                    {
                        "name": str(z.get("name") or z.get("Name") or "Zone"),
                        "zoneId": str(z.get("zoneId") or z.get("id") or z.get("Id") or "—"),
                    },
                )
        return {
            "type": "table" if rows else "article",
            "title": "Primary zones",
            "subtitle": f"Inventory API · event {eid}",
            "badge": _badge(intent),
            "footnote": _note_mock(payload),
            "count": len(rows),
            "columns": [
                {"key": "name", "label": "Zone"},
                {"key": "zoneId", "label": "Zone ID"},
            ],
            "rows": rows,
            "paragraphs": ["No primary zones in response."] if not rows else [],
        }

    if intent == "get_event":
        eid = plan.get("eventId") or "—"
        if not plan.get("eventId"):
            return {
                "type": "article",
                "title": "Event details",
                "badge": _badge(intent),
                "level": "warning",
                "paragraphs": [
                    "Include an event UUID in your message.",
                    "Example: get event 8f0a2f5c-9f45-4a7e-93f2-2f6a3f1f2b10",
                ],
            }
        p = payload or {}
        return {
            "type": "article",
            "title": str(p.get("name") or p.get("Name") or "Event"),
            "subtitle": f"Events API · {eid}",
            "badge": _badge(intent),
            "footnote": _note_mock(payload),
            "fields": [
                {"label": "Status", "value": str(p.get("status") or p.get("Status") or "—")},
                {"label": "Event ID", "value": eid},
            ],
        }

    if intent == "create_organization":
        p = payload or {}
        req = p.get("request") or {}
        dry = p.get("_dry_run") and not execute_writes
        return {
            "type": "article",
            "title": "Create organization",
            "subtitle": "Admin API POST /v1/organizations",
            "badge": _badge(intent),
            "level": "warning" if dry else "info",
            "footnote": _note_mock(payload),
            "fields": [
                {"label": "Mode", "value": "Dry-run (not sent)" if dry else "Live POST"},
                {"label": "Name", "value": str(req.get("name") or p.get("organizationId") or "—")},
                {"label": "Region", "value": str(req.get("region") or "—")},
                {"label": "Currency", "value": str(req.get("currency") or "—")},
                {
                    "label": "Organization ID",
                    "value": str(p.get("organizationId") or "—"),
                },
            ],
        }

    if intent == "create_client_venue":
        p = payload or {}
        req = p.get("request") or {}
        dry = p.get("_dry_run") and not execute_writes
        cv = p.get("clientVenue") or p.get("ClientVenue") or {}
        return {
            "type": "article",
            "title": "Create client venue",
            "subtitle": "Admin API POST /v1/client-venues",
            "badge": _badge(intent),
            "level": "warning" if dry else "info",
            "footnote": _note_mock(payload),
            "fields": [
                {"label": "Mode", "value": "Dry-run (not sent)" if dry else "Live POST"},
                {"label": "Name", "value": str(req.get("name") or "—")},
                {"label": "Client ID", "value": str(req.get("clientId") or "—")},
                {"label": "Venue type", "value": str(req.get("venueType") or "—")},
                {"label": "Client venue ID", "value": str(cv.get("id") or cv.get("Id") or "—")},
            ],
        }

    if intent == "explain":
        bare = strip_ui_region(question)
        if bare and is_off_topic(bare):
            return {
                "type": "article",
                "title": "Outside APEX scope",
                "badge": _badge(intent),
                "paragraphs": [
                    "I can't answer general questions like weather or trivia. "
                    "I'm wired to APEX dev APIs for ticketing operations.",
                ],
                "sections": [
                    {
                        "title": "Example prompts",
                        "table": HELP_EXAMPLE_TABLE,
                    },
                ],
            }
        if is_assistant_meta_question(bare):
            return build_identity_display()
        if is_greeting(bare):
            return build_welcome_display()
        if is_general_help_question(bare):
            return build_help_display()
        return {
            "type": "article",
            "title": "Answer",
            "subtitle": "From internal KB — not live API data",
            "badge": _badge(intent),
            "sections": [
                {
                    "title": "Summary",
                    "paragraphs": kb[:4] if kb else ["No matching KB topics. Type Help for example prompts."],
                },
                {"title": "Example prompts", "table": HELP_EXAMPLE_TABLE},
            ],
        }

    return {
        "type": "article",
        "title": "Response",
        "badge": _badge(intent),
        "paragraphs": [state.get("answer") or ""],
    }
