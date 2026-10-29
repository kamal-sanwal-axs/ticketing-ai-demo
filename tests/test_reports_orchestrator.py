from unittest.mock import patch

from apex_rag_demo.reports_intent_helpers import resolve_report_ids_from_event
from apex_rag_demo.reports_orchestrator import (
    try_reports_finish_step,
    try_reports_orchestrator_step,
)


def test_reports_chain_promotes_after_get_event():
    uuid = "0167f575-64bf-4465-93fe-98c378d3fd6f"
    question = f"can you show me reports for the event {uuid}"
    trace = [
        {
            "intent": "get_event",
            "plan": {
                "eventId": uuid,
                "_pending_report_intent": "b2b_flash_report",
                "_reports_chain": True,
            },
            "payload": {
                "id": uuid,
                "event": {"client": {"contextId": 100, "name": "Demo"}},
            },
        },
    ]
    step = try_reports_orchestrator_step(
        question,
        classified_intent="b2b_flash_report",
        api_trace=trace,
        session_focus=None,
    )
    assert step is not None
    assert step["orchestrator_action"] == "call_api"
    assert step["intent"] == "b2b_flash_report"
    assert step["orchestrator_reason"] == "reports_after_event_lookup"
    plan = step["action_plan"]
    assert plan["contextId"] == 100
    assert plan.get("eventUuid") == uuid


def test_reports_chain_schedules_get_event_first():
    uuid = "0167f575-64bf-4465-93fe-98c378d3fd6f"
    question = f"can you show me reports for the event {uuid}"
    step = try_reports_orchestrator_step(
        question,
        classified_intent="b2b_flash_report",
        api_trace=None,
        session_focus=None,
    )
    assert step is not None
    assert step["intent"] == "get_event"
    assert step["action_plan"]["_reports_chain"] is True
    assert step["action_plan"]["_pending_report_intent"] == "b2b_flash_report"
    assert step["orchestrator_reason"] == "reports_event_lookup_first"


def test_resolve_report_ids_uses_integration_when_payload_sparse():
    uuid = "0167f575-64bf-4465-93fe-98c378d3fd6f"
    sparse = {"id": uuid, "name": "Event without numeric ids on body"}

    with patch(
        "apex_rag_demo.clients.apex_events.get_event_ticketing_integration",
        return_value={"contextId": 555, "eventId": 777},
    ):
        ctx, ev, err = resolve_report_ids_from_event(uuid, event_payload=sparse)

    assert err is None
    assert ctx == 555
    assert ev == 777


def test_reports_finish_after_live_api():
    question = "flash sales report context 1 event 2"
    trace = [
        {
            "intent": "b2b_flash_report",
            "payload": {"rows": [{"sold": 1}]},
            "plan": {"contextId": 1, "eventId": 2},
        },
    ]
    finish = try_reports_finish_step(question, api_trace=trace, session_focus=None)
    assert finish is not None
    assert finish["orchestrator_action"] == "finish"
    assert finish["orchestrator_reason"] == "reports_api_complete"


def test_dynamic_catalog_registers_inventory_zones_tool():
    from apex_rag_demo.dynamic_tools import load_dynamic_tool_catalog

    load_dynamic_tool_catalog.cache_clear()
    catalog = load_dynamic_tool_catalog()
    zone_tools = [t for t in catalog.values() if t.legacy_intent == "inventory_zones"]
    assert zone_tools, "inventory GET /events/{eventId}/zones/primary should be a dynamic tool"
    assert any("zones/primary" in t.path_template for t in zone_tools)
