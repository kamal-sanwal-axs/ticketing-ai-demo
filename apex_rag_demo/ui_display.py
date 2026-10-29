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
from apex_rag_demo.event_query_helpers import wants_event_names_only
from apex_rag_demo.event_list import (
    CLIENT_VENUE_HIERARCHY_TABLE_COLUMNS,
    EVENT_HIERARCHY_TABLE_COLUMNS,
    EVENT_NAME_ONLY_TABLE_COLUMNS,
    client_venue_table_rows,
    event_display_name,
    event_start_end_labels,
    event_state_label,
    event_table_rows,
    hierarchy_footnote,
    unwrap_event_payload,
)
from apex_rag_demo.crud_policy import requires_human_confirmation, write_kind_for_intent
from apex_rag_demo.event_context_display import build_resolved_id_display
from apex_rag_demo.inventory_assessment import build_inventory_assessment, looks_like_price_code_setup_question
from apex_rag_demo.inventory_display import build_inventory_sections
from apex_rag_demo.user_display import build_list_users_display
from apex_rag_demo.org_hierarchy import get_hierarchy_index, hierarchy_for_event_list
from apex_rag_demo.response_formatters import parse_ui_region, strip_ui_region


def _badge(intent: str) -> str:
    return intent.replace("_", " ")


def _note_mock(payload: dict[str, Any] | None) -> str | None:
    if payload and payload.get("_mock"):
        return "Sample data (mock or missing token)."
    return None


