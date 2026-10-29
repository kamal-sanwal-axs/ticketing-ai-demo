from apex_rag_demo.intent_helpers import guard_api_intent
from apex_rag_demo.order_intent_helpers import (
    extract_order_search_query,
    looks_like_order_search_request,
    looks_like_recent_search_list_request,
    order_search_precheck,
    parse_result_limit,
)


def test_order_search_guard():
    assert guard_api_intent("explain", "search orders for fan@example.com") == "search_orders"


def test_payment_status_intent():
    assert (
        guard_api_intent("explain", "list order payment statuses for splash")
        == "search_order_payment_statuses"
    )


def test_extract_query():
    assert "fan@example.com" in extract_order_search_query("search orders for fan@example.com")


def test_not_confused_with_events():
    assert not looks_like_order_search_request("search events matching lakers")


def test_customers_not_orders():
    from apex_rag_demo.order_intent_helpers import looks_like_customer_search_request

    assert looks_like_customer_search_request("search customers for a@b.com")
    assert guard_api_intent("explain", "search customers for a@b.com") == "search_customers"


def test_last_n_search_routes_to_events_not_orders():
    q = "show me last 5 search"
    assert looks_like_recent_search_list_request(q)
    assert not looks_like_order_search_request(q)
    assert guard_api_intent("search_orders", q) == "marketing_events"
    assert parse_result_limit(q) == 5


def test_order_precheck_blocks_vague_query():
    msg = order_search_precheck("search orders", "", "")
    assert msg is not None
    assert order_search_precheck(
        "search orders for fan@example.com",
        "fan@example.com",
        "fan@example.com",
    ) is None
