"""TestRail / MFE integration catalog for assistant routing and KB."""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

from apex_rag_demo.config import DATA_DIR
from apex_rag_demo.mfe_scope import OPERATIONAL_INTENTS

_CATALOG_PATH = DATA_DIR / "testrail_catalog.json"
_HARNESS_PATH = DATA_DIR / "ai_harness_prompts.json"


@lru_cache(maxsize=1)
def load_catalog() -> dict[str, Any]:
    if not _CATALOG_PATH.is_file():
        return {"entries": [], "entry_count": 0}
    return json.loads(_CATALOG_PATH.read_text(encoding="utf-8"))


def catalog_entries() -> list[dict[str, Any]]:
    return list(load_catalog().get("entries") or [])


@lru_cache(maxsize=1)
def load_harness_prompts() -> list[dict[str, Any]]:
    if not _HARNESS_PATH.is_file():
        return []
    return list(json.loads(_HARNESS_PATH.read_text(encoding="utf-8")))


def catalog_kb_texts(max_entries: int = 400) -> list[tuple[str, str]]:
    """(id, text) for Chroma — operational TestRail rows only (no layout/MFE trivia)."""
    out: list[tuple[str, str]] = []
    for row in catalog_entries():
        if len(out) >= max_entries:
            break
        intent = row.get("assistant_intent")
        prompt = row.get("example_prompt")
        if not prompt or intent not in OPERATIONAL_INTENTS:
            continue
        tid = row.get("testrail_id") or row.get("jira") or "spec"
        mfe = row.get("mfe") or row.get("service") or "apex"
        title = str(row.get("title") or "")[:200]
        text = (
            f"TestRail [{mfe}] {tid} intent={intent}. "
            f"Scenario: {title}. "
            f"Operator prompt: {prompt}."
        )
        cid = f"testrail-{tid}-{hash(title) % 100000}"
        out.append((cid, text))
    for row in load_harness_prompts():
        if len(out) >= max_entries:
            break
        intent = row.get("expected_intent")
        prompt = row.get("prompt")
        if not prompt or not intent:
            continue
        hid = str(row.get("id") or "harness")
        text = f"Harness intent={intent} mfe={row.get('mfe')}. Operator prompt: {prompt}."
        out.append((f"harness-{hid}", text))
    return out


def match_catalog_intent_hint(question: str) -> str | None:
    """Keyword routing aligned with TestRail operator flows."""
    from apex_rag_demo.fan_purchase import looks_like_fan_purchase_request
    from apex_rag_demo.operational_intent_helpers import (
        looks_like_best_available_request,
        looks_like_fan_inventory_question,
        looks_like_fan_or_customer_lookup,
    )
    from apex_rag_demo.order_intent_helpers import (
        looks_like_customer_search_request,
        looks_like_order_search_request,
    )

    bare = question.lower()
    if looks_like_fan_purchase_request(question):
        return "explain"
    if looks_like_best_available_request(question):
        if re.search(r"\bcustomer\b|\bfan\b", bare):
            return "search_customers"
        return "inventory_zones"
    if looks_like_order_search_request(question):
        if "payment status" in bare or "payment statuses" in bare:
            return "search_order_payment_statuses"
        return "search_orders"
    if looks_like_fan_inventory_question(question):
        return "search_customers"
    if looks_like_customer_search_request(question) or looks_like_fan_or_customer_lookup(question):
        return "search_customers"
    return None
