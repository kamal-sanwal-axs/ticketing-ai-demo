from __future__ import annotations

from typing import Any

from apex_rag_demo.clients import apex_admin, apex_inventory, apex_marketing, apex_search
from apex_rag_demo.crud_consent import consent_allows_execution
from apex_rag_demo.crud_execute import execute_crud_intent
from apex_rag_demo.crud_policy import WriteKind, mutation_executes_live, write_kind_for_intent
from apex_rag_demo.event_resolve import get_event_with_context


def execute_intent_api(
    intent: str,
    plan: dict[str, Any],
    *,
    question: str,
    search_query: str = "",
    mutations_dry_run: bool = False,
    confirm_mutation: bool = False,
    mutation_token: str | None = None,
) -> dict[str, Any]:
    """Run one APEX API intent; returns api_payload, api_error, optional pipeline_error."""

    def dry_run_for(api_intent: str) -> bool:
        return not mutation_executes_live(
            api_intent,
            confirm_mutation=confirm_mutation,
            mutations_dry_run=mutations_dry_run,
        )
    try:
        if intent == "search_customers":
            from apex_rag_demo.clients.apex_search import search_customers

            keyword = plan.get("keyword") or plan.get("searchValues") or search_query
            payload = search_customers(
                keyword=str(keyword) if keyword else None,
                search_values=str(plan.get("searchValues") or keyword or "") or None,
                page_size=int(plan.get("pageSize") or 25),
            )
            return {"api_payload": payload, "api_error": None}

        if intent == "search_orders":
            from apex_rag_demo.clients.apex_search import search_orders
            from apex_rag_demo.order_intent_helpers import order_search_precheck

            keyword = plan.get("keyword") or plan.get("searchValues") or search_query
            search_values = plan.get("searchValues") or keyword
            guidance = order_search_precheck(
                question,
                str(keyword) if keyword else None,
                str(search_values) if search_values else None,
            )
            if guidance:
                return {
                    "api_payload": None,
                    "api_error": None,
                    "answer": guidance,
                    "memory_source": "order_search_guidance",
                }
            payload = search_orders(
                keyword=str(keyword) if keyword else None,
                search_values=str(search_values or "") or None,
                page_size=int(plan.get("pageSize") or 25),
            )
            return {"api_payload": payload, "api_error": None}

        if intent == "search_order_payment_statuses":
            from apex_rag_demo.clients.apex_search import search_order_payment_statuses

            keyword = plan.get("keyword") or plan.get("searchValues") or search_query
            payload = search_order_payment_statuses(
                keyword=str(keyword) if keyword else None,
                search_values=str(plan.get("searchValues") or keyword or "") or None,
            )
            return {"api_payload": payload, "api_error": None}

        if intent == "search_events":
            from apex_rag_demo.event_lifecycle_filters import (
                apply_lifecycle_filter_to_payload,
                enrich_marketing_plan_from_question,
            )

            plan = enrich_marketing_plan_from_question(plan, question)
            query = plan.get("query") or search_query
            payload = apex_search.search_events_suggest(query)
            events = payload.get("events") if payload else None
            if events is None:
                events = []
            suggestions = (payload or {}).get("suggestions") or (payload or {}).get("Suggestions") or []
            if not events and not suggestions:
                payload = apex_search.search_events(query, page_size=25)
                payload["_search_via"] = "post-events"
            payload = apply_lifecycle_filter_to_payload(
                payload,
                lifecycle_filter=plan.get("lifecycleFilter"),
            )
            return {"api_payload": payload, "api_error": None}

        if intent == "list_client_venues":
            payload = apex_search.search_client_venues(
                page_size=int(plan.get("pageSize") or 25),
                organization_ids=plan.get("organizationIds") or None,
            )
            return {"api_payload": payload, "api_error": None}

        if intent == "list_users":
            from apex_rag_demo.auth import decode_jwt_payload
            from apex_rag_demo.clients.http_common import get_bearer_token

            claims = decode_jwt_payload(get_bearer_token())
            override = str(plan.get("adminUserId") or "").strip() or None
            payload = apex_admin.list_users_admin_snapshot(
                admin_user_id=override,
                jwt_claims=claims,
                user_search=str(plan.get("search") or "").strip() or None,
                users_limit=int(plan.get("limit") or 50),
                users_offset=int(plan.get("offset") or 0),
            )
            return {"api_payload": payload, "api_error": None}

        if intent == "create_organization":
            body = apex_admin.build_create_organization_body(plan)
            payload = apex_admin.create_organization(body, dry_run=dry_run_for(intent))
            return {"api_payload": payload, "api_error": None}

        if intent == "create_client_venue":
            body = apex_admin.build_create_client_venue_body(plan)
            payload = apex_admin.create_client_venue(body, dry_run=dry_run_for(intent))
            return {"api_payload": payload, "api_error": None}

        if intent == "list_marketing_pixels":
            payload = apex_marketing.list_pixels(plan.get("eventId") or "")
            return {"api_payload": payload, "api_error": None}

        if write_kind_for_intent(intent) != WriteKind.READ and intent not in (
            "create_organization",
            "create_client_venue",
            "explain",
        ):
            allowed, block = consent_allows_execution(
                intent,
                mutations_dry_run=mutations_dry_run,
                confirm_mutation=confirm_mutation,
                mutation_token=mutation_token,
                action_plan=plan,
            )
            blocked = block if not allowed else None
            live = mutation_executes_live(
                intent,
                confirm_mutation=confirm_mutation,
                mutations_dry_run=mutations_dry_run,
            )
            if blocked and blocked != "confirmation_required" and live:
                return {
                    "api_payload": None,
                    "api_error": f"Cannot run mutation: {blocked}",
                }
            payload, err = execute_crud_intent(
                intent,
                plan,
                dry_run=dry_run_for(intent),
                blocked_reason=blocked,
            )
            if err:
                from apex_rag_demo.pipeline_errors import format_apex_api_error, log_pipeline_failure

                failure = format_apex_api_error(intent, err)
                log_pipeline_failure(failure)
                return {
                    "api_payload": payload,
                    "api_error": err,
                    "pipeline_error": failure.to_dict(),
                    "answer": failure.summary,
                }
            return {"api_payload": payload, "api_error": err}

        if intent == "get_event":
            event_id = plan.get("eventId") or ""
            if not event_id:
                return {"api_payload": None, "api_error": None}
            payload, err = get_event_with_context(event_id)
            if payload and plan.get("includeInventory"):
                from apex_rag_demo.event_list import unwrap_event_payload

                if payload.get("_resolution") in ("events_get", "events_get_via_search"):
                    ev = unwrap_event_payload(payload)
                    inv_event_id = str(ev.get("id") or event_id)
                    cv_id = str(ev.get("clientVenueId") or ev.get("ClientVenueId") or "") or None
                    inventory = apex_inventory.get_event_inventory_snapshot(
                        inv_event_id,
                        client_venue_id=cv_id,
                        include_ticket_types=bool(plan.get("includeTicketTypes")),
                    )
                    payload = {**payload, "_inventory": inventory}
            return {"api_payload": payload, "api_error": err}

        if intent == "inventory_zones":
            event_id = plan.get("eventId") or ""
            if not event_id:
                return {"api_payload": None, "api_error": None}
            payload = apex_inventory.get_event_inventory_snapshot(event_id)
            return {"api_payload": payload, "api_error": None}

        if intent == "marketing_events":
            from apex_rag_demo.event_date_filters import apply_date_filter_to_payload
            from apex_rag_demo.event_lifecycle_filters import (
                apply_lifecycle_filter_to_payload,
                enrich_marketing_plan_from_question,
            )

            plan = enrich_marketing_plan_from_question(plan, question)
            page_size = int(plan.get("pageSize") or 25)
            payload = apex_marketing.list_events_with_search_fallback(page_size=page_size)
            payload = apply_date_filter_to_payload(payload, plan.get("dateFilter"))
            payload = apply_lifecycle_filter_to_payload(
                payload,
                lifecycle_filter=plan.get("lifecycleFilter"),
            )
            from apex_rag_demo.event_enrichment import enrich_marketing_events_payload

            payload = enrich_marketing_events_payload(payload)
            return {"api_payload": payload, "api_error": None}

        if intent == "get_venue_config":
            from apex_rag_demo.clients import apex_manifest
            from apex_rag_demo.reports_intent_helpers import enrich_reports_plan_from_question

            plan = enrich_reports_plan_from_question(intent, plan, question)
            vid = str(plan.get("venueConfigId") or "").strip()
            if not vid:
                return {"api_payload": None, "api_error": "venueConfigId (UUID) required for manifest API."}
            try:
                payload = apex_manifest.get_venue_config(vid)
                return {"api_payload": payload, "api_error": None}
            except Exception as exc:  # noqa: BLE001
                return {"api_payload": None, "api_error": str(exc)}

        if intent == "b2b_flash_report":
            from apex_rag_demo.clients import apex_reports
            from apex_rag_demo.reports_intent_helpers import (
                build_report_catalog_payload,
                enrich_reports_plan_from_question,
                resolve_report_ids_via_events_api,
            )

            plan = enrich_reports_plan_from_question(intent, plan, question)
            if plan.get("_report_catalog"):
                return {"api_payload": build_report_catalog_payload(), "api_error": None}
            event_uuid = str(plan.get("eventUuid") or "").strip()
            if event_uuid and (plan.get("contextId") is None or plan.get("eventId") is None):
                rctx, rev, resolve_err = resolve_report_ids_via_events_api(event_uuid)
                if rctx is not None:
                    plan["contextId"] = rctx
                if rev is not None:
                    plan["eventId"] = rev
                if resolve_err and plan.get("contextId") is None:
                    catalog = build_report_catalog_payload()
                    catalog["_resolve_error"] = resolve_err
                    return {"api_payload": catalog, "api_error": None}
            kind = str(plan.get("flashReport") or "sales_event")
            if plan.get("contextId") is None:
                catalog = build_report_catalog_payload()
                catalog["_missing"] = "contextId"
                return {"api_payload": catalog, "api_error": None}
            if kind != "sales_date_range" and plan.get("eventId") is None:
                catalog = build_report_catalog_payload()
                catalog["_missing"] = "eventId"
                return {"api_payload": catalog, "api_error": None}
            try:
                payload = apex_reports.run_flash_report(plan)
                return {"api_payload": payload, "api_error": None}
            except Exception as exc:  # noqa: BLE001
                return {"api_payload": None, "api_error": str(exc)}

        if intent == "reports_inventory_event":
            from apex_rag_demo.clients import apex_reports
            from apex_rag_demo.reports_intent_helpers import (
                build_report_catalog_payload,
                enrich_reports_plan_from_question,
                resolve_report_ids_via_events_api,
            )

            plan = enrich_reports_plan_from_question(intent, plan, question)
            event_uuid = str(plan.get("eventUuid") or "").strip()
            if event_uuid and (plan.get("contextId") is None or plan.get("eventId") is None):
                rctx, rev, resolve_err = resolve_report_ids_via_events_api(event_uuid)
                if rctx is not None:
                    plan["contextId"] = rctx
                if rev is not None:
                    plan["eventId"] = rev
                if resolve_err and (plan.get("contextId") is None or plan.get("eventId") is None):
                    catalog = build_report_catalog_payload()
                    catalog["_resolve_error"] = resolve_err
                    return {"api_payload": catalog, "api_error": None}
            ctx = plan.get("contextId")
            ev = plan.get("eventId")
            if ctx is None or ev is None:
                catalog = build_report_catalog_payload()
                catalog["_missing"] = "contextId_and_eventId"
                return {"api_payload": catalog, "api_error": None}
            try:
                payload = apex_reports.get_inventory_event_report(int(ctx), int(ev))
                return {"api_payload": payload, "api_error": None}
            except Exception as exc:  # noqa: BLE001
                return {"api_payload": None, "api_error": str(exc)}

        if intent == "reports_timezones":
            from apex_rag_demo.clients import apex_reports

            try:
                payload = apex_reports.list_report_timezones()
                return {"api_payload": payload, "api_error": None}
            except Exception as exc:  # noqa: BLE001
                return {"api_payload": None, "api_error": str(exc)}

        if intent == "explain":
            return {"api_payload": None, "api_error": None}

        return {"api_payload": {"note": f"unhandled intent {intent}"}, "api_error": None}
    except Exception as exc:  # noqa: BLE001 — demo boundary
        from apex_rag_demo.pipeline_errors import explain_exception, log_pipeline_failure

        failure = explain_exception(exc, phase=f"apex_{intent}")
        log_pipeline_failure(failure, exc=exc)
        return {
            "api_payload": None,
            "api_error": failure.summary,
            "pipeline_error": failure.to_dict(),
        }
