from apex_rag_demo.intent_helpers import guard_api_intent
from apex_rag_demo.marketing_list_followup import (
    looks_like_marketing_list_reformat,
    try_marketing_list_followup_step,
)


def test_group_by_org_followup_detected():
    q = "now group them by their organization"
    assert looks_like_marketing_list_reformat(q)
    assert guard_api_intent("create_organization", q) == "marketing_events"


def test_marketing_followup_finish_step():
    step = try_marketing_list_followup_step(
        "now group them by their organization",
        session_focus={"hasMarketingList": True, "lastIntent": "marketing_events"},
        user_id="u1",
        session_id="s1",
    )
    assert step
    assert step["orchestrator_action"] == "finish"
    assert step["intent"] == "marketing_events"
    assert step["action_plan"]["_followup_group_by"] == "organization"


def test_explicit_create_org_not_blocked():
    q = "create organization QA Demo Org"
    assert guard_api_intent("create_organization", q) == "create_organization"
