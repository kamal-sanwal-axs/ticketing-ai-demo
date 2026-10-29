from apex_rag_demo.event_list import EVENT_HIERARCHY_TABLE_COLUMNS
from apex_rag_demo.ui_schema import (
    EVENT_CATALOG_TABLE_COLUMNS,
    resolve_event_list_columns,
    wants_org_hierarchy_in_event_list,
)


def test_show_events_catalog_columns_only():
    cols = resolve_event_list_columns("show me events")
    assert cols == EVENT_CATALOG_TABLE_COLUMNS
    assert not wants_org_hierarchy_in_event_list("show me events")


def test_org_phrase_uses_hierarchy():
    cols = resolve_event_list_columns("list events with org hierarchy")
    assert cols == EVENT_HIERARCHY_TABLE_COLUMNS
