from __future__ import annotations

import re
from typing import Any

from apex_rag_demo.help_content import (
    IDENTITY_SUMMARY,
    WELCOME_SUMMARY,
    format_help_text,
    is_general_help_question,
)
from apex_rag_demo.intent_helpers import is_assistant_meta_question, is_greeting, is_off_topic

_REGION_PREFIX = re.compile(r"\[User region:\s*([^\]]+)\]\s*", re.I)

_FORMATTERS: dict[str, str] = {
    "search_events": "apex-search-api",
    "list_client_venues": "apex-search-api",
    "create_organization": "apex-admin-api",
    "create_client_venue": "apex-admin-api",
    "get_event": "apex-events-api",
    "inventory_zones": "apex-inventory-api",
    "marketing_events": "apex-marketing-api",
}


def parse_ui_region(question: str) -> str | None:
    match = _REGION_PREFIX.search(question)
    return match.group(1).strip() if match else None


def strip_ui_region(question: str) -> str:
    return _REGION_PREFIX.sub("", question).strip()


def _mock_note(payload: dict[str, Any] | None) -> list[str]:
    if payload and payload.get("_mock"):
        return ["", "Note: mock data (no token or APEX_MOCK).", ""]
    return []


def _api_failure(service: str, operation: str, api_error: str) -> str:
    return (
        f"Call to {service} failed ({operation}).\n\n"
        f"{api_error}\n\n"
        "Check your apex-dev JWT and permissions."
    )


def _venue_display(item: dict[str, Any]) -> str:
    venue = item.get("venue") or item.get("Venue") or {}
    client = item.get("client") or item.get("Client") or {}
    vid = item.get("id") or item.get("Id") or "?"
    name = venue.get("name") or venue.get("Name") or "Unnamed venue"
    client_name = client.get("name") or client.get("Name") or ""
    suffix = f" (client: {client_name})" if client_name else ""
    return f"- {name} — id {vid}{suffix}"


def format_search_events(
    question: str,
    payload: dict[str, Any] | None,
    api_error: str | None,
    plan: dict[str, Any],
) -> str:
    if api_error:
        return _api_failure("apex-search-api", "POST /v1/events/suggest", api_error)

    query = plan.get("query") or "?"
    lines = [
        f"Event search (apex-search-api POST /v1/events/suggest), query: \"{query}\".",
        "",
    ]
    lines.extend(_mock_note(payload))

    if not payload:
        return "\n".join(lines + ["No response body."])

    suggestions = payload.get("suggestions") or payload.get("Suggestions") or []
    if isinstance(suggestions, list) and suggestions:
        lines.append(f"Suggestions ({len(suggestions)}):")
        for item in suggestions[:15]:
            if isinstance(item, dict):
                name = item.get("name") or item.get("Name") or item.get("text") or str(item)
                vid = item.get("id") or item.get("Id") or ""
                venue = item.get("venueName") or item.get("venue") or ""
                extra = f" @ {venue}" if venue else ""
                lines.append(f"- {name}{extra} (id {vid})" if vid else f"- {name}{extra}")
            else:
                lines.append(f"- {item}")
        return "\n".join(lines)

    events = payload.get("events") or payload.get("Events") or []
    if isinstance(events, list) and events:
        lines.append(f"Events ({len(events)}):")
        for ev in events[:15]:
            if isinstance(ev, dict):
                name = ev.get("name") or ev.get("Name") or "?"
                eid = ev.get("id") or ev.get("Id") or ""
                lines.append(f"- {name} (id {eid})")
        return "\n".join(lines)

    lines.append("No events in this response. Try a longer query or POST /v1/events for full search.")
    return "\n".join(lines)


def format_list_client_venues(
    question: str,
    payload: dict[str, Any] | None,
    api_error: str | None,
) -> str:
    region = parse_ui_region(question) or "your selected region"

    if api_error:
        return _api_failure("apex-search-api", "POST /v1/client-venues", api_error)

    if not payload:
        return "No data returned from the client-venue search API."

    venues_raw = payload.get("clientVenues") or payload.get("ClientVenues") or []
    venues = list(venues_raw) if venues_raw else []

    lines = [
        "Client venues (apex-search-api POST /v1/client-venues).",
        f"UI region {region} is a preference only; filter by client/venue/org IDs in the API if needed.",
        "",
    ]
    lines.extend(_mock_note(payload))

    if not venues:
        lines.append("No client venues on this page.")
        return "\n".join(lines)

    lines.append(f"Showing {len(venues)} venue(s):")
    lines.extend(_venue_display(v) for v in venues[:25])
    if len(venues) > 25:
        lines.append(f"… and {len(venues) - 25} more.")
    return "\n".join(lines)


