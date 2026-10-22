from __future__ import annotations

import json
import re
from typing import Any

from apex_rag_demo.clients.llama import chat_completion

INTENTS = (
    "search_events",
    "create_organization",
    "create_client_venue",
    "get_event",
    "inventory_zones",
    "marketing_events",
    "explain",
)

_UUID_RE = re.compile(
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}",
)

_CLASSIFY_SYSTEM = """Classify the user message into exactly one intent.
Reply with only one token from this list:
search_events | create_organization | create_client_venue | get_event | inventory_zones | marketing_events | explain

search_events = find or search events (search-api)
create_organization = create a new organization (admin-api)
create_client_venue = create a client venue (admin-api)
get_event = get event details by event id (events-api)
inventory_zones = zones or inventory for an event (inventory-api)
marketing_events = list marketing events or pixels context (marketing-api)
explain = how something works, general help"""


def _parse_json_object(text: str) -> dict[str, Any]:
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fence:
        text = fence.group(1)
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        text = text[start : end + 1]
    return json.loads(text)


def classify_intent(question: str) -> str:
    q = question.lower()
    if any(w in q for w in ("create org", "new organization", "create organization")):
        return "create_organization"
    if "create" in q and any(w in q for w in ("venue", "client venue", "arena")):
        return "create_client_venue"
    if any(w in q for w in ("search", "find", "lookup")) and "event" in q:
        return "search_events"
    if "event" in q and "suggest" in q:
        return "search_events"
    if _UUID_RE.search(question) and any(w in q for w in ("zone", "inventory", "ticket")):
        return "inventory_zones"
    if _UUID_RE.search(question) and any(w in q for w in ("event detail", "get event", "event by id")):
        return "get_event"
    if "marketing" in q and "event" in q:
        return "marketing_events"
    if any(w in q for w in ("pixel", "marketing list")):
        return "marketing_events"

    raw = chat_completion(_CLASSIFY_SYSTEM, question, temperature=0.0).strip().lower()
    for intent in INTENTS:
        if intent in raw:
            return intent
    return "explain"


_PLAN_ORG_SYSTEM = """Extract fields for POST /v1/organizations (apex-admin-api).
Return JSON only with keys: name (required), parentOrganizationId (optional uuid),
currency, region, address (object with addressLine, city, state, zip, country).
Use sensible defaults for missing address fields."""


_PLAN_VENUE_SYSTEM = """Extract fields for POST /v1/client-venues (apex-admin-api).
Return JSON only with keys: clientId (uuid, required if mentioned), name, venueType
(one of Shared, Open, Exclusive), timezoneId (IANA), address, venueMaps (optional).
If client id not in message, omit clientId."""


_PLAN_SEARCH_SYSTEM = """Extract a short event search query for apex-search-api.
Return JSON only: {"query": "..."} with 2-100 characters."""


def _extract_event_id(question: str) -> str | None:
    match = _UUID_RE.search(question)
    return match.group(0) if match else None


def plan_for_intent(intent: str, question: str) -> dict[str, Any]:
    if intent == "search_events":
        raw = chat_completion(_PLAN_SEARCH_SYSTEM, question, temperature=0.0)
        try:
            data = _parse_json_object(raw)
            query = str(data.get("query", "")).strip()
        except json.JSONDecodeError:
            query = question[:80]
        if len(query) < 2:
            query = question[:80]
        return {"query": query}

    if intent == "create_organization":
        raw = chat_completion(_PLAN_ORG_SYSTEM, question, temperature=0.0)
        try:
            return _parse_json_object(raw)
        except json.JSONDecodeError:
            return {"name": question[:120] or "Demo Organization"}

    if intent == "create_client_venue":
        raw = chat_completion(_PLAN_VENUE_SYSTEM, question, temperature=0.0)
        try:
            return _parse_json_object(raw)
        except json.JSONDecodeError:
            return {"name": question[:120] or "Demo Client Venue"}

    if intent in ("get_event", "inventory_zones"):
        event_id = _extract_event_id(question)
        return {"eventId": event_id or ""}

    if intent == "marketing_events":
        return {}

    return {}
