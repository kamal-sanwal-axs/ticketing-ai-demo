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
    wants_list_users,
)
from apex_rag_demo.crud_planners import plan_for_crud_intent
from apex_rag_demo.event_query_helpers import get_event_enrichment_flags, looks_like_event_inventory_followup
from apex_rag_demo.mutation_intent_helpers import looks_like_publish_event_request
from apex_rag_demo.crud_policy import write_kind_for_intent, WriteKind
from apex_rag_demo.crud_registry import match_mutation_intent
from apex_rag_demo.response_formatters import strip_ui_region

INTENTS = (
    "search_events",
    "search_orders",
    "search_order_payment_statuses",
    "search_customers",
    "list_client_venues",
    "list_users",
    "create_organization",
    "create_client_venue",
    "get_event",
    "update_event",
    "delete_event",
    "create_event",
    "publish_event",
    "update_organization",
    "update_client_venue",
    "create_inventory_zone",
    "reset_inventory_publish",
    "update_inventory_ticket_types",
    "update_inventory_ga_manifest",
    "list_marketing_pixels",
    "create_marketing_pixel",
    "update_marketing_pixel",
    "delete_marketing_pixel",
    "inventory_zones",
    "marketing_events",
    "get_venue_config",
    "b2b_flash_report",
    "reports_inventory_event",
    "reports_timezones",
    "explain",
)

_UUID_RE = re.compile(
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}",
)

_CLASSIFY_SYSTEM = """Classify the user message into exactly one intent.
Reply with only one token from this list:
search_events | search_orders | search_order_payment_statuses | list_client_venues | list_users | create_organization | create_client_venue | get_event | update_event | inventory_zones | marketing_events | explain

search_events = find or search events (search-api)
search_orders = search fan orders (search-api POST /v1/orders) — axs-apex-search Orders
search_order_payment_statuses = order payment status lookup (search-api POST /v1/orders/list/payment-statuses)
search_customers = search fan customers (search-api POST /v1/customers) — axs-apex-search Customers
list_client_venues = list or show all client venues (search-api POST /v1/client-venues)
list_users = B2B user directory (resources-api GET /v1/Users) — same as Admin UI user list
create_organization = create a new organization (admin-api)
create_client_venue = create a new client venue (admin-api)
get_event = get event details by event id (events-api)
update_event = change event title/headliners (events-api PUT) — requires event UUID and new name
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


def classify_intent(
    question: str,
    *,
    session_focus: dict[str, Any] | None = None,
    session_snippets: list[str] | None = None,
) -> str:
    from apex_rag_demo.agent_classify import classify_with_routing

    intent, _ = classify_with_routing(
        question,
        session_focus=session_focus,
        session_snippets=session_snippets,
    )
    return intent


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


def _extract_admin_user_id(question: str) -> str | None:
    if _UUID_RE.search(question):
        return None
    match = re.search(
        r"\b(?:user\s+)?(?:id\s+)?(\d{4,})\b",
        strip_ui_region(question),
        re.I,
    )
    return match.group(1) if match else None


def _extract_user_directory_search(question: str) -> str | None:
    bare = strip_ui_region(question)
    for pattern in (
        r"\busers?\s+(?:matching|named|like|containing)\s+(.+?)\s*$",
        r"\bsearch\s+users?\s+(?:for\s+)?(.+?)\s*$",
    ):
        match = re.search(pattern, bare, re.I)
        if match:
            text = match.group(1).strip().rstrip(".!?")
            if len(text) >= 2:
                return text
    return None


def plan_for_intent(
    intent: str,
    question: str,
    session_focus: dict[str, Any] | None = None,
    *,
    chroma_system_context: str | None = None,
    semantic_context_block: str | None = None,
    chat_history: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    from apex_rag_demo.agent_plan import plan_for_intent_agentic

    plan = plan_for_intent_agentic(
        intent,
        question,
        session_focus,
        chroma_system_context=chroma_system_context,
        semantic_context_block=semantic_context_block,
        chat_history=chat_history,
    )
    from apex_rag_demo.capability_routing import enrich_read_plan_from_question

    return enrich_read_plan_from_question(intent, plan, question)
