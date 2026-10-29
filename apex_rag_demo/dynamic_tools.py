"""OpenAPI-derived dynamic tools (Cursor-style): catalog from swagger, not static intent phrases."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from apex_rag_demo.api_guidance import load_apex_services
from apex_rag_demo.config import DATA_DIR
from apex_rag_demo.crud_registry import CRUD_CATALOG
from apex_rag_demo.planning import INTENTS
from apex_rag_demo.response_formatters import strip_ui_region

OPENAPI_CACHE_DIR = DATA_DIR / "openapi_cache"
_HTTP_METHODS = frozenset({"get", "post", "put", "patch", "delete"})
_UUID_RE = re.compile(
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}",
)

# Map OpenAPI path patterns → existing LangGraph intent (UI formatters + client wrappers).
_LEGACY_INTENT_RULES: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"/v1/orders/list/payment-statuses", re.I), "search_order_payment_statuses"),
    (re.compile(r"/v1/orders", re.I), "search_orders"),
    (re.compile(r"/v1/customers", re.I), "search_customers"),
    (re.compile(r"/v1/client-venues", re.I), "list_client_venues"),
    (re.compile(r"/v1/events/suggest", re.I), "search_events"),
    (re.compile(r"/v1/events/filtered-search", re.I), "marketing_events"),
    (re.compile(r"/v1/events", re.I), "search_events"),
    (re.compile(r"/v1/Users", re.I), "list_users"),
    (re.compile(r"/v1/organizations", re.I), "create_organization"),
    (re.compile(r"/events/\{eventId\}/zones/primary", re.I), "inventory_zones"),
    (re.compile(r"/venue-configs/\{venueConfigId\}", re.I), "get_venue_config"),
    (re.compile(r"/v1/Sales/dateRange", re.I), "b2b_flash_report"),
    (re.compile(r"/v1/Sales/event", re.I), "b2b_flash_report"),
    (re.compile(r"/v1/TicketLifeCycle/event", re.I), "b2b_flash_report"),
    (re.compile(r"/v1/TicketInTransfer/event", re.I), "b2b_flash_report"),
    (re.compile(r"/v1/Inventory/contexts/\{contextId\}/events/\{eventId\}/report", re.I), "reports_inventory_event"),
    (re.compile(r"/v1/Timezones/timezones", re.I), "reports_timezones"),
    (re.compile(r"/\{eventId\}/publish", re.I), "publish_event"),
    (re.compile(r"/\{eventId\}", re.I), "get_event"),
]


@dataclass(frozen=True)
class DynamicTool:
    tool_id: str
    service_id: str
    method: str
    path_template: str
    summary: str
    legacy_intent: str
    base_url_env: str
    default_base_url: str
    operation_id: str = ""
    tags: tuple[str, ...] = ()

    def description(self) -> str:
        return (
            f"{self.summary or self.operation_id or self.path_template}. "
            f"{self.method.upper()} {self.path_template} "
            f"({self.service_id} API → intent {self.legacy_intent})."
        )


def _legacy_intent_for_path(service_id: str, path: str, method: str) -> str | None:
    if service_id == "manifest" and method == "get" and "venue-configs" in path:
        return "get_venue_config"
    if service_id == "reports":
        if method == "get" and "/Timezones/timezones" in path:
            return "reports_timezones"
        if method == "get" and "/Inventory/contexts/" in path:
            return "reports_inventory_event"
        if method == "put" and "/v1/" in path:
            return "b2b_flash_report"
    if service_id == "marketing" and method == "get" and "/v1/events" in path:
        return "marketing_events"
    if service_id == "search":
        if method == "post" and path.rstrip("/") == "/v1/events":
            return "search_events"
        if method == "post" and "/v1/events/suggest" in path:
            return "search_events"
        if "/v1/client-venues" in path:
            return "list_client_venues"
        if "/v1/customers" in path:
            return "search_customers"
        if "/v1/orders/list/payment-statuses" in path:
            return "search_order_payment_statuses"
        if "/v1/orders" in path:
            return "search_orders"
        return None
    for pattern, intent in _LEGACY_INTENT_RULES:
        if pattern.search(path):
            if intent in INTENTS:
                return intent
    if method == "get" and "{eventId}" in path and service_id == "events":
        return "get_event"
    return None


def _demo_operation_keys(service: dict[str, Any]) -> set[tuple[str, str]]:
    keys: set[tuple[str, str]] = set()
    for raw in service.get("demo_operations") or []:
        text = str(raw).strip()
        m = re.match(r"^(GET|POST|PUT|PATCH|DELETE)\s+(.+)$", text, re.I)
        if m:
            keys.add((m.group(1).lower(), m.group(2).split()[0].strip()))
    for entry in CRUD_CATALOG:
        m = re.match(r"^(GET|POST|PUT|PATCH|DELETE)\s+(.+)$", entry.http, re.I)
        if m:
            keys.add((m.group(1).lower(), m.group(2).split("{")[0].rstrip("/")))
    return keys


def _path_allowed(
    service_id: str,
    method: str,
    path: str,
    *,
    demo_keys: set[tuple[str, str]],
) -> bool:
    legacy = _legacy_intent_for_path(service_id, path, method)
    if legacy is None:
        return False
    if method == "get":
        return True
    if method == "put" and service_id == "reports" and legacy == "b2b_flash_report":
        return True
    if method in ("post", "put", "patch", "delete"):
        for dm, prefix in demo_keys:
            if dm == method and path.startswith(prefix):
                return True
        if legacy in {
            "search_orders",
            "search_customers",
            "search_events",
            "list_client_venues",
            "create_organization",
            "create_client_venue",
            "publish_event",
            "update_event",
        }:
            return True
    return False


def _tool_id(service_id: str, method: str, path: str) -> str:
    slug = path.strip("/").replace("/", "-").replace("{", "").replace("}", "")
    slug = re.sub(r"[^a-zA-Z0-9_-]+", "-", slug)[:80]
    return f"{service_id}.{method}.{slug or 'root'}"


@lru_cache(maxsize=1)
def load_dynamic_tool_catalog() -> dict[str, DynamicTool]:
    tools: dict[str, DynamicTool] = {}
    for service in load_apex_services():
        service_id = str(service.get("id") or "")
        if not service_id:
            continue
        cache_path = OPENAPI_CACHE_DIR / f"{service_id}.json"
        if not cache_path.is_file():
            continue
        try:
            spec = json.loads(cache_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        paths = spec.get("paths") if isinstance(spec.get("paths"), dict) else {}
        demo_keys = _demo_operation_keys(service)
        base_env = str(service.get("base_url_env") or "")
        default_base = str(service.get("default_base_url") or "").rstrip("/")

        for path, methods in paths.items():
            if not isinstance(methods, dict):
                continue
            for method, detail in methods.items():
                m = method.lower()
                if m not in _HTTP_METHODS:
                    continue
                if not _path_allowed(service_id, m, path, demo_keys=demo_keys):
                    continue
                legacy = _legacy_intent_for_path(service_id, path, m)
                if not legacy:
                    continue
                if not isinstance(detail, dict):
                    detail = {}
                summary = str(detail.get("summary") or detail.get("operationId") or "")[:240]
                tags = tuple(str(t) for t in (detail.get("tags") or [])[:3])
                tid = _tool_id(service_id, m, path)
                if tid in tools:
                    tid = f"{tid}-{len(tools)}"
                tools[tid] = DynamicTool(
                    tool_id=tid,
                    service_id=service_id,
                    method=m,
                    path_template=path,
                    summary=summary,
                    legacy_intent=legacy,
                    base_url_env=base_env,
                    default_base_url=default_base,
                    operation_id=str(detail.get("operationId") or ""),
                    tags=tags,
                )
    return tools


def get_dynamic_tool(tool_id: str) -> DynamicTool | None:
    return load_dynamic_tool_catalog().get(tool_id)


def tool_catalog_for_prompt(*, max_tools: int = 48) -> str:
    lines = ["Dynamic tools (prefer tool_id + parameters over bare intent names):"]
    for tool in list(load_dynamic_tool_catalog().values())[:max_tools]:
        lines.append(f"- {tool.tool_id}: {tool.summary[:100] or tool.path_template} → {tool.legacy_intent}")
    extra = len(load_dynamic_tool_catalog()) - max_tools
    if extra > 0:
        lines.append(f"(+ {extra} more tools in catalog; same pattern tool_id + parameters JSON)")
    return "\n".join(lines)


def tool_catalog_for_orchestrator(
    question: str,
    *,
    classified_intent: str = "",
    semantic_intent_hint: str | None = None,
    max_tools: int = 14,
) -> str:
    """Small, question-relevant tool list — do not paste the full OpenAPI catalog into routing LLM."""
    catalog = load_dynamic_tool_catalog()
    if not catalog:
        return "Dynamic tools: (catalog empty — sync openapi cache)"

    picked: list[str] = []
    intent_hints: list[str] = []
    for raw in (classified_intent, semantic_intent_hint or "", preferred_legacy_intent(question) or ""):
        leg = str(raw or "").strip().lower()
        if leg and leg in INTENTS and leg not in intent_hints:
            intent_hints.append(leg)

    for leg in intent_hints:
        for tid, tool in catalog.items():
            if tool.legacy_intent == leg and tid not in picked:
                picked.append(tid)
            if len(picked) >= max_tools:
                break
        if len(picked) >= max_tools:
            break

    scored = dynamic_tool_scores(question)
    for tid, _score in sorted(scored.items(), key=lambda item: item[1], reverse=True):
        if tid in picked:
            continue
        tool = catalog.get(tid)
        if tool and tool_matches_question(tool, question):
            picked.append(tid)
        if len(picked) >= max_tools:
            break

    if len(picked) < min(6, max_tools):
        for tid, tool in catalog.items():
            if tid in picked:
                continue
            if tool.legacy_intent in ("marketing_events", "list_client_venues", "get_event"):
                picked.append(tid)
            if len(picked) >= max_tools:
                break

    lines = [
        "Dynamic tools (ranked subset for this turn — not the full catalog; "
        "debug: GET /api/tools):",
    ]
    for tid in picked[:max_tools]:
        tool = catalog[tid]
        lines.append(f"- {tool.tool_id}: {tool.summary[:90] or tool.path_template} → {tool.legacy_intent}")
    omitted = len(catalog) - len(picked)
    if omitted > 0:
        lines.append(f"(+ {omitted} other tools omitted from prompt to save context)")
    return "\n".join(lines)


def legacy_intent_for_tool_id(tool_id: str) -> str | None:
    tool = get_dynamic_tool(tool_id)
    return tool.legacy_intent if tool else None


def parameters_to_action_plan(tool: DynamicTool, parameters: dict[str, Any] | None, question: str) -> dict[str, Any]:
    """Merge LLM/host parameters into the action_plan shape execute_intent_api expects."""
    from apex_rag_demo.capability_routing import enrich_read_plan_from_question
    from apex_rag_demo.order_intent_helpers import extract_search_keyword

    params = dict(parameters or {})
    plan: dict[str, Any] = {"tool_id": tool.tool_id, **params}

    bare = strip_ui_region(question)
    if tool.legacy_intent in ("search_orders", "search_order_payment_statuses", "search_customers"):
        q = str(params.get("keyword") or params.get("searchValues") or extract_search_keyword(question))
        plan.setdefault("keyword", q)
        plan.setdefault("searchValues", q)
    if tool.legacy_intent == "search_events":
        plan.setdefault("query", str(params.get("query") or bare[:120]))
    if tool.legacy_intent == "get_event":
        eid = str(params.get("eventId") or "")
        if not eid:
            m = _UUID_RE.search(bare)
            if m:
                eid = m.group(0)
        if eid:
            plan["eventId"] = eid
    if tool.legacy_intent == "inventory_zones":
        eid = str(params.get("eventId") or "")
        if not eid:
            m = _UUID_RE.search(bare)
            if m:
                plan["eventId"] = m.group(0)
    if tool.legacy_intent == "marketing_events":
        plan.setdefault("pageSize", int(params.get("pageSize") or 25))
    if tool.legacy_intent == "get_venue_config":
        vid = str(params.get("venueConfigId") or "")
        if not vid:
            m = _UUID_RE.search(bare)
            if m:
                vid = m.group(0)
        if vid:
            plan["venueConfigId"] = vid
    if tool.legacy_intent == "b2b_flash_report":
        if "Sales/dateRange" in tool.path_template:
            plan.setdefault("flashReport", "sales_date_range")
        elif "TicketLifeCycle" in tool.path_template:
            plan.setdefault("flashReport", "ticket_lifecycle")
        elif "TicketInTransfer" in tool.path_template:
            plan.setdefault("flashReport", "ticket_in_transfer")
        else:
            plan.setdefault("flashReport", "sales_event")
    if tool.legacy_intent in ("b2b_flash_report", "reports_inventory_event"):
        from apex_rag_demo.reports_intent_helpers import enrich_reports_plan_from_question

        plan = enrich_reports_plan_from_question(tool.legacy_intent, plan, question)

    return enrich_read_plan_from_question(tool.legacy_intent, plan, question)


def embedding_texts_for_tool(tool: DynamicTool) -> list[str]:
    """Multiple lines per tool improve routing (still derived from OpenAPI + intent role)."""
    lines = [tool.description()]
    role_hints: dict[str, str] = {
        "marketing_events": (
            "List, browse, or count ticketed events in the marketing catalog. "
            "Show me events. Show events count. Last N events."
        ),
        "search_events": "Search events by name, artist, or festival in the search index.",
        "search_orders": "Find fan orders by customer email or order number only.",
        "search_customers": "Search fan customer accounts by email or name.",
        "list_client_venues": "List client venue registry (not the marketing events catalog).",
        "get_event": "Get one event by UUID from events API.",
        "inventory_zones": "Inventory zones and price levels for a specific event id.",
        "get_venue_config": "Manifest API venue configuration by venueConfigId UUID.",
        "b2b_flash_report": (
            "B2B flash sales, ticket lifecycle, or transfer reports. "
            "Show me reports for an event. Get me a report."
        ),
        "reports_inventory_event": "B2B inventory report for context id and event id.",
        "reports_timezones": "List timezones for flash reports.",
    }
    hint = role_hints.get(tool.legacy_intent)
    if hint:
        lines.append(f"{hint} {tool.method.upper()} {tool.path_template}")
    return lines


def tool_matches_question(tool: DynamicTool, question: str) -> bool:
    """Validators — like Cursor arg checks, not phrase regex lists."""
    from apex_rag_demo.order_intent_helpers import (
        looks_like_customer_search_request,
        looks_like_order_search_request,
    )
    from apex_rag_demo.intent_helpers import looks_like_list_events, looks_like_named_event_search

    bare = strip_ui_region(question)
    if tool.legacy_intent in ("search_orders", "search_order_payment_statuses"):
        return looks_like_order_search_request(bare)
    if tool.legacy_intent == "search_customers":
        return looks_like_customer_search_request(bare)
    if tool.legacy_intent == "search_events":
        from apex_rag_demo.agentic_event import looks_like_seat_inventory_demo

        if _UUID_RE.search(bare) and looks_like_seat_inventory_demo(bare):
            return False
        if looks_like_order_search_request(bare):
            return False
        return looks_like_named_event_search(bare) or (
            "search" in bare.lower() and not looks_like_list_events(bare)
        )
    if tool.legacy_intent == "marketing_events":
        if looks_like_order_search_request(bare):
            return False
        return True
    if tool.legacy_intent == "list_client_venues":
        from apex_rag_demo.agentic_event import looks_like_seat_inventory_demo

        if _UUID_RE.search(bare) and looks_like_seat_inventory_demo(bare):
            return False
        return "venue" in bare.lower() or "client venue" in bare.lower()
    if tool.legacy_intent == "get_event":
        from apex_rag_demo.reports_intent_helpers import looks_like_b2b_reports_question

        if looks_like_b2b_reports_question(question):
            return False
        return bool(_UUID_RE.search(bare)) or "get event" in bare.lower()
    if tool.legacy_intent == "inventory_zones":
        from apex_rag_demo.agentic_event import looks_like_seat_inventory_demo
        from apex_rag_demo.reports_intent_helpers import looks_like_b2b_reports_question

        if looks_like_b2b_reports_question(question):
            return False
        if not _UUID_RE.search(bare):
            return False
        if looks_like_seat_inventory_demo(bare):
            return True
        return bool(re.search(r"\binventory\s+zones?\b", bare, re.I))
    if tool.legacy_intent == "get_venue_config":
        from apex_rag_demo.reports_intent_helpers import looks_like_manifest_venue_config

        return looks_like_manifest_venue_config(question)
    if tool.legacy_intent in ("b2b_flash_report", "reports_inventory_event", "reports_timezones"):
        from apex_rag_demo.reports_intent_helpers import looks_like_b2b_reports_question

        return looks_like_b2b_reports_question(question)
    return True


DYNAMIC_TOOL_MIN_SCORE = 0.24
DYNAMIC_TOOL_MARGIN = 0.02


def preferred_legacy_intent(question: str) -> str | None:
    """Disambiguate when several tools score similarly (domain fit, not regex routing table)."""
    from apex_rag_demo.intent_helpers import (
        looks_like_list_events,
        looks_like_named_event_search,
        looks_like_onsale_or_event_count_question,
    )
    from apex_rag_demo.order_intent_helpers import (
        looks_like_customer_search_request,
        looks_like_order_search_request,
        looks_like_recent_search_list_request,
        parse_result_limit,
    )

    from apex_rag_demo.reports_intent_helpers import (
        looks_like_b2b_reports_question,
        resolve_reports_guard_intent,
    )

    bare = strip_ui_region(question)
    from apex_rag_demo.agentic_event import looks_like_seat_inventory_demo

    if _UUID_RE.search(bare) and looks_like_seat_inventory_demo(bare):
        return "get_event"
    if looks_like_b2b_reports_question(bare):
        resolved = resolve_reports_guard_intent(question)
        if resolved:
            return resolved
    if looks_like_order_search_request(bare):
        return "search_order_payment_statuses" if "payment status" in bare.lower() else "search_orders"
    if looks_like_customer_search_request(bare):
        return "search_customers"
    if looks_like_named_event_search(bare):
        return "search_events"
    if (
        looks_like_list_events(bare)
        or looks_like_onsale_or_event_count_question(bare)
        or looks_like_recent_search_list_request(bare)
        or parse_result_limit(bare) is not None
    ):
        return "marketing_events"
    return None


def resolve_dynamic_tool_id(question: str) -> str | None:
    """Best matching tool_id from OpenAPI descriptions (sentence-transformers)."""
    scored = dynamic_tool_scores(question)
    if not scored:
        return None
    ranked = sorted(scored.items(), key=lambda item: item[1], reverse=True)
    catalog = load_dynamic_tool_catalog()
    valid: list[tuple[str, float]] = []
    for tool_id, score in ranked:
        if score < DYNAMIC_TOOL_MIN_SCORE:
            break
        tool = catalog.get(tool_id)
        if tool and tool_matches_question(tool, question):
            valid.append((tool_id, score))
    if not valid:
        return None

    by_intent: dict[str, tuple[str, float]] = {}
    for tool_id, score in valid:
        leg = catalog[tool_id].legacy_intent
        if leg not in by_intent or score > by_intent[leg][1]:
            by_intent[leg] = (tool_id, score)

    prefer = preferred_legacy_intent(question)
    if prefer and prefer in by_intent:
        return by_intent[prefer][0]

    intent_ranked = sorted(by_intent.values(), key=lambda item: item[1], reverse=True)
    top_id, top_score = intent_ranked[0]
    if len(intent_ranked) > 1 and intent_ranked[1][1] >= top_score - DYNAMIC_TOOL_MARGIN:
        return None
    return top_id


def dynamic_tool_scores(question: str) -> dict[str, float]:
    bare = strip_ui_region(question).strip()
    if len(bare) < 3:
        return {}
    catalog = load_dynamic_tool_catalog()
    if not catalog:
        return {}
    from apex_rag_demo.semantic_message import embed_pooled_message
    from apex_rag_demo.rag.embeddings import embed_texts_inprocess

    q_vec = embed_pooled_message(bare)
    if not q_vec:
        return {}
    tools = list(catalog.values())
    all_texts: list[str] = []
    tool_index: list[str] = []
    for tool in tools:
        for line in embedding_texts_for_tool(tool):
            all_texts.append(line)
            tool_index.append(tool.tool_id)
    vectors = embed_texts_inprocess(all_texts, log_call=False)
    scored: dict[str, float] = {}
    for tid, vec in zip(tool_index, vectors, strict=True):
        from apex_rag_demo.intent_semantic import _cosine

        score = _cosine(q_vec, vec)
        scored[tid] = max(scored.get(tid, -1.0), score)
    return scored


def dynamic_tools_status() -> dict[str, Any]:
    catalog = load_dynamic_tool_catalog()
    intents = sorted({t.legacy_intent for t in catalog.values()})
    return {
        "enabled": dynamic_tools_enabled(),
        "tool_count": len(catalog),
        "legacy_intents": intents,
        "openapi_cache_dir": str(OPENAPI_CACHE_DIR),
    }


def dynamic_tools_enabled() -> bool:
    from apex_rag_demo.config import DYNAMIC_TOOLS_ENABLED

    return DYNAMIC_TOOLS_ENABLED
