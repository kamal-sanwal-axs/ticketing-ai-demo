"""Guards for operator-style prompts (TestRail harness / anti-hallucination routing)."""

from __future__ import annotations

import re

from apex_rag_demo.response_formatters import strip_ui_region

_BEST_AVAILABLE_RE = re.compile(
    r"\bbest\s+available\b|\bba\s+tickets?\b",
    re.I,
)

_FAN_CUSTOMER_RE = re.compile(
    r"("
    r"\b(show|list|find|search|lookup)\b.*\b(fans?|customers?)\b|"
    r"\b(fans?|customers?)\b.*\b(for|named|matching|with)\b|"
    r"\bcustomer\s+[a-z][a-z0-9_-]{1,40}\b"
    r")",
    re.I,
)

_FAN_INVENTORY_RE = re.compile(
    r"\b(fans?|customers?)\b.*\binventory\b|\binventory\b.*\b(fans?|customers?)\b",
    re.I,
)


def looks_like_best_available_request(question: str) -> bool:
    return bool(_BEST_AVAILABLE_RE.search(strip_ui_region(question)))


def looks_like_fan_or_customer_lookup(question: str) -> bool:
    bare = strip_ui_region(question)
    if looks_like_best_available_request(bare) and re.search(r"\bcustomer\b", bare, re.I):
        return True
    return bool(_FAN_CUSTOMER_RE.search(bare))


def looks_like_fan_inventory_question(question: str) -> bool:
    return bool(_FAN_INVENTORY_RE.search(strip_ui_region(question)))


def extract_customer_lookup_term(question: str) -> str | None:
    bare = strip_ui_region(question)
    for pattern in (
        r"\bcustomer\s+(?:named\s+)?([a-z][a-z0-9 _.-]{1,48})",
        r"\bfor\s+customer\s+([a-z][a-z0-9 _.-]{1,48})",
        r"\bfans?\s+(?:named\s+)?([a-z][a-z0-9 _.-]{1,48})",
        r"\bcustomers?\s+for\s+([^\n.?]{2,60})",
    ):
        m = re.search(pattern, bare, re.I)
        if m:
            term = m.group(1).strip().rstrip(".")
            if term.lower() not in ("email", "inventory", "orders"):
                return term
    return None
