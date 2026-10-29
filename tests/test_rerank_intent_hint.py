from unittest.mock import MagicMock, patch

from apex_rag_demo.rag.rerank import rerank_texts


@patch("apex_rag_demo.rag.rerank._cross_encoder")
def test_rerank_boosts_kb_snippet_matching_intent_hint(mock_ce):
    model = MagicMock()
    model.predict.return_value = [0.01, 0.02]
    mock_ce.return_value = model
    docs = [
        "TestRail intent=search_events. POST /v1/Events search by title",
        "TestRail intent=marketing_events. empty state when no upcoming events",
    ]
    out = rerank_texts("find events by title", docs, 1, intent_hint="search_events")
    assert "search_events" in out[0]
