from apex_rag_demo.dynamic_tools import (
    legacy_intent_for_tool_id,
    load_dynamic_tool_catalog,
    parameters_to_action_plan,
    resolve_dynamic_tool_id,
)


def test_openapi_catalog_loads():
    catalog = load_dynamic_tool_catalog()
    assert len(catalog) >= 10
    bad = [
        t
        for t in catalog.values()
        if "list-event-statuses" in t.path_template or "list-venues" in t.path_template
    ]
    assert not bad, f"Auxiliary search list endpoints should not be tools: {[t.tool_id for t in bad]}"
    sample = next(iter(catalog.values()))
    assert sample.tool_id
    assert sample.legacy_intent in (
        "marketing_events",
        "search_events",
        "search_orders",
        "get_event",
        "list_client_venues",
    )


def test_resolve_marketing_list_tool():
    tool_id = resolve_dynamic_tool_id("show me last 5 search")
    assert tool_id
    assert legacy_intent_for_tool_id(tool_id) == "marketing_events"


def test_parameters_include_page_size():
    catalog = load_dynamic_tool_catalog()
    tool_id = resolve_dynamic_tool_id("show me last 5 search")
    assert tool_id
    tool = catalog[tool_id]
    plan = parameters_to_action_plan(tool, {}, "show me last 5 search")
    assert plan.get("pageSize") == 5
    assert plan.get("tool_id") == tool_id
