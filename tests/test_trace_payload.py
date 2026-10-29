"""Tests for trace payload restoration and agentic finish."""

from apex_rag_demo.agentic_event import try_agentic_finish_step
from apex_rag_demo.trace_payload import enrich_state_from_best_trace, find_best_get_event_from_trace

EID = "c6b25836-991d-4ab7-b583-5ed5b9c3047d"
QUERY = f"get price code, price level, sections and zone also venue details for {EID}"


def test_find_best_get_event_prefers_inventory():
    trace = [
        {
            "intent": "get_event",
            "plan": {"eventId": EID, "includeInventory": True},
            "payload": {
                "_resolution": "events_get",
                "id": EID,
                "title": "Demo Event",
                "_inventory": {"zones": []},
            },
        },
        {
            "intent": "list_client_venues",
            "plan": {"tool_id": "search.post.v1-client-venues"},
            "payload": {"venues": []},
        },
    ]
    hit = find_best_get_event_from_trace(trace, event_id=EID, need_inventory=True)
    assert hit
    plan, payload = hit
    assert plan["eventId"] == EID
    assert payload.get("_inventory")


def test_enrich_state_restores_get_event_payload():
    good = {
        "_resolution": "events_get",
        "id": EID,
        "title": "Demo Event",
        "startDate": "2026-01-01",
        "_inventory": {"primaryZone": {}},
    }
    trace = [
        {"intent": "get_event", "plan": {"eventId": EID, "includeInventory": True}, "payload": good},
        {"intent": "list_client_venues", "plan": {}, "payload": {"items": []}},
    ]
    state = {
        "question": QUERY,
        "intent": "get_event",
        "action_plan": {"tool_id": "search.post.v1-client-venues"},
        "api_payload": {"items": []},
        "api_trace": trace,
    }
    out = enrich_state_from_best_trace(state)
    assert out["api_payload"] == good
    assert out["action_plan"]["includeInventory"] is True


def test_agentic_finish_after_successful_get_event():
    trace = [
        {
            "intent": "get_event",
            "plan": {"eventId": EID, "includeInventory": True, "includeTicketTypes": True},
            "payload": {
                "_resolution": "events_get",
                "id": EID,
                "_inventory": {"zones": []},
            },
        },
    ]
    step = try_agentic_finish_step(QUERY, api_trace=trace, session_focus={})
    assert step
    assert step["orchestrator_action"] == "finish"
    assert step["intent"] == "get_event"
