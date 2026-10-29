from apex_rag_demo.dynamic_tools import load_dynamic_tool_catalog
from apex_rag_demo.intent_helpers import guard_api_intent
from apex_rag_demo.reports_intent_helpers import (
    enrich_reports_plan_from_question,
    infer_flash_report_kind,
    looks_like_b2b_reports_question,
)


def test_guard_routes_flash_sales():
    q = "flash sales report context 100 event 200"
    assert guard_api_intent("explain", q) == "b2b_flash_report"


def test_guard_routes_manifest():
    vid = "a6163117-d8f3-4971-be7d-c0ea53ec9e75"
    assert guard_api_intent("explain", f"venue config {vid}") == "get_venue_config"


def test_enrich_reports_plan():
    plan = enrich_reports_plan_from_question(
        "b2b_flash_report",
        {},
        "sales report context 11 event 22",
    )
    assert plan["contextId"] == 11
    assert plan["eventId"] == 22
    assert infer_flash_report_kind("ticket lifecycle report context 1 event 2") == "ticket_lifecycle"


def test_dynamic_catalog_includes_reports_and_manifest():
    load_dynamic_tool_catalog.cache_clear()
    catalog = load_dynamic_tool_catalog()
    intents = {t.legacy_intent for t in catalog.values()}
    assert "get_venue_config" in intents
    assert "b2b_flash_report" in intents
    assert "reports_inventory_event" in intents
    assert "inventory_zones" in intents
    assert any(t.service_id == "manifest" for t in catalog.values())
    assert any(t.service_id == "reports" for t in catalog.values())
    assert any(t.service_id == "inventory" for t in catalog.values())


def test_b2b_reports_phrase_detect():
    assert looks_like_b2b_reports_question("show b2b reports inventory for context 1 event 2")
    assert looks_like_b2b_reports_question("get me a report")
    assert looks_like_b2b_reports_question(
        "can you show me reports for the event 0167f575-64bf-4465-93fe-98c378d3fd6f",
    )


def test_guard_routes_reports_not_get_event():
    q = "can you show me reports for the event 0167f575-64bf-4465-93fe-98c378d3fd6f"
    assert guard_api_intent("get_event", q) == "b2b_flash_report"


def test_resolve_reports_guard_intent():
    from apex_rag_demo.reports_intent_helpers import resolve_reports_guard_intent

    assert resolve_reports_guard_intent("get me a report") == "b2b_flash_report"
    assert (
        resolve_reports_guard_intent(
            "can you show me reports for the event 0167f575-64bf-4465-93fe-98c378d3fd6f",
        )
        == "b2b_flash_report"
    )
