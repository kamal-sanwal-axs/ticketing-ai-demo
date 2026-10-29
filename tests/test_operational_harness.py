from apex_rag_demo.intent_helpers import guard_api_intent
from apex_rag_demo.testrail_catalog import catalog_kb_texts, load_harness_prompts


def test_harness_guard_labels():
    for row in load_harness_prompts():
        expected = row["expected_intent"]
        got = guard_api_intent("explain", row["prompt"])
        assert got == expected, f"{row['id']}: {got} != {expected}"


def test_catalog_kb_skips_layout_smoke():
    texts = " ".join(t for _, t in catalog_kb_texts())
    assert "What does the" not in texts
    assert "MFE do in APEX" not in texts
    assert "search customers" in texts.lower() or "show me customers" in texts.lower()


def test_best_available_routing():
    assert guard_api_intent("explain", "show best available for event 8f0a2f5c-9f45-4a7e-93f2-2f6a3f1f2b10") == "inventory_zones"
    assert guard_api_intent("explain", "show best available for customer Kamal") == "search_customers"
