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
    "list_users": "apex-resources-api",
    "create_organization": "apex-admin-api",
    "create_client_venue": "apex-admin-api",
    "get_event": "apex-events-api",
    "update_event": "apex-events-api",
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

    from apex_rag_demo.event_list import event_table_rows

    rows = event_table_rows(payload, include_state=True)
    if rows:
        label = "Events" if payload.get("events") else "Suggestions"
        lines.append(f"{label} ({len(rows)}):")
        for row in rows[:15]:
            lines.append(
                f"- {row['name']} | start {row.get('startDate', '—')} | end {row.get('endDate', '—')} "
                f"| {row.get('status', '—')} @ {row['venue']} (id {row['id']})",
            )
        return "\n".join(lines)

    lines.append("No events in this response. Try a longer query or POST /v1/events for full search.")
    return "\n".join(lines)


def format_search_customers(
    payload: dict[str, Any] | None,
    api_error: str | None,
    plan: dict[str, Any],
) -> str:
    q = plan.get("keyword") or plan.get("searchValues") or "?"
    if api_error:
        return _api_failure("apex-search-api", "POST /v1/customers", api_error)
    lines = [
        f"Customer search (axs-apex-search / POST /v1/customers), query: \"{q}\".",
        "Permission: b2b_search_customers (axs-b2b-control).",
        "",
    ]
    lines.extend(_mock_note(payload))
    if not payload:
        return "\n".join(lines + ["No response body."])
    customers = payload.get("customers") or payload.get("Customers") or []
    if not isinstance(customers, list):
        customers = []
    lines.append(f"Customers ({len(customers)}):")
    for c in customers[:20]:
        if not isinstance(c, dict):
            continue
        lines.append(
            f"- {c.get('customerName') or '—'} | {c.get('email') or '—'} | acct {c.get('accountNumber') or '—'}",
        )
    if not customers:
        lines.append("(empty — no matching customers in search index)")
    return "\n".join(lines)


def format_search_orders(
    payload: dict[str, Any] | None,
    api_error: str | None,
    plan: dict[str, Any],
) -> str:
    q = plan.get("keyword") or plan.get("searchValues") or "?"
    if api_error:
        return _api_failure("apex-search-api", "POST /v1/orders", api_error)
    lines = [
        f"Order search (axs-apex-search / search-api POST /v1/orders), query: \"{q}\".",
        "TestRail: C66084315 (authenticated search), C66084317+ (sort/payment ordering).",
        "",
    ]
    lines.extend(_mock_note(payload))
    if not payload:
        return "\n".join(lines + ["No response body."])
    orders = payload.get("orders") or payload.get("Orders") or []
    if not isinstance(orders, list):
        orders = []
    lines.append(f"Orders ({len(orders)}):")
    for o in orders[:20]:
        if not isinstance(o, dict):
            continue
        lines.append(
            f"- #{o.get('orderNumber') or o.get('orderId') or '—'} | "
            f"{o.get('customerName') or '—'} | {o.get('email') or '—'} | "
            f"payment {o.get('paymentStatus') or '—'}",
        )
    if not orders:
        lines.append("(empty — no matching orders in search index)")
    return "\n".join(lines)


def format_search_order_payment_statuses(
    payload: dict[str, Any] | None,
    api_error: str | None,
    plan: dict[str, Any],
) -> str:
    q = plan.get("keyword") or plan.get("searchValues") or "?"
    if api_error:
        return _api_failure("apex-search-api", "POST /v1/orders/list/payment-statuses", api_error)
    lines = [
        f"Order payment statuses (search-api POST /v1/orders/list/payment-statuses), query: \"{q}\".",
        "TestRail: C66084309–C66084314.",
        "",
    ]
    lines.extend(_mock_note(payload))
    if not payload:
        return "\n".join(lines + ["No response body."])
    statuses = payload.get("paymentStatuses") or payload.get("items") or payload
    lines.append(str(statuses)[:2000])
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


