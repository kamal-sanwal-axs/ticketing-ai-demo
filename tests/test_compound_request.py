from apex_rag_demo.compound_request import (
    looks_like_events_plus_seat_level_detail,
    try_compound_orchestrator_step,
)
from apex_rag_demo.intent_helpers import guard_api_intent
from apex_rag_demo.intent_semantic import is_conversational_message

QUERY = (
    "show me published events so that I can see seat sold and price code "
    "and ticket type and all other seat level info"
)
QUERY_TYPO = (
    "show me published events so that I can see seat sold and price code "
    "and ticket type and all other seat levle info"
)


def test_compound_detected():
    assert looks_like_events_plus_seat_level_detail(QUERY)
    assert looks_like_events_plus_seat_level_detail(QUERY_TYPO)


def test_guard_routes_marketing():
    assert guard_api_intent("explain", QUERY) == "marketing_events"


def test_not_conversational():
    assert not is_conversational_message(QUERY)


def test_compound_step_one():
    step = try_compound_orchestrator_step(QUERY, api_trace=[], session_focus={})
    assert step and step.get("orchestrator_action") == "call_api"
    assert step.get("intent") == "marketing_events"
