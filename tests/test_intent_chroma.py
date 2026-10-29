from apex_rag_demo.rag.intent_chroma import resolve_pre_llm_routing

COMPOUND = (
    "show me published events so that I can see seat sold and price code "
    "and ticket type and all other seat levle info"
)


def test_compound_pre_llm_skips_classify_llm():
    route = resolve_pre_llm_routing(COMPOUND)
    assert route is not None
    assert route.intent == "marketing_events"
    assert route.skip_llm_classify
    assert route.compound
    assert "pre-LLM" in route.label
