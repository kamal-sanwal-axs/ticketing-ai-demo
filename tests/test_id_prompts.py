from apex_rag_demo.id_prompts import clarify_missing_event_id, resolve_event_id


def test_clarify_price_codes_without_uuid():
    msg = clarify_missing_event_id("explain", "show price codes for my event")
    assert msg is not None
    assert "event UUID" in msg


def test_resolve_event_id_from_question():
    q = "get event 8f0a2f5c-9f45-4a7e-93f2-2f6a3f1f2b10"
    assert resolve_event_id(q, {}, {}) == "8f0a2f5c-9f45-4a7e-93f2-2f6a3f1f2b10"
