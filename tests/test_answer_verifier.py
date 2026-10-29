from apex_rag_demo.answer_verifier import strip_ungrounded_uuids, verify_answer_uuids


def test_verify_blocks_unknown_uuid():
    facts = {"all_uuids": ["aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"]}
    ok, extra = verify_answer_uuids(
        "Event id ffffffff-ffff-ffff-ffff-ffffffffffff is on sale.",
        facts,
    )
    assert not ok
    assert extra


def test_strip_replaces_bad_uuid():
    facts = {"all_uuids": ["aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"]}
    text = "Good: aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee Bad: ffffffff-ffff-ffff-ffff-ffffffffffff"
    out = strip_ungrounded_uuids(text, facts)
    assert "ffffffff" not in out
