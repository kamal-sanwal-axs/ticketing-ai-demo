from apex_rag_demo.rag.kg_entities import ExtractedEntity, extract_entities, lookup_terms


def test_event_uuid_canonical_key():
    uid = "2e9c7e62-240d-48ec-a175-754dd8352e7a"
    ent = ExtractedEntity(entity_type="Event", text=uid)
    assert ent.canonical_key() == f"Event:{uid.lower()}"


def test_extract_uuid_from_text():
    uid = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    found = extract_entities(f"Load inventory for event {uid} please")
    keys = {e.canonical_key() for e in found}
    assert f"Event:{uid.lower()}" in keys


def test_lookup_terms_includes_session_focus():
    terms = lookup_terms(
        "show zones",
        {"eventId": "11111111-2222-3333-4444-555555555555", "eventLabel": "Summer Fest"},
    )
    assert "11111111-2222-3333-4444-555555555555" in terms
    assert any("Summer" in t for t in terms)
