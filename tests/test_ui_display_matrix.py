"""Fixture-driven UI layout tests for build_ui_display (complements docs/MANUAL_UI_DISPLAY_TESTS.md)."""

from __future__ import annotations

from typing import Any

import pytest

from apex_rag_demo.ui_display import build_ui_display


def _state(
    *,
    intent: str,
    question: str = "",
    payload: dict[str, Any] | None = None,
    api_error: str | None = None,
    plan: dict[str, Any] | None = None,
    pipeline_error: dict[str, Any] | None = None,
    api_trace: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "intent": intent,
        "question": question,
        "api_payload": payload,
        "api_error": api_error,
        "action_plan": plan or {},
        "pipeline_error": pipeline_error,
        "api_trace": api_trace or [],
        "kb_snippets": [],
        "answer": "",
    }


_NAMED_EVENT = {
    "id": "0167f575-64bf-4465-93fe-98c378d3fd6f",
    "headliners": "MHayarpi Announced event",
    "status": "Published",
    "dates": {
        "start": {"on": "2026-12-15T10:00:00Z"},
        "end": {"on": "2026-12-30T15:00:00Z"},
    },
}

_ID_ONLY_EVENT = {
    "id": "06dad184-a01c-44fb-b1a5-f5be8727a2fa",
}


