from __future__ import annotations

import json
import re
from typing import Any

from apex_rag_demo.clients.llama import chat_completion
from apex_rag_demo.help_content import is_general_help_question
from apex_rag_demo.intent_helpers import (
    extract_event_search_query,
    guard_api_intent,
    is_assistant_meta_question,
    is_events_not_venues_request,
    is_greeting,
    is_off_topic,
    is_weak_suggest_query,
    looks_like_list_events,
    looks_like_named_event_search,
    looks_like_event_search,
    mentions_event_keyword,
    wants_list_client_venues,
)
from apex_rag_demo.response_formatters import strip_ui_region

INTENTS = (
    "search_events",
    "list_client_venues",
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
search_events | list_client_venues | create_organization | create_client_venue | get_event | inventory_zones | marketing_events | explain

search_events = find or search events (search-api)
list_client_venues = list or show all client venues (search-api POST /v1/client-venues)
create_organization = create a new organization (admin-api)
create_client_venue = create a new client venue (admin-api)
get_event = get event details by event id (events-api)
inventory_zones = zones or inventory for an event (inventory-api)
marketing_events = list or browse events (marketing-api GET /v1/events) — published/live/all events, date-style asks
explain = off-topic (weather, jokes), bot identity, how something works, or general APEX help

list_client_venues = ONLY when user asks for client venues (venue registry), NOT ticketed events.

Important: "weather" is NOT get_event. get_event requires an explicit event UUID in the message."""


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


def _extract_search_query_heuristic(question: str) -> str | None:
    bare = strip_ui_region(question)
    if not looks_like_named_event_search(bare):
        return None
    query = extract_event_search_query(bare)
    if is_weak_suggest_query(query):
        return None
    return query if len(query) >= 2 else None


def classify_intent(question: str) -> str:
    q = question.lower()
    bare = strip_ui_region(question)
    bare_lower = bare.lower()

    if is_off_topic(bare):
        return "explain"

    if is_general_help_question(bare):
        return "explain"

    if is_greeting(bare):
        return "explain"

    if is_assistant_meta_question(bare):
        return "explain"

    bare_stripped = bare_lower.strip().rstrip(".!?")
    if looks_like_list_events(bare) or (
        is_events_not_venues_request(bare) and bare_stripped in ("all events", "events", "event")
    ):
        return "marketing_events"

    if wants_list_client_venues(bare):
        return "list_client_venues"

    if looks_like_named_event_search(bare):
        return "search_events"

    if looks_like_event_search(bare):
        return "marketing_events" if is_weak_suggest_query(extract_event_search_query(bare)) else "search_events"

    if any(w in q for w in ("how does", "how do i", "what is", "explain", "help me understand")):
        action_phrases = (
            "create ",
            "list all",
            "list client",
            "search events",
            "find events",
            "get event",
            "inventory zone",
            "marketing events",
            "client venue",
            "organization",
        )
        if not any(p in q for p in action_phrases):
            return "explain"

    if any(w in q for w in ("create org", "new organization", "create organization")):
        return "create_organization"

    if wants_list_client_venues(bare):
        return "list_client_venues"

    if "create" in q and any(w in q for w in ("venue", "client venue", "arena")):
        return "create_client_venue"

    if _UUID_RE.search(question):
        if any(w in q for w in ("zone", "inventory", "ticket type", "primary zone")):
            return "inventory_zones"
        if any(w in q for w in ("event", "detail", "status", "publish")):
            return "get_event"
        if "inventory" in q or "zones" in q:
            return "inventory_zones"
        return "get_event"

    if any(w in q for w in ("marketing event", "marketing list", "pixel")):
        return "marketing_events"
    if "list" in q and "marketing" in q:
        return "marketing_events"
    if bare in ("list marketing events", "marketing events"):
        return "marketing_events"

    if any(w in q for w in ("search", "find", "lookup", "matching", "suggest")) and mentions_event_keyword(
        bare_lower,
    ):
        return "search_events"
    if mentions_event_keyword(bare_lower) and "venue" not in bare_lower and "client" not in bare_lower:
        if any(w in q for w in ("search", "find", "look")):
            return "search_events"

    if is_events_not_venues_request(bare) and not wants_list_client_venues(bare):
        return "marketing_events"

    raw = chat_completion(_CLASSIFY_SYSTEM, bare, temperature=0.0).strip().lower()
    for intent in INTENTS:
        if intent in raw:
            return guard_api_intent(intent, question)
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
        heuristic = _extract_search_query_heuristic(question)
        if heuristic and len(heuristic) >= 2:
            return {"query": heuristic}
        raw = chat_completion(_PLAN_SEARCH_SYSTEM, strip_ui_region(question), temperature=0.0)
        try:
            data = _parse_json_object(raw)
            query = str(data.get("query", "")).strip()
        except json.JSONDecodeError:
            query = strip_ui_region(question)[:80]
        if len(query) < 2:
            query = strip_ui_region(question)[:80]
        return {"query": query}

    if intent == "create_organization":
        raw = chat_completion(_PLAN_ORG_SYSTEM, strip_ui_region(question), temperature=0.0)
        try:
            return _parse_json_object(raw)
        except json.JSONDecodeError:
            return {"name": strip_ui_region(question)[:120] or "Demo Organization"}

    if intent == "create_client_venue":
        raw = chat_completion(_PLAN_VENUE_SYSTEM, strip_ui_region(question), temperature=0.0)
        try:
            return _parse_json_object(raw)
        except json.JSONDecodeError:
            return {"name": strip_ui_region(question)[:120] or "Demo Client Venue"}

    if intent in ("get_event", "inventory_zones"):
        event_id = _extract_event_id(question)
        return {"eventId": event_id or ""}

    if intent == "marketing_events":
        return {}

    if intent == "list_client_venues":
        org_ids = [m.group(0) for m in _UUID_RE.finditer(question)]
        return {
            "pageSize": 25,
            "organizationIds": org_ids[:5],
        }

    return {}