def format_create_organization(
    payload: dict[str, Any] | None,
    api_error: str | None,
    execute_writes: bool,
) -> str:
    if api_error:
        return _api_failure("apex-admin-api", "POST /v1/organizations", api_error)
    if not payload:
        return "No response from admin-api."

    lines: list[str] = []
    if payload.get("_dry_run") and not execute_writes:
        lines.append("Dry-run — request was NOT sent to admin-api.")
        lines.append(f"Would POST: {payload.get('endpoint', '/v1/organizations')}")
        req = payload.get("request") or {}
        lines.append(f"Body name: {req.get('name')}, region: {req.get('region')}, currency: {req.get('currency')}")
    else:
        lines.append("Organization create response (apex-admin-api):")
        oid = payload.get("organizationId") or payload.get("OrganizationId")
        if oid:
            lines.append(f"organizationId: {oid}")
        if payload.get("isSuccess") is not None:
            lines.append(f"isSuccess: {payload.get('isSuccess')}")

    lines.extend(_mock_note(payload))
    return "\n".join(lines)


def format_create_client_venue(
    payload: dict[str, Any] | None,
    api_error: str | None,
    execute_writes: bool,
) -> str:
    if api_error:
        return _api_failure("apex-admin-api", "POST /v1/client-venues", api_error)
    if not payload:
        return "No response from admin-api."

    lines: list[str] = []
    if payload.get("_dry_run") and not execute_writes:
        lines.append("Dry-run — request was NOT sent to admin-api.")
        lines.append(f"Would POST: {payload.get('endpoint', '/v1/client-venues')}")
        req = payload.get("request") or {}
        lines.append(
            f"Body name: {req.get('name')}, clientId: {req.get('clientId')}, "
            f"venueType: {req.get('venueType')}",
        )
    else:
        lines.append("Client venue create response (apex-admin-api):")
        cv = payload.get("clientVenue") or payload.get("ClientVenue") or payload
        cid = cv.get("id") or cv.get("Id")
        if cid:
            lines.append(f"clientVenueId: {cid}")

    lines.extend(_mock_note(payload))
    return "\n".join(lines)


def format_get_event(
    payload: dict[str, Any] | None,
    api_error: str | None,
    plan: dict[str, Any],
) -> str:
    eid = plan.get("eventId") or "?"
    if api_error:
        return _api_failure("apex-events-api", f"GET /{eid}", api_error)
    if not payload:
        return "No response from events-api."

    lines = [f"Event detail (apex-events-api GET /{eid}):", ""]
    lines.extend(_mock_note(payload))

    name = payload.get("name") or payload.get("Name") or payload.get("title")
    status = payload.get("status") or payload.get("Status")
    if name:
        lines.append(f"Name: {name}")
    if status:
        lines.append(f"Status: {status}")
    if not name and not status:
        lines.append("See fields returned:")
        for key in list(payload.keys())[:12]:
            if not key.startswith("_"):
                lines.append(f"- {key}: {payload[key]}")
    return "\n".join(lines)


def format_inventory_zones(
    payload: dict[str, Any] | None,
    api_error: str | None,
    plan: dict[str, Any],
) -> str:
    eid = plan.get("eventId") or "?"
    if api_error:
        return _api_failure(
            "apex-inventory-api",
            f"GET /events/{eid}/zones/primary",
            api_error,
        )
    if not payload:
        return "No response from inventory-api."

    lines = [
        f"Primary zones (apex-inventory-api GET /events/{eid}/zones/primary):",
        "",
    ]
    lines.extend(_mock_note(payload))

    zones = payload.get("zones") or payload.get("Zones") or []
    if isinstance(zones, list) and zones:
        lines.append(f"Zones ({len(zones)}):")
        for z in zones[:20]:
            if isinstance(z, dict):
                zid = z.get("zoneId") or z.get("id") or z.get("Id") or "?"
                zname = z.get("name") or z.get("Name") or ""
                lines.append(f"- {zname or 'Zone'} (id {zid})")
            else:
                lines.append(f"- {z}")
        return "\n".join(lines)

    lines.append("No zones in response (event may have no primary zones configured).")
    return "\n".join(lines)


