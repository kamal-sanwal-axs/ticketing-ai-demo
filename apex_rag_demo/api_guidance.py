from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

from apex_rag_demo.response_formatters import strip_ui_region

_SERVICES_PATH = Path(__file__).resolve().parents[1] / "data" / "apex_services.json"

_RULES: list[tuple[re.Pattern[str], str, str]] = [
    (
        re.compile(
            r"\b(buy|purchase|book|reserve)\b.*\b(seat|seats|ticket|tickets)\b|"
            r"\bcan you (buy|get|sell)\b.*\b(ticket|seat)\b",
            re.I,
        ),
        "search",
        "Fan checkout is not a back-office API here. Configure publish + inventory in Events/Inventory MFEs; "
        "verify sales with search-api POST /v1/orders (Orders in axs-apex-search).",
    ),
    (
        re.compile(r"\b(find|search|lookup)\b.*\borders?\b", re.I),
        "search",
        "Say: search orders for <email or order number> — search-api POST /v1/orders (axs-apex-search Orders).",
    ),
    (
        re.compile(r"\b(find|search|lookup)\b.*\bcustomers?\b", re.I),
        "search",
        "Say: search customers for <email or name> — search-api POST /v1/customers (b2b_search_customers).",
    ),
    (
        re.compile(r"\b(b2b[- ]?platform|single[- ]?spa|MFE remotes)\b", re.I),
        "search",
        "Platform map: axs-b2b-platform hosts child MFEs; API tasks use search/events/admin intents — not UI shell tests.",
    ),
    (
        re.compile(r"\bpublish\b", re.I),
        "events",
        "Say: publish event <event-uuid> or publish AINV-#### <id-prefix> — calls events-api POST /{{eventId}}/publish.",
    ),
    (
        re.compile(r"\b(client[- ]?venues?|list\s+venues)\b", re.I),
        "search",
        "Say: list all client venues — search-api POST /v1/client-venues.",
    ),
    (
        re.compile(r"\b(users?|roles?|assignments?)\b", re.I),
        "admin",
        "Say: show me users — resources/admin user directory (demo uses resources GET /v1/Users).",
    ),
    (
        re.compile(r"\b(show|list)\s+(me\s+)?(all\s+)?events?\b", re.I),
        "marketing",
        "Use: show me events — marketing-api GET /v1/events (search-api fallback if marketing is forbidden).",
    ),
    (
        re.compile(r"\b(search|find|matching)\b.*\bevents?\b", re.I),
        "search",
        'Say: search events matching <name> — search-api POST /v1/events/suggest.',
    ),
    (
        re.compile(r"\b(marketing|catalog)\b.*\bevents?\b", re.I),
        "marketing",
        "Say: list marketing events or show events after <date> — marketing-api GET /v1/events (or search fallback).",
    ),
    (
        re.compile(r"\b(inventory|zones?|ticket\s+types?|price\s+levels?)\b", re.I),
        "inventory",
        "Say: inventory zones for event <event-uuid> — inventory-api GET /events/{eventId}/zones/primary.",
    ),
    (
        re.compile(
            r"\b(b2b[- ]?reports?|flash\s+(sales|report)|ticket\s+life[- ]?cycle|inventory\s+report)\b",
            re.I,
        ),
        "reports",
        "Say: flash sales report context <id> event <id> — reports-api PUT /v1/Sales/event?regionId=1 "
        "(unified-api-reports / axs-b2b-reports). Inventory: GET /v1/Inventory/contexts/{contextId}/events/{eventId}/report.",
    ),
    (
        re.compile(r"\b(venue\s+config|manifest)\b.*\b(uuid|id)\b|\bvenueConfigId\b", re.I),
        "manifest",
        "Say: venue config <venueConfigId-uuid> — manifest-api GET /venue-configs/{venueConfigId}.",
    ),
    (
        re.compile(r"\b(get|details?)\b.*\bevents?\b", re.I),
        "events",
        "Say: get event <event-uuid> — events-api GET /{eventId}.",
    ),
    (
        re.compile(r"\bshow\b.*\bevent\s+id\b", re.I),
        "events",
        "Say: get event <event-uuid> — events-api GET /{eventId}.",
    ),
    (
        re.compile(r"\b(organization|org)\b", re.I),
        "admin",
        "Say: create organization <name> — admin-api POST /v1/organizations.",
    ),
]


@lru_cache(maxsize=1)
def load_apex_services() -> list[dict]:
    if not _SERVICES_PATH.is_file():
        return []
    return json.loads(_SERVICES_PATH.read_text(encoding="utf-8"))


def service_by_id(service_id: str) -> dict | None:
    for svc in load_apex_services():
        if svc.get("id") == service_id:
            return svc
    return None


def openapi_sentence_for_service(service_id: str) -> str:
    svc = service_by_id(service_id)
    if not svc:
        return ""
    ops = svc.get("demo_operations") or []
    op_text = ", ".join(str(o) for o in ops[:4])
    return (
        f"{svc.get('name', service_id)} — OpenAPI {svc.get('swagger_url', '')}. "
        f"Demo calls: {op_text}."
    )


def explain_need_api_prompt(question: str, kb_snippets: list[str] | None = None) -> str:
    """One-line guidance when the assistant did not call a live API."""
    bare = strip_ui_region(question)
    from apex_rag_demo.fan_purchase import format_fan_purchase_guidance, looks_like_fan_purchase_request

    if looks_like_fan_purchase_request(bare):
        return format_fan_purchase_guidance(bare)
    from apex_rag_demo.compound_request import looks_like_events_plus_seat_level_detail

    if looks_like_events_plus_seat_level_detail(bare):
        return (
            "This is a multi-step live API flow: list published/on-sale events, then load inventory "
            "(price codes, ticket types, zones) per event. Retry the message — the orchestrator should "
            "run marketing_events then get_event with inventory automatically."
        )
    for pattern, service_id, template in _RULES:
        if pattern.search(bare):
            base = openapi_sentence_for_service(service_id)
            hint = template.replace("{{eventId}}", "{eventId}")
            return f"I need a live API request, not docs. {hint} ({base})" if base else f"I need a live API request. {hint}"

    if kb_snippets:
        for snippet in kb_snippets[:5]:
            text = str(snippet)[:200].strip()
            if not text:
                continue
            if "Create organization" in text and not re.search(r"\borgani", bare, re.I):
                continue
            return (
                "I need a direct API command (event uuid, search name, or list/search verb). "
                f"Closest capability: {text[:160]}"
            )

    services = load_apex_services()
    if services:
        names = ", ".join(s.get("id", "") for s in services[:5])
        return (
            f"I only answer from live APIs here ({names}). "
            "Try: list client venues, search events matching <name>, get event <uuid>, or publish event <uuid>."
        )
    return "I need a direct API command — e.g. search events matching <name> or get event <event-uuid>."


def all_services_openapi_summary() -> str:
    parts = [openapi_sentence_for_service(s.get("id", "")) for s in load_apex_services()]
    return " ".join(p for p in parts if p)