def format_list_users(payload: dict[str, Any] | None, api_error: str | None) -> str:
    if api_error:
        return _api_failure("apex-admin-api", "GET /v1/users/*", api_error)
    from apex_rag_demo.user_display import build_list_users_display

    view = build_list_users_display(payload)
    lines: list[str] = ["Users (resources-api GET /v1/Users):", ""]
    for para in view.get("paragraphs") or []:
        lines.append(str(para))
    lines.append("")
    lines.append(f"Users in table: {view.get('user_count', 0)}.")
    lines.append(f"Roles in catalog: {view.get('role_count', 0)}.")
    lines.append(f"Assignment rows: {view.get('assignment_count', 0)}.")
    lines.append("")
    lines.append("Sources:")
    for cite in view.get("citations") or []:
        lines.append(f"- {cite.get('label')} ({cite.get('status')})")
    return "\n".join(lines)


def format_create_organization(
    payload: dict[str, Any] | None,
    api_error: str | None,
) -> str:
    if api_error:
        return _api_failure("apex-admin-api", "POST /v1/organizations", api_error)
    if not payload:
        return "No response from admin-api."

    lines: list[str] = []
    if payload.get("_dry_run"):
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
) -> str:
    if api_error:
        return _api_failure("apex-admin-api", "POST /v1/client-venues", api_error)
    if not payload:
        return "No response from admin-api."

    lines: list[str] = []
    if payload.get("_dry_run"):
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
    from apex_rag_demo.event_list import event_display_name, event_state_label, unwrap_event_payload

    eid = plan.get("eventId") or "?"
    resolution = (payload or {}).get("_resolution") if isinstance(payload, dict) else None
    if resolution and resolution not in ("events_get", "events_get_via_search"):
        return None
    if api_error and resolution != "not_found":
        return None
    if api_error:
        return _api_failure("apex-events-api", f"GET /{eid}", api_error)
    if not payload:
        return "No response from events-api."

    ev = unwrap_event_payload(payload)
    lines = [f"Event detail (apex-events-api GET /{eid}):", ""]
    lines.extend(_mock_note(payload))

    name = event_display_name(ev)
    status = event_state_label(ev)
    if name:
        lines.append(f"Name: {name}")
    if status:
        lines.append(f"Status: {status}")
    if name == "—" and status == "—":
        lines.append("See fields returned:")
        for key in list(ev.keys())[:12]:
            if not key.startswith("_"):
                lines.append(f"- {key}: {ev[key]}")
    return "\n".join(lines)


def format_update_event(
    payload: dict[str, Any] | None,
    api_error: str | None,
    plan: dict[str, Any],
) -> str:
    eid = plan.get("eventId") or "?"
    if api_error:
        return _api_failure("apex-events-api", f"PUT /{eid}", api_error)
    if not payload:
        return "No response from events-api."

    lines: list[str] = []
    req = payload.get("request") or {}
    new_name = payload.get("headliners") or req.get("headliners") or plan.get("headliners")
    previous = payload.get("previousHeadliners") or req.get("_previousHeadliners") or "—"

    if payload.get("_dry_run"):
        lines.append("Dry-run — event was NOT updated on events-api.")
        lines.append(f"Would PUT: {payload.get('endpoint', f'/{eid}')}")
        lines.append(f"Event ID: {eid}")
        lines.append(f"Current title (headliners): {previous}")
        lines.append(f"New title (headliners): {new_name}")
        lines.append("Click Confirm in the chat UI to send the PUT.")
    elif payload.get("_updated"):
        lines.append("Event updated (apex-events-api PUT):")
        lines.append(f"Event ID: {eid}")
        lines.append(f"New title (headliners): {new_name}")
        after = payload.get("eventAfter") or {}
        from apex_rag_demo.event_list import event_display_name, unwrap_event_payload

        ev = unwrap_event_payload(after)
        if ev:
            lines.append(f"Verified name: {event_display_name(ev)}")
    else:
        lines.append("Update event response:")
        lines.append(f"Event ID: {eid}")
        lines.append(f"New title: {new_name}")

    lines.extend(_mock_note(payload))
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
        f"Event inventory (apex-inventory-api) for event {eid}:",
        "  GET /events/{id}/zones/primary",
        "  GET /events/{id}/zones/publish-data",
        "  GET /zones/{zoneId}/ticket-types",
        "",
    ]
    lines.extend(_mock_note(payload))

    from apex_rag_demo.inventory_display import build_inventory_sections

    for block in build_inventory_sections(payload):
        title = block.get("title") or "Section"
        lines.append(f"{title}:")
        for field in block.get("fields") or []:
            lines.append(f"  {field.get('label')}: {field.get('value')}")
        table = block.get("table") or {}
        for row in (table.get("rows") or [])[:15]:
            if isinstance(row, dict):
                bits = ", ".join(f"{k}={v}" for k, v in row.items() if v and v != "—")
                lines.append(f"  - {bits}")
        for para in block.get("paragraphs") or []:
            lines.append(f"  {para}")
        lines.append("")

    if payload.get("_fetch_errors"):
        lines.append("Fetch notes:")
        for err in payload["_fetch_errors"]:
            lines.append(f"- {err}")

    return "\n".join(lines).strip()


