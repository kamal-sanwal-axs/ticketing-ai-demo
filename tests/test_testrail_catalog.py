from apex_rag_demo.testrail_catalog import catalog_entries, load_catalog


def test_catalog_loaded():
    cat = load_catalog()
    assert cat.get("entry_count", 0) >= 50
    entries = catalog_entries()
    assert any(e.get("testrail_id") == "C66084315" for e in entries)
    assert any(e.get("mfe") == "axs-apex-search" for e in entries)


def test_orders_cases_mapped():
    orders = [e for e in catalog_entries() if e.get("assistant_intent") == "search_orders"]
    assert len(orders) >= 10
