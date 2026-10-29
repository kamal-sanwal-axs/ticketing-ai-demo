"""Legacy home MFE explain routing removed — operational flows only."""

from apex_rag_demo.intent_helpers import guard_api_intent


def test_upcoming_events_operational():
    assert guard_api_intent("explain", "show upcoming events") == "marketing_events"