@pytest.mark.parametrize(
    "state,expect_type,expect_keys",
    [
        (
            _state(
                intent="marketing_events",
                question="show me events",
                payload={"events": [_NAMED_EVENT]},
            ),
            "table",
            {"title": "Events", "columns": True, "rows": True},
        ),
        (
            _state(
                intent="marketing_events",
                question="show events count",
                payload={"events": [_NAMED_EVENT, dict(_NAMED_EVENT, id="2", headliners="B")]},
            ),
            "table",
            {"count": 2},
        ),
        (
            _state(
                intent="marketing_events",
                question="show event names only",
                payload={"events": [_NAMED_EVENT]},
            ),
            "table",
            {"column_keys": {"name"}},
        ),
        (
            _state(
                intent="marketing_events",
                question="list events with org hierarchy",
                payload={"events": [_NAMED_EVENT]},
            ),
            "table",
            {"column_keys_superset": {"principalOrganization", "client", "name", "id"}},
        ),
        (
            _state(
                intent="marketing_events",
                question="events by month chart",
                payload={"events": [_NAMED_EVENT]},
            ),
            "dashboard",
            {"charts": True},
        ),
        (
            _state(
                intent="marketing_events",
                question="show me events",
                payload={
                    "events": [_NAMED_EVENT, _ID_ONLY_EVENT],
                    "_event_enrichment": {
                        "resolved_names": 1,
                        "description": "test enrichment",
                    },
                },
            ),
            "table",
            {"sections": True, "paragraph_hydrated": True},
        ),
        (
            _state(
                intent="marketing_events",
                question="show me events",
                payload={
                    "_source": "search-api-fallback",
                    "_marketing_status": 403,
                    "_fallback_query": "event",
                    "events": [_NAMED_EVENT],
                },
            ),
            "table",
            {"title_contains": "search fallback"},
        ),
        (
            _state(
                intent="marketing_events",
                question="events after Jan 2099",
                payload={
                    "events": [],
                    "_date_filter": {
                        "description": "Start after 2099-01-01",
                        "_matched": 0,
                        "_total_before_filter": 1,
                    },
                },
            ),
            "article",
            {"paragraphs": True},
        ),
        (
            _state(
                intent="search_events",
                question="search events matching Splash",
                payload={"events": [_NAMED_EVENT], "_search_via": "post-events"},
                plan={"query": "Splash"},
            ),
            "table",
            {"title": "Event search"},
        ),
        (
            _state(
                intent="search_events",
                question="search events matching None",
                payload={"events": []},
                plan={"query": "None"},
            ),
            "article",
            {"paragraphs": True},
        ),
        (
            _state(
                intent="search_orders",
                question="search orders for fan@example.com",
                payload={
                    "orders": [
                        {
                            "orderNumber": "ORD-1",
                            "customerName": "Fan",
                            "email": "fan@example.com",
                            "paymentStatus": "Paid",
                        },
                    ],
                },
                plan={"keyword": "fan@example.com"},
            ),
            "table",
            {"title": "Orders (search)"},
        ),
        (
            _state(
                intent="search_orders",
                question="search orders for none@example.com",
                payload={"orders": []},
                plan={"keyword": "none@example.com"},
            ),
            "article",
            {"paragraphs": True},
        ),
        (
            _state(
                intent="search_customers",
                question="search customers for a@b.com",
                payload={
                    "customers": [
                        {
                            "accountNumber": "1",
                            "customerName": "A",
                            "email": "a@b.com",
                            "client": "C",
                        },
                    ],
                },
                plan={"keyword": "a@b.com"},
            ),
            "table",
            {"title": "Customers (search)"},
        ),
        (
            _state(
                intent="list_client_venues",
                question="list client venues",
                payload={"clientVenues": [{"name": "Venue A", "id": "v1"}]},
            ),
            "table",
            {"title_contains": "Client venues"},
        ),
        (
            _state(
                intent="get_event",
                question="get event",
                plan={},
            ),
            "article",
            {"level": "warning"},
        ),
        (
            _state(
                intent="inventory_zones",
                question="inventory zones",
                plan={"eventId": "0167f575-64bf-4465-93fe-98c378d3fd6f"},
                payload={"zones": []},
            ),
            "article",
            {"title": "Event inventory"},
        ),
        (
            _state(
                intent="explain",
                question="hello",
            ),
            "article",
            {"title_contains": "Welcome"},
        ),
        (
            _state(
                intent="marketing_events",
                question="show me events",
                api_error="HTTP 403 Forbidden",
            ),
            "article",
            {"level": "error"},
        ),
        (
            _state(
                intent="explain",
                pipeline_error={
                    "code": "search_orders_http_500",
                    "title": "Search API orders error (HTTP 500)",
                    "summary": '{"error":["Internal System Error"]}',
                    "detail": '{"error":["Internal System Error"]}',
                    "remediation": "Fix upstream.",
                    "http_status": 500,
                    "endpoint": "https://api.apex-dev.axsdevops.io/search/v1/orders",
                    "component": "apex_search_orders",
                },
            ),
            "article",
            {"level": "error", "fields": True},
        ),
        (
            _state(
                intent="create_organization",
                question="create organization Demo",
                payload={"request": {"name": "Demo"}, "_dry_run": True},
            ),
            "article",
            {"level": "warning"},
        ),
        (
            _state(
                intent="marketing_events",
                question="show me events",
                payload={
                    "_pending_confirmation": True,
                    "message": "Confirm?",
                    "preview": {"summary": "Will create"},
                    "mutation_token": "tok",
                },
            ),
            "article",
            {"title": "Confirm before sending"},
        ),
    ],
)
def test_ui_display_matrix(state: dict[str, Any], expect_type: str, expect_keys: dict[str, Any]):
    ui = build_ui_display(state)
    assert ui is not None
    assert ui.get("type") == expect_type

    if "title" in expect_keys:
        assert ui.get("title") == expect_keys["title"]
    if "title_contains" in expect_keys:
        assert expect_keys["title_contains"] in str(ui.get("title") or "")
    if expect_keys.get("columns"):
        assert isinstance(ui.get("columns"), list) and ui["columns"]
    if expect_keys.get("rows"):
        assert isinstance(ui.get("rows"), list)
    if "count" in expect_keys:
        assert ui.get("count") == expect_keys["count"]
    if expect_keys.get("column_keys"):
        keys = {c["key"] for c in ui.get("columns") or []}
        assert keys == expect_keys["column_keys"]
    if expect_keys.get("column_keys_superset"):
        keys = {c["key"] for c in ui.get("columns") or []}
        assert expect_keys["column_keys_superset"] <= keys
    if expect_keys.get("charts"):
        assert ui.get("charts")
    if expect_keys.get("sections"):
        assert ui.get("sections")
    if expect_keys.get("paragraph_hydrated"):
        text = " ".join(ui.get("paragraphs") or [])
        assert "Hydrated" in text
    if expect_keys.get("paragraphs"):
        assert ui.get("paragraphs")
    if "level" in expect_keys:
        assert ui.get("level") == expect_keys["level"]
    if expect_keys.get("fields"):
        assert ui.get("fields")
