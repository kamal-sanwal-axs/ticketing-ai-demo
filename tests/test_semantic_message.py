from apex_rag_demo.semantic_message import (
    asymmetric_message_similarity,
    history_similarity_to_prior_users,
    semantic_units,
)
from apex_rag_demo.semantic_turn import prepare_semantic_turn


def test_semantic_units_includes_lines():
    text = "show me events\nwith inventory for uuid"
    units = semantic_units(text)
    assert text in units
    assert any("inventory" in u for u in units)


def test_new_session_topic_shift():
    ctx = prepare_semantic_turn("show me events", [])
    assert ctx.topic_shift
    assert ctx.chat_messages == []


def test_different_topics_low_similarity():
    a = "search customers for kamal@example.com"
    b = "show me published events with price codes and ticket types"
    sim = asymmetric_message_similarity(b, a)
    assert sim < 0.55


def test_empty_prior_history_similarity():
    assert history_similarity_to_prior_users("hello", []) == 0.0
