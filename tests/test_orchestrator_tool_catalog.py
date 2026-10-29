from apex_rag_demo.dynamic_tools import tool_catalog_for_orchestrator, tool_catalog_for_prompt


def test_orchestrator_catalog_smaller_than_full():
    q = "please group the response from Client venue and show pie chart"
    full = tool_catalog_for_prompt(max_tools=48)
    subset = tool_catalog_for_orchestrator(
        q,
        classified_intent="list_client_venues",
        semantic_intent_hint="list_client_venues",
    )
    assert len(subset) < len(full)
    assert "search.post.v1-client-venues" in subset
    assert "(+ " in subset and "omitted" in subset


def test_orchestrator_catalog_includes_hint_intent():
    subset = tool_catalog_for_orchestrator(
        "now group them by their organization",
        classified_intent="marketing_events",
    )
    assert "marketing" in subset.lower() or "events" in subset.lower()
