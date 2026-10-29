from apex_rag_demo.agentic_event import (
    looks_like_any_event_inventory_demo,
    looks_like_event_or_venue_detail_with_id,
    try_agentic_orchestrator_step,
)
from apex_rag_demo.agent_orchestrator import decide_orchestrator_step

ANY_EVENT_QUERY = (
    "use any event to show me price code, ticket type and sections"
)
VENUE_QUERY = (
    "get me venue details for a6163117-d8f3-4971-be7d-c0ea53ec9e75 event"
)
FAKE_ID = "8f0a2f5c-9f45-4a7e-93f2-2f6a3f1f2b10"


def test_any_event_inventory_detected():
    assert looks_like_any_event_inventory_demo(ANY_EVENT_QUERY)


def test_venue_detail_with_uuid():
    assert looks_like_event_or_venue_detail_with_id(VENUE_QUERY)


def test_agentic_step_lists_events_for_any_event():
    step = try_agentic_orchestrator_step(ANY_EVENT_QUERY, api_trace=[], session_focus={})
    assert step
    assert step["orchestrator_action"] == "call_api"
    assert step["intent"] == "marketing_events"


def test_agentic_step_get_event_for_venue_uuid():
    step = try_agentic_orchestrator_step(VENUE_QUERY, api_trace=[], session_focus={})
    assert step
    assert step["intent"] == "get_event"
    assert step["action_plan"]["eventId"] == "a6163117-d8f3-4971-be7d-c0ea53ec9e75"


def test_recovery_after_404_lists_marketing():
    trace = [
        {
            "intent": "get_event",
            "plan": {"eventId": FAKE_ID},
            "payload": {"_resolution": "not_found"},
        },
    ]
    step = try_agentic_orchestrator_step(
        f"get event {FAKE_ID}",
        api_trace=trace,
        session_focus={},
    )
    assert step and step["intent"] == "marketing_events"


def test_decide_prefers_agentic_before_missing_id_finish():
    decision = decide_orchestrator_step(
        ANY_EVENT_QUERY,
        classified_intent="explain",
        session_focus={},
        api_trace=[],
        orchestrator_round=1,
        user_id="test-user",
        semantic_intent_hint="explain",
        semantic_score=0.99,
    )
    assert decision.get("orchestrator_action") == "call_api"
    assert decision.get("intent") == "marketing_events"
