from __future__ import annotations

import re

# Human-readable routing hints stored beside embeddings for similar future questions.
_INTENT_MEANING: dict[str, str] = {
    "marketing_events": (
        "List or browse ticketed events (marketing catalog). Includes filters like published/live "
        "state, on-sale soon, or date windows — not a single event UUID lookup."
    ),
    "search_events": "Typeahead or POST search for events by name, artist, or festival.",
    "search_orders": "Search fan orders (order #, email, customer) via search-api POST /v1/orders.",
    "search_order_payment_statuses": "Order payment status lookup via POST /v1/orders/list/payment-statuses.",
    "search_customers": "Search fan customers via POST /v1/customers (b2b_search_customers).",
    "get_event": "Single event by UUID from events-api (details, dates, status).",
    "inventory_zones": "Inventory primary zone, price levels, sections for an event id.",
    "list_client_venues": "Client venue registry from search-api, not marketing events.",
    "list_users": "B2B user directory from resources-api GET /v1/Users (axs-b2b-admin user list).",
    "publish_event": "POST publish on a specific event id.",
    "update_event": "PUT event to change headliners/title for a uuid.",
}


def interpret_publish_status_question(bare_question: str) -> str | None:
    q = bare_question.lower()
    if not re.search(r"\b(publish|published|onsale|on-sale|live)\b", q):
        return None
    if re.search(r"\bevents?\b", q) and re.search(r"\b(status|state|show|list|with)\b", q):
        return (
            "User wants events filtered by publish/live/onsale lifecycle — use marketing_events "
            "or search_events, not get_event unless a uuid is present."
        )
    return None


def memory_document_text(
    question: str,
    intent: str,
    answer_summary: str,
    *,
    plan: dict | None = None,
) -> str:
    from apex_rag_demo.response_formatters import strip_ui_region

    bare = strip_ui_region(question)
    lines = [
        f"Question: {bare}",
        f"Intent: {intent}",
        f"Meaning: {_INTENT_MEANING.get(intent, 'APEX API operation')}",
    ]
    extra = interpret_publish_status_question(bare)
    if extra:
        lines.append(f"Note: {extra}")
    if plan:
        lines.append(f"Plan: {plan}")
    if answer_summary:
        lines.append(f"Answer: {answer_summary[:500]}")
    return "\n".join(lines)


def suggest_intent_from_question(bare_question: str) -> str | None:
    from apex_rag_demo.order_intent_helpers import looks_like_order_search_request

    from apex_rag_demo.order_intent_helpers import looks_like_customer_search_request

    if looks_like_order_search_request(bare_question):
        if re.search(r"\bpayment\s+status", bare_question, re.I):
            return "search_order_payment_statuses"
        return "search_orders"
    if looks_like_customer_search_request(bare_question):
        return "search_customers"
    pub = interpret_publish_status_question(bare_question)
    if pub and "marketing_events" in pub:
        if re.search(
            r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b",
            bare_question,
            re.I,
        ):
            return None
        return "marketing_events"
    return None