def format_marketing_events(
    payload: dict[str, Any] | None,
    api_error: str | None,
    *,
    question: str = "",
) -> str:
    if api_error:
        msg = _api_failure("apex-marketing-api", "GET /v1/events", api_error)
        if "403" in api_error:
            msg += (
                "\n\nMarketing API is often role-restricted. "
                "The app will try Search API fallback when possible; "
                'otherwise use "Search events matching <name>".'
            )
        return msg
    if not payload:
        return "No response from marketing-api."

    from apex_rag_demo.event_list import event_table_rows

    via_search = payload.get("_source") == "search-api-fallback"
    if via_search:
        lines = [
            "Events via search-api fallback (Marketing GET /v1/events was denied):",
            f'Query: "{payload.get("_fallback_query", "event")}"',
            "",
        ]
    else:
        lines = ["Marketing events (apex-marketing-api GET /v1/events):", ""]
    lines.extend(_mock_note(payload))

    from apex_rag_demo.event_query_helpers import wants_event_names_only

    from apex_rag_demo.event_enrichment import partition_event_table_rows

    from apex_rag_demo.ui_schema import project_event_rows, resolve_event_list_columns

    list_columns = resolve_event_list_columns(question)
    all_rows = event_table_rows(payload)
    rows, incomplete = partition_event_table_rows(all_rows)
    rows = project_event_rows(rows, list_columns)
    names_only = wants_event_names_only(strip_ui_region(question))
    bare_q = strip_ui_region(question).lower()
    lf = payload.get("_lifecycle_filter") if isinstance(payload.get("_lifecycle_filter"), dict) else None
    if re.search(r"\bhow many\b|\bcount\b", bare_q) and "event" in bare_q:
        if lf and lf.get("_matched") is not None:
            lines.append(
                f"Events matching on-sale filter: {lf['_matched']} "
                f"(of {lf.get('_total_before_filter')} in the fetched page).",
            )
        else:
            lines.append(f"Total displayable events: {len(rows)} (from the API page fetched).")
    if incomplete:
        lines.append(
            f"Hidden {len(incomplete)} ID-only marketing row(s) without display names (not usable for follow-up).",
        )
    enrich = payload.get("_event_enrichment")
    if isinstance(enrich, dict) and enrich.get("resolved_names"):
        lines.append(f"Names hydrated from events-api: {enrich['resolved_names']}.")
    if rows:
        lines.append(f"Events ({len(rows)}):")
        for row in rows[:20]:
            if names_only:
                lines.append(f"- {row['name']}")
                continue
            venue = row.get("venue")
            if venue and venue != "—":
                lines.append(f"- {row['name']} @ {venue} (id {row['id']})")
            else:
                lines.append(f"- {row['name']} (id {row['id']})")
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
        return WELCOME_SUMMARY

    if is_general_help_question(bare):
        return format_help_text()

    from apex_rag_demo.fan_purchase import format_fan_purchase_guidance, looks_like_fan_purchase_request
    if looks_like_fan_purchase_request(bare):
        return format_fan_purchase_guidance(bare)

    from apex_rag_demo.api_guidance import explain_need_api_prompt

    return explain_need_api_prompt(bare, kb_snippets or [])


