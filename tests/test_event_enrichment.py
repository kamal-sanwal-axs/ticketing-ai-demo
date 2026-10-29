from apex_rag_demo.event_enrichment import partition_event_table_rows
from apex_rag_demo.event_list import event_display_name, event_has_actionable_name


def test_actionable_name():
    assert event_has_actionable_name({"headliners": "Splash House"})
    assert not event_has_actionable_name({"id": "0167f575-64bf-4465-93fe-98c378d3fd6f"})


def test_partition_hides_id_only():
    rows = [
        {"name": "Real Show", "id": "a", "startDate": "—", "status": "Live", "clientVenueId": "—"},
        {"name": "—", "id": "b", "startDate": "—", "status": "—", "clientVenueId": "—"},
    ]
    ok, bad = partition_event_table_rows(rows)
    assert len(ok) == 1
    assert ok[0]["name"] == "Real Show"
    assert len(bad) == 1
    assert bad[0]["id"] == "b"


def test_display_name_from_headliners():
    assert event_display_name({"headliners": "Coachella 2026"}) == "Coachella 2026"
