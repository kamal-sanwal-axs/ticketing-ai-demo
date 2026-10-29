"""Order search intents (axs-apex-search / TestRail C66084315+)."""

from __future__ import annotations

import re

from apex_rag_demo.response_formatters import strip_ui_region

_CUSTOMER_SEARCH_RE = re.compile(
    r"("
    r"\b(search|find|lookup|list|show)\b.*\b(customers?|fans?)\b|"
    r"\b(customers?|fans?)\b.*\b(search|for|matching|email|named|with)\b|"
    r"\bfan\s+account\b"
    r")",
    re.I,
)

_ORDER_SEARCH_RE = re.compile(
    r"("
    r"\b(search|find|lookup|list|show)\b.*\borders?\b|"
    r"\borders?\b.*\b(search|for|matching|number)\b|"
    r"\border\s+number\b|"
    r"\bcustomer\b.*\b(order|email)\b"
    r")",
    re.I,
)

_PAYMENT_STATUS_RE = re.compile(
    r"\b(payment\s+status|payment\s+statuses)\b.*\b(order)?\b",
    re.I,
)

# "show me last 5 search" — event/browse wording, not axs-apex-search Orders.
_RECENT_SEARCH_LIST_RE = re.compile(
    r"("
    r"\b(?:show|list|give)\b.*\b(?:last|latest|recent)\b\s*\d*\s*\bsearch(?:es)?\b|"
    r"\b(?:last|latest|recent)\b\s*\d+\s*\bsearch(?:es)?\b"
    r")",
    re.I,
)

_EMAIL_RE = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")
_ORDER_NUM_RE = re.compile(r"\b(?:ORD[- ]?)?\d{4,}\b", re.I)
_META_KEYWORD_RE = re.compile(r"^(?:show|list|find|search|lookup)\s+me\b", re.I)


def looks_like_customer_search_request(question: str) -> bool:
    return bool(_CUSTOMER_SEARCH_RE.search(strip_ui_region(question)))


def looks_like_recent_search_list_request(question: str) -> bool:
    """User wants a short list of search results (usually events), not POST /v1/orders."""
    bare = strip_ui_region(question)
    if looks_like_order_search_request(bare):
        return False
    return bool(_RECENT_SEARCH_LIST_RE.search(bare))


def parse_result_limit(question: str, *, default: int | None = None) -> int | None:
    bare = strip_ui_region(question)
    m = re.search(r"\b(?:last|latest|top|first)\s+(\d{1,3})\b", bare, re.I)
    if m:
        return max(1, min(int(m.group(1)), 100))
    return default


def looks_like_order_search_request(question: str) -> bool:
    bare = strip_ui_region(question)
    if _CUSTOMER_SEARCH_RE.search(bare) and "order" not in bare.lower():
        return False
    if _PAYMENT_STATUS_RE.search(bare):
        return True
    return bool(_ORDER_SEARCH_RE.search(bare))


def extract_search_keyword(question: str) -> str:
    return extract_order_search_query(question)


def extract_order_search_query(question: str) -> str:
    bare = strip_ui_region(question)
    for pattern in (
        r"\borders?\s+for\s+(.+)$",
        r"\bsearch\s+orders?\s+(?:for\s+)?(.+)$",
        r"\bfind\s+orders?\s+(?:for\s+)?(.+)$",
        r"\bcustomer\s+(.+)$",
        r"\bemail\s+(.+)$",
    ):
        m = re.search(pattern, bare, re.I)
        if m:
            return m.group(1).strip().rstrip(".")
    bare = bare.strip()[:120]
    if looks_like_recent_search_list_request(bare):
        return ""
    return bare


def order_search_precheck(
    question: str,
    keyword: str | None,
    search_values: str | None,
) -> str | None:
    """Return a user message when POST /v1/orders should not be called."""
    q = strip_ui_region(question)
    if looks_like_recent_search_list_request(q):
        return (
            "That sounds like a **recent search / event list**, not fan **orders**. "
            "Try: `show me the last 5 events` or `search events for Splash House`. "
            "For orders: `search orders for fan@example.com`."
        )
    if not looks_like_order_search_request(q):
        return (
            "I only call **search orders** when you mention orders. "
            "Example: `search orders for fan@example.com`. "
            "For events: `show me events` or `search events for <name>`."
        )
    kw = (keyword or search_values or "").strip()
    if not kw:
        return (
            "Add an **order number** or **customer email** — e.g. "
            "`search orders for fan@example.com`."
        )
    if _META_KEYWORD_RE.match(kw) or looks_like_recent_search_list_request(kw):
        return (
            "I need a specific **email** or **order #**, not the whole phrase. "
            "Example: `search orders for fan@example.com`."
        )
    if _EMAIL_RE.search(kw) or _ORDER_NUM_RE.search(kw):
        return None
    if len(kw) > 80:
        return (
            "Use a shorter order search term (email, order number, or customer name)."
        )
    if len(kw) >= 2:
        return None
    return "Add a customer email or order number to search orders."