def format_marketing_events(
    payload: dict[str, Any] | None,
    api_error: str | None,
) -> str:
    if api_error:
        return _api_failure("apex-marketing-api", "GET /v1/events", api_error)
    if not payload:
        return "No response from marketing-api."

    lines = ["Marketing events (apex-marketing-api GET /v1/events):", ""]
    lines.extend(_mock_note(payload))

    events = payload.get("events") or payload.get("Events") or payload.get("items") or []
    if isinstance(events, list) and events:
        lines.append(f"Events ({len(events)}):")
        for ev in events[:20]:
            if isinstance(ev, dict):
                name = ev.get("name") or ev.get("Name") or ev.get("eventName") or "?"
                eid = ev.get("eventId") or ev.get("id") or ev.get("Id") or ""
                lines.append(f"- {name} (id {eid})" if eid else f"- {name}")
            else:
                lines.append(f"- {ev}")
        return "\n".join(lines)

    lines.append("Empty list or unrecognized shape — raw keys: " + ", ".join(payload.keys()))
    return "\n".join(lines)


def format_explain(kb_snippets: list[str], question: str = "") -> str:
    bare = strip_ui_region(question)
    if bare and is_off_topic(bare):
        lines = [
            "I can't help with that here — this assistant is for APEX ticketing APIs "
            "(events, client venues, organizations, inventory, marketing).",
            "",
            "Try asking:",
        ]
        for item in (
            "List all client venues",
            "Search events matching <name>",
            "Get event <event-uuid>",
        ):
            lines.append(f"• {item}")
        return "\n".join(lines)

    if is_assistant_meta_question(bare):
        return IDENTITY_SUMMARY

    if is_greeting(bare):
        return f"{WELCOME_SUMMARY}\n\n{format_help_text()}"

    if is_general_help_question(bare):
        return format_help_text()

    lines = ["From knowledge base (not live API data):", ""]
    if kb_snippets:
        for snippet in kb_snippets[:4]:
            lines.append(f"• {snippet}")
    else:
        lines.append("• No matching topics. Type Help for example prompts.")
    lines.extend(["", format_help_text()])
    return "\n".join(lines)


def format_deterministic(
    intent: str,
    question: str,
    payload: dict[str, Any] | None,
    api_error: str | None,
    *,
    action_plan: dict[str, Any] | None = None,
    execute_writes: bool = False,
    kb_snippets: list[str] | None = None,
) -> str | None:
    """Agent-style replies: API facts only, no internal prompt leakage."""
    plan = action_plan or {}

    if intent == "explain":
        return format_explain(kb_snippets or [], question)

    if intent == "search_events":
        return format_search_events(question, payload, api_error, plan)
    if intent == "list_client_venues":
        return format_list_client_venues(question, payload, api_error)
    if intent == "create_organization":
        return format_create_organization(payload, api_error, execute_writes)
    if intent == "create_client_venue":
        return format_create_client_venue(payload, api_error, execute_writes)
    if intent == "get_event":
        if api_error:
            return format_get_event(payload, api_error, plan)
        if not plan.get("eventId"):
            return (
                "I need an event UUID to call apex-events-api (GET /{eventId}). "
                "Example: get event 8f0a2f5c-9f45-4a7e-93f2-2f6a3f1f2b10"
            )
        return format_get_event(payload, api_error, plan)
    if intent == "inventory_zones":
        if api_error:
            return format_inventory_zones(payload, api_error, plan)
        if not plan.get("eventId"):
            return (
                "I need an event UUID for apex-inventory-api "
                "(GET /events/{eventId}/zones/primary)."
            )
        return format_inventory_zones(payload, api_error, plan)
    if intent == "marketing_events":
        return format_marketing_events(payload, api_error)

    if api_error:
        svc = _FORMATTERS.get(intent, "API")
        return f"{svc} error: {api_error}"
    return None


def summarize_with_llm(question: str, api_block: str) -> str:
    """Last resort when no formatter applies."""
    from apex_rag_demo.clients.llama import chat_completion

    system = """You are an APEX internal assistant. Answer in plain language.
Use ONLY the API JSON below. Do not invent data.
Do not mention KB, intents, or action plans. Max 6 sentences."""
    user = f"Question: {strip_ui_region(question)}\n\nAPI JSON:\n{api_block}"
    return chat_completion(system, user, temperature=0.2)