def build_ui_display(state: dict[str, Any]) -> dict[str, Any] | None:
    from apex_rag_demo.compound_request import build_compound_display

    compound_ui = build_compound_display(state)
    if compound_ui:
        return compound_ui

    from apex_rag_demo.reports_display import build_reports_manifest_display

    reports_ui = build_reports_manifest_display(
        state.get("intent") or "explain",
        state.get("api_payload") if isinstance(state.get("api_payload"), dict) else None,
        state.get("action_plan") or {},
        state.get("api_error"),
    )
    if reports_ui:
        return reports_ui

    pipeline_error = state.get("pipeline_error")
    if isinstance(pipeline_error, dict) and pipeline_error.get("title"):
        from apex_rag_demo.pipeline_errors import pipeline_error_display

        return pipeline_error_display(pipeline_error)

    intent = state.get("intent") or "explain"
    payload = state.get("api_payload")
    api_error = state.get("api_error")
    question = state.get("question") or ""
    plan = state.get("action_plan") or {}
    kb = state.get("kb_snippets") or []
    from apex_rag_demo.crud_policy import is_dry_run_payload

    if isinstance(payload, dict) and payload.get("_pending_confirmation"):
        preview = payload.get("preview") or {}
        plan = state.get("action_plan") or {}
        return {
            "type": "article",
            "title": "Confirm before sending",
            "subtitle": f"{write_kind_for_intent(intent).value} · {intent}",
            "badge": _badge(intent),
            "level": "warning",
            "paragraphs": [
                payload.get("message") or "This change needs your approval.",
                preview.get("summary") or "",
            ],
            "fields": [
                {"label": "Intent", "value": intent},
                {"label": "Write kind", "value": write_kind_for_intent(intent).value},
                {"label": "Plan", "value": str(plan)},
            ],
            "pending_confirmation": {
                "mutation_token": payload.get("mutation_token"),
                "requires_confirm": requires_human_confirmation(intent),
            },
        }

    if intent == "get_event" and isinstance(payload, dict):
        resolved = build_resolved_id_display(payload, plan, api_error)
        if resolved:
            return resolved

    if api_error and intent == "publish_event" and isinstance(payload, dict) and payload.get("_mutation_error"):
        ctx = payload.get("publishContext") if isinstance(payload.get("publishContext"), dict) else {}
        detail = str(ctx.get("apiDetail") or payload.get("detail") or "")
        status = int(ctx.get("httpStatus") or payload.get("httpStatus") or 0)
        eid = (plan.get("eventId") or (payload.get("plan") or {}).get("eventId") or "—")
        snap = payload.get("eventSnapshot")
        ev = unwrap_event_payload(snap) if isinstance(snap, dict) else {}
        event_state = str(ctx.get("eventState") or event_state_label(ev) if ev else "—")
        from apex_rag_demo.http_errors import classify_publish_conflict

        if not ctx:
            classified = classify_publish_conflict(
                http_status=status,
                api_detail=detail,
                api_code=str(payload.get("errorCode") or ""),
                event_state=event_state if event_state != "—" else None,
            )
            paragraphs = classified.paragraphs()
            title = classified.headline
            reason_label = classified.reason_code.replace("_", " ")
        else:
            paragraphs = [
                str(ctx.get("meaning") or ""),
                f"Events-api detail: {detail}" if detail else "",
            ]
            paragraphs = [p for p in paragraphs if p]
            if ctx.get("nextSteps"):
                paragraphs.append("What to do:")
                paragraphs.extend(f"• {s}" for s in ctx["nextSteps"])
            title = str(ctx.get("headline") or "Publish not applied")
            reason_label = str(ctx.get("reasonCode") or "conflict").replace("_", " ")

        fields = [
            {"label": "Reason", "value": reason_label},
            {"label": "Event ID", "value": eid},
            {"label": "HTTP status", "value": str(status or "—")},
            {"label": "API detail", "value": detail or "—"},
            {"label": "Current state (GET)", "value": event_state},
            {"label": "Event name", "value": event_display_name(ev) if ev else "—"},
        ]
        return {
            "type": "article",
            "title": title,
            "subtitle": f"events-api POST /{eid}/publish · HTTP {status}",
            "badge": _badge(intent),
            "level": "warning",
            "paragraphs": paragraphs,
            "fields": fields,
            "citations": [
                {
                    "label": f"events-api POST /{eid}/publish",
                    "href": f"https://api.apex-dev.axsdevops.io/events/{eid}/publish",
                    "status": f"HTTP {status}",
                },
                {
                    "label": f"events-api GET /{eid}",
                    "href": f"https://api.apex-dev.axsdevops.io/events/{eid}",
                    "status": "current event record",
                },
            ],
        }

    if api_error:
        paragraphs = [str(api_error)]
        if intent == "marketing_events" and "403" in str(api_error):
            paragraphs.extend(
                [
                    "Marketing GET /v1/events returned Forbidden — this JWT often lacks marketing API scope in apex-dev.",
                    "Try Search instead: “Search events matching Splash House”. "
                    "Ask your tenant admin for marketing API access if you need the full marketing catalog.",
                ],
            )
        return {
            "type": "article",
            "title": "Request failed",
            "badge": _badge(intent),
            "level": "error",
            "paragraphs": paragraphs,
        }

    if intent == "list_users":
        view = build_list_users_display(payload if isinstance(payload, dict) else None)
        return {
            "type": "article",
            "title": "Users",
            "subtitle": "resources-api GET /v1/Users · admin roles & assignments supplement",
            "badge": _badge(intent),
            "footnote": _note_mock(payload),
            "paragraphs": view.get("paragraphs") or [],
            "sections": view.get("sections") or [],
            "citations": view.get("citations") or [],
        }

    if intent == "list_client_venues":
        region = parse_ui_region(question) or "US-West"
        hierarchy = get_hierarchy_index()
        rows = client_venue_table_rows(payload, hierarchy=hierarchy)
        footnote = _note_mock(payload) or hierarchy_footnote(hierarchy)
        return {
            "type": "table",
            "title": "Client venues (org → client → venue)",
            "subtitle": f"Search API · UI region {region} (preference only, not an API filter)",
            "badge": _badge(intent),
            "footnote": footnote,
            "count": len(rows),
            "columns": CLIENT_VENUE_HIERARCHY_TABLE_COLUMNS,
            "rows": rows,
        }

    if intent == "search_events":
        from apex_rag_demo.ui_schema import (
            project_event_rows,
            resolve_event_list_columns,
            wants_org_hierarchy_in_event_list,
        )

        query = plan.get("query") or "—"
        p = payload or {}
        via_full = p.get("_search_via") == "post-events"
        use_hierarchy = wants_org_hierarchy_in_event_list(question)
        hierarchy = hierarchy_for_event_list(use_hierarchy)
        list_columns = resolve_event_list_columns(question)
        rows = project_event_rows(
            event_table_rows(p, include_state=True, hierarchy=hierarchy),
            list_columns,
        )
        total = p.get("totalResults")
        subtitle = (
            f'Search API POST /v1/events · query: "{query}"'
            if via_full
            else f'Search API POST /v1/events/suggest · query: "{query}"'
        )
        if total is not None:
            subtitle += f" · {total} total match(es)"
        return {
            "type": "table" if rows else "article",
            "title": "Event search",
            "subtitle": subtitle,
            "badge": _badge(intent),
            "footnote": _note_mock(payload) or (hierarchy_footnote(hierarchy) if use_hierarchy else None),
            "count": len(rows),
            "columns": list_columns,
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

    if intent == "search_customers":
        p = payload or {}
        q = plan.get("keyword") or plan.get("searchValues") or "—"
        customers = p.get("customers") or p.get("Customers") or []
        if not isinstance(customers, list):
            customers = []
        rows = []
        for c in customers[:50]:
            if not isinstance(c, dict):
                continue
            rows.append(
                {
                    "accountNumber": str(c.get("accountNumber") or "—"),
                    "customerName": str(c.get("customerName") or "—"),
                    "email": str(c.get("email") or "—"),
                    "client": str(c.get("client") or c.get("clientName") or "—"),
                },
            )
        return {
            "type": "table" if rows else "article",
            "title": "Customers (search)",
            "subtitle": f'axs-apex-search · POST /v1/customers · "{q}"',
            "badge": _badge(intent),
            "footnote": _note_mock(payload),
            "count": len(rows),
            "columns": [
                {"key": "accountNumber", "label": "Account #"},
                {"key": "customerName", "label": "Name"},
                {"key": "email", "label": "Email"},
                {"key": "client", "label": "Client"},
            ],
            "rows": rows,
            "paragraphs": (["No customers matched."] if not rows else []),
        }

    if intent in ("search_orders", "search_order_payment_statuses"):
        p = payload or {}
        q = plan.get("keyword") or plan.get("searchValues") or "—"
        orders = p.get("orders") or p.get("Orders") or []
        if not isinstance(orders, list):
            orders = []
        rows = []
        for o in orders[:50]:
            if not isinstance(o, dict):
                continue
            rows.append(
                {
                    "orderNumber": str(o.get("orderNumber") or o.get("orderId") or "—"),
                    "customerName": str(o.get("customerName") or "—"),
                    "email": str(o.get("email") or "—"),
                    "paymentStatus": str(o.get("paymentStatus") or "—"),
                },
            )
        endpoint = (
            "POST /v1/orders/list/payment-statuses"
            if intent == "search_order_payment_statuses"
            else "POST /v1/orders"
        )
        return {
            "type": "table" if rows else "article",
            "title": "Orders (search)" if intent == "search_orders" else "Order payment statuses",
            "subtitle": f'axs-apex-search · Search API {endpoint} · "{q}"',
            "badge": _badge(intent),
            "footnote": _note_mock(payload),
            "count": len(rows),
            "columns": [
                {"key": "orderNumber", "label": "Order #"},
                {"key": "customerName", "label": "Customer"},
                {"key": "email", "label": "Email"},
                {"key": "paymentStatus", "label": "Payment"},
            ],
            "rows": rows,
            "paragraphs": (
                ["No orders matched. Try email, order number, or customer name."]
                if not rows and intent == "search_orders"
                else []
            ),
        }

    if intent == "marketing_events":
        p = payload or {}
        via_search = p.get("_source") == "search-api-fallback"
        hierarchy = get_hierarchy_index()
        from apex_rag_demo.event_enrichment import partition_event_table_rows

        from apex_rag_demo.ui_schema import (
            build_events_timeline_chart,
            project_event_rows,
            resolve_event_list_columns,
            wants_event_timeline_chart,
        )

        from apex_rag_demo.ui_schema import wants_org_hierarchy_in_event_list

        list_columns = resolve_event_list_columns(question)
        use_hierarchy = wants_org_hierarchy_in_event_list(question)
        hierarchy_index = hierarchy_for_event_list(use_hierarchy)
        all_rows = event_table_rows(p, hierarchy=hierarchy_index)
        rows, incomplete_rows = partition_event_table_rows(all_rows)
        rows = project_event_rows(rows, list_columns)
        names_only = list_columns == EVENT_NAME_ONLY_TABLE_COLUMNS
        enrich_meta = p.get("_event_enrichment") if isinstance(p.get("_event_enrichment"), dict) else None
        date_meta = p.get("_date_filter") if isinstance(p.get("_date_filter"), dict) else None
        date_note = ""
        if date_meta and date_meta.get("description"):
            matched = date_meta.get("_matched")
            total = date_meta.get("_total_before_filter")
            date_note = str(date_meta.get("description"))
            if matched is not None and total is not None:
                date_note += f" — showing {matched} of {total} fetched row(s) by start date."
        if via_search:
            subtitle = (
                f'Search API POST /v1/events (fallback — Marketing returned '
                f'{p.get("_marketing_status", 403)}) · query: "{p.get("_fallback_query", "event")}"'
            )
            if date_note:
                subtitle += f" · Filter: {date_note}"
            footnote = (
                "Your token cannot call Marketing /v1/events; showing search index matches instead. "
                "Date filters apply to start dates on the fetched page (increase pageSize in plan for more coverage). "
                'For name lookup use “Search events matching <name>”.'
            )
            title = "Events (search fallback)" if names_only else "Events (search fallback)"
            columns = list_columns
            display_rows = rows
        else:
            subtitle = (
                "Marketing API GET /v1/events — ticketed events, not client-venue registry "
                "(use “list client venues” for venues)"
            )
            if date_note:
                subtitle += f" · Filter: {date_note}"
            footnote = _note_mock(payload) or (hierarchy_footnote(hierarchy) if use_hierarchy else None)
            title = "Events" if not names_only else "Event names"
            columns = list_columns
            display_rows = rows

        charts: list[dict[str, Any]] = []
        if wants_event_timeline_chart(question) or (date_meta and rows):
            chart = build_events_timeline_chart(rows)
            if chart:
                charts.append(chart)

        paragraphs: list[str] = []
        if not display_rows:
            paragraphs.append(
                "No events matched the date filter on the fetched catalog."
                if date_meta
                else "No events with display names returned.",
            )
        if incomplete_rows:
            paragraphs.append(
                f"{len(incomplete_rows)} marketing row(s) had only an event ID (no title/headliners) "
                "and are hidden — they cannot be used for chat follow-up until events-api returns a name.",
            )
        if enrich_meta and enrich_meta.get("resolved_names"):
            paragraphs.append(
                f"Hydrated {enrich_meta['resolved_names']} name(s) from events-api "
                f"({enrich_meta.get('description', '')}).",
            )

        sections: list[dict[str, Any]] = []
        if incomplete_rows:
            sections.append(
                {
                    "title": "Hidden — ID only (not usable)",
                    "paragraphs": [
                        "These IDs were in the marketing catalog without a display name. "
                        "Use get event <uuid> after fixing data in Events, or search events matching <name>.",
                    ],
                    "table": {
                        "columns": [
                            {"key": "id", "label": "Event ID"},
                            {"key": "dataQuality", "label": "Issue"},
                        ],
                        "rows": [
                            {
                                "id": r.get("id", "—"),
                                "dataQuality": r.get("dataQuality", "ID only"),
                            }
                            for r in incomplete_rows[:50]
                        ],
                    },
                },
            )

        layout_type = "dashboard" if charts and display_rows else ("table" if display_rows else "article")
        return {
            "type": layout_type,
            "title": title,
            "subtitle": subtitle,
            "badge": _badge(intent),
            "footnote": footnote,
            "count": len(display_rows),
            "columns": columns,
            "rows": display_rows,
            "charts": charts,
            "paragraphs": paragraphs,
            "sections": sections,
        }

    if intent == "inventory_zones":
        eid = plan.get("eventId") or "—"
        inv_sections = build_inventory_sections(payload)
        return {
            "type": "article",
            "title": "Event inventory",
            "subtitle": (
                f"Inventory API · event {eid} · primary zone, price levels, sections, "
                "price codes, seat selection"
            ),
            "badge": _badge(intent),
            "footnote": _note_mock(payload),
            "sections": inv_sections,
        }

    if intent == "get_event":
        from apex_rag_demo.id_prompts import resolve_event_id

        resolved = resolve_event_id(
            question,
            plan,
            state.get("session_focus"),
        )
        if not plan.get("eventId") and resolved:
            plan = {**plan, "eventId": resolved}
        eid = plan.get("eventId") or resolved or "—"
        if not (plan.get("eventId") or resolved):
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
        ev = unwrap_event_payload(payload)
        venue = (ev.get("venue") or {}) if isinstance(ev.get("venue"), dict) else {}
        client = (ev.get("client") or {}) if isinstance(ev.get("client"), dict) else {}
        start_date, end_date = event_start_end_labels(ev)
        include_org = bool(plan.get("includeOrgHierarchy"))
        include_inv = bool(plan.get("includeInventory"))
        hierarchy = hierarchy_for_event_list(include_org)
        chain = hierarchy.for_event(ev) if ev else hierarchy.for_client_venue_id(None)
        if not include_org and ev:
            chain = {
                **chain,
                "client": chain["client"]
                if chain["client"] != "—"
                else str((client or {}).get("name") or "—"),
                "clientVenue": chain["clientVenue"]
                if chain["clientVenue"] != "—"
                else str((venue or {}).get("name") or "—"),
                "clientVenueId": str(ev.get("clientVenueId") or "—"),
            }
        inv_payload = (payload or {}).get("_inventory") if isinstance(payload, dict) else None
        inv_sections = build_inventory_sections(inv_payload) if include_inv and inv_payload else []
        subtitle = f"Events API GET /{eid}"
        if include_inv:
            subtitle += " · with inventory snapshot"
        else:
            subtitle += " · event record only (say “with inventory” to include zones and price levels)"
        footnote = _note_mock(payload)
        if include_org:
            footnote = footnote or hierarchy_footnote(hierarchy)
        bare_q = strip_ui_region(question)
        assessment = None
        if include_inv and inv_payload and looks_like_price_code_setup_question(bare_q):
            assessment = build_inventory_assessment(payload, inv_payload, str(eid))
        title = event_display_name(ev) if ev else "Event"
        if assessment:
            title = assessment["headline"]
        from apex_rag_demo.ui_schema import build_get_event_fields

        event_fields, org_sections = build_get_event_fields(
            ev or {},
            eid=str(eid),
            include_org=include_org,
            chain=chain,
            client=client if isinstance(client, dict) else {},
            venue=venue if isinstance(venue, dict) else {},
            start_date=start_date,
            end_date=end_date,
            status=event_state_label(ev),
            name=event_display_name(ev),
        )
        trace_sections: list[dict[str, Any]] = []
        api_trace = state.get("api_trace") if isinstance(state.get("api_trace"), list) else []
        from apex_rag_demo.ui_schema import orchestration_trace_sections

        trace_sections = orchestration_trace_sections(api_trace)
        return {
            "type": "article",
            "title": title,
            "subtitle": subtitle,
            "badge": _badge(intent),
            "footnote": footnote,
            "paragraphs": (assessment or {}).get("paragraphs") or [],
            "citations": (assessment or {}).get("citations") or [],
            "fields": event_fields,
            "sections": trace_sections + org_sections + inv_sections,
        }

    if intent == "update_event":
        p = payload or {}
        req = p.get("request") or {}
        dry = is_dry_run_payload(p)
        eid = plan.get("eventId") or p.get("eventId") or "—"
        new_name = p.get("headliners") or req.get("headliners") or plan.get("headliners") or "—"
        previous = p.get("previousHeadliners") or req.get("_previousHeadliners") or "—"
        after = p.get("eventAfter")
        verified = "—"
        if after:
            ev = unwrap_event_payload(after)
            verified = event_display_name(ev) if ev else "—"
        return {
            "type": "article",
            "title": "Update event name",
            "subtitle": f"Events API PUT /{eid}",
            "badge": _badge(intent),
            "level": "warning" if dry else "info",
            "footnote": _note_mock(payload),
            "fields": [
                {"label": "Mode", "value": "Dry-run (not sent)" if dry else "Live PUT"},
                {"label": "Event ID", "value": eid},
                {"label": "Previous title", "value": previous},
                {"label": "New title (headliners)", "value": new_name},
                {"label": "Verified after update", "value": verified if not dry else "—"},
            ],
            "paragraphs": (
                [
                    "Dry-run preview only. Click Confirm to apply this change in apex-dev.",
                ]
                if dry
                else []
            ),
        }

    if intent == "create_organization":
        p = payload or {}
        req = p.get("request") or {}
        dry = is_dry_run_payload(p)
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
        dry = is_dry_run_payload(p)
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
        from apex_rag_demo.fan_purchase import build_fan_purchase_display, looks_like_fan_purchase_request
        if looks_like_fan_purchase_request(bare):
            return build_fan_purchase_display()
        from apex_rag_demo.api_guidance import explain_need_api_prompt

        line = explain_need_api_prompt(bare, kb)
        return {
            "type": "article",
            "title": "Need a clearer request",
            "badge": _badge(intent),
            "level": "warning",
            "paragraphs": [line],
        }

    return {
        "type": "article",
        "title": "Response",
        "badge": _badge(intent),
        "paragraphs": [state.get("answer") or ""],
    }