def format_deterministic(
    intent: str,
    question: str,
    payload: dict[str, Any] | None,
    api_error: str | None,
    *,
    action_plan: dict[str, Any] | None = None,
    kb_snippets: list[str] | None = None,
) -> str | None:
    """Agent-style replies: API facts only, no internal prompt leakage."""
    plan = action_plan or {}

    if intent == "explain":
        return format_explain(kb_snippets or [], question)

    if intent == "search_events":
        return format_search_events(question, payload, api_error, plan)
    if intent == "search_customers":
        return format_search_customers(payload, api_error, plan)
    if intent == "search_orders":
        return format_search_orders(payload, api_error, plan)
    if intent == "search_order_payment_statuses":
        return format_search_order_payment_statuses(payload, api_error, plan)
    if intent == "list_client_venues":
        return format_list_client_venues(question, payload, api_error)
    if intent == "list_users":
        return format_list_users(payload, api_error)
    if intent == "create_organization":
        return format_create_organization(payload, api_error)
    if intent == "create_client_venue":
        return format_create_client_venue(payload, api_error)
    if intent == "update_event":
        return format_update_event(payload, api_error, plan or {})

    from apex_rag_demo.crud_formatters import format_crud_mutation
    from apex_rag_demo.crud_policy import write_kind_for_intent, WriteKind

    if write_kind_for_intent(intent) not in (WriteKind.READ, WriteKind.CREATE) or intent in (
        "create_event",
        "publish_event",
        "create_marketing_pixel",
        "create_inventory_zone",
        "reset_inventory_publish",
        "list_marketing_pixels",
        "delete_event",
        "delete_marketing_pixel",
        "update_organization",
        "update_client_venue",
        "update_marketing_pixel",
    ):
        if intent not in ("create_organization", "create_client_venue", "update_event", "explain"):
            formatted = format_crud_mutation(intent, payload, api_error, plan)
            if formatted:
                return formatted
    if intent == "get_event":
        if api_error:
            return format_get_event(payload, api_error, plan)
        if not plan.get("eventId"):
            return (
                "I need an event UUID to call apex-events-api (GET /{eventId}). "
                "Example: get event 8f0a2f5c-9f45-4a7e-93f2-2f6a3f1f2b10"
            )
        from apex_rag_demo.inventory_assessment import (
            format_price_code_setup_answer,
            looks_like_price_code_setup_question,
        )

        bare = strip_ui_region(question)
        if plan.get("includeInventory") and looks_like_price_code_setup_question(bare):
            inv = (payload or {}).get("_inventory") if isinstance(payload, dict) else None
            return format_price_code_setup_answer(payload, inv, str(plan.get("eventId")))
        return format_get_event(payload, api_error, plan)
    if intent == "inventory_zones":
        if api_error:
            return format_inventory_zones(payload, api_error, plan)
        if not plan.get("eventId"):
            return (
                "I need an event UUID for apex-inventory-api "
                "(GET /events/{eventId}/zones/primary)."
            )
        from apex_rag_demo.inventory_assessment import (
            format_price_code_setup_answer,
            looks_like_price_code_setup_question,
        )

        if looks_like_price_code_setup_question(strip_ui_region(question)):
            return format_price_code_setup_answer(None, payload, str(plan.get("eventId")))
        return format_inventory_zones(payload, api_error, plan)
    if intent == "marketing_events":
        return format_marketing_events(payload, api_error, question=question)

    if api_error:
        svc = _FORMATTERS.get(intent, "API")
        return f"{svc} error: {api_error}"
    return None


def summarize_with_llm(question: str, api_block: str) -> str:
    """Last resort when no formatter applies."""
    from apex_rag_demo.llm_synthesis import synthesize_apex_answer

    return synthesize_apex_answer(
        question,
        "unknown",
        api_payload={"raw": api_block},
        api_error=None,
        kb_snippets=None,
        action_plan=None,
    )
