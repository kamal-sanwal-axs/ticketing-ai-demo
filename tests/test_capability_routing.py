from apex_rag_demo.capability_routing import (
    capability_correct_read_intent,
    enrich_read_plan_from_question,
    resolve_capability_intent,
)
from apex_rag_demo.intent_helpers import guard_api_intent


def test_capability_resolves_last_search_to_marketing():
    intent = resolve_capability_intent("show me last 5 search")
    assert intent == "marketing_events"


def test_capability_corrects_misclassified_orders():
    fixed = capability_correct_read_intent("search_orders", "show me last 5 search")
    assert fixed == "marketing_events"


def test_guard_uses_capability_not_regex_list():
    assert guard_api_intent("search_orders", "show me last 5 search") == "marketing_events"


def test_enrich_plan_page_size():
    plan = enrich_read_plan_from_question("marketing_events", {}, "show me last 5 search")
    assert plan.get("pageSize") == 5
