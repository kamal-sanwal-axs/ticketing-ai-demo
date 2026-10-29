from __future__ import annotations

import re

_EVENT_NAME_ONLY_RE = re.compile(
    r"("
    r"\bevent\s+names?\s+only\b|"
    r"\bonly\s+(the\s+)?event\s+names?\b|"
    r"\bshow\s+event\s+names?\s+only\b|"
    r"\bnames?\s+only\b.*\bevents?\b|"
    r"\bevents?\b.*\bnames?\s+only\b"
    r")",
    re.I,
)

_EVENT_ONLY_RE = re.compile(
    r"("
    r"\bonly\b|"
    r"\bjust\s+the\s+event\b|"
    r"\bevent\s+details?\s+only\b|"
    r"\bdetails?\s+only\b|"
    r"\bwithout\s+inventory\b|"
    r"\bno\s+inventory\b|"
    r"\bexclude\s+inventory\b"
    r")",
    re.I,
)

_EVENT_FULL_RE = re.compile(
    r"("
    r"\bwith\s+inventory\b|"
    r"\bincluding\s+inventory\b|"
    r"\bfull\s+details?\b|"
    r"\bprice\s+levels?\b|"
    r"\bprice\s+codes?\b|"
    r"\bsections?\b|"
    r"\bprimary\s+zone\b|"
    r"\binventory\s+snapshot\b|"
    r"\borg\s+hierarchy\b|"
    r"\bwith\s+org\b|"
    r"\bticket\s+types?\b|"
    r"\bvenue\s+details?\b"
    r")",
    re.I,
)

_INVENTORY_FOLLOWUP_RE = re.compile(
    r"("
    r"\bprice\s+levels?\b|"
    r"\bprice\s+codes?\b|"
    r"\bsections?\b|"
    r"\bprimary\s+zone\b|"
    r"\binventory\b|"
    r"\bzones?\b|"
    r"\bticket\s+types?\b|"
    r"\bvenue\s+details?\b"
    r")",
    re.I,
)

_HTML_TAG_RE = re.compile(r"<[^>]+>")


def wants_event_names_only(bare_question: str) -> bool:
    return bool(_EVENT_NAME_ONLY_RE.search(bare_question))


def wants_event_details_only(bare_question: str) -> bool:
    return bool(_EVENT_ONLY_RE.search(bare_question))


def wants_event_full_enrichment(bare_question: str) -> bool:
    return bool(_EVENT_FULL_RE.search(bare_question))


def looks_like_event_inventory_followup(bare_question: str) -> bool:
    """Inventory / seating detail asks without necessarily naming 'event'."""
    from apex_rag_demo.intent_helpers import wants_list_client_venues

    if wants_list_client_venues(bare_question):
        return False
    b = bare_question.lower()
    if re.search(r"\bclient[- ]?venues?\b", b) and re.search(r"\b(list|all|every)\b", b):
        return False
    return bool(_INVENTORY_FOLLOWUP_RE.search(bare_question))


def get_event_enrichment_flags(bare_question: str) -> dict[str, bool]:
    """Default: events-api fields only. Opt in to inventory/org with explicit phrases."""
    from apex_rag_demo.inventory_assessment import looks_like_price_code_setup_question

    if looks_like_price_code_setup_question(bare_question):
        return {
            "includeInventory": True,
            "includeOrgHierarchy": False,
            "includeTicketTypes": False,
        }
    if wants_event_details_only(bare_question):
        return {
            "includeInventory": False,
            "includeOrgHierarchy": False,
            "includeTicketTypes": False,
        }
    if wants_event_full_enrichment(bare_question):
        include_tt = bool(re.search(r"\bticket\s+types?\b", bare_question, re.I))
        return {
            "includeInventory": True,
            "includeOrgHierarchy": True,
            "includeTicketTypes": include_tt,
        }
    return {"includeInventory": False, "includeOrgHierarchy": False, "includeTicketTypes": False}


def strip_html_text(value: str) -> str:
    return _HTML_TAG_RE.sub("", value).strip()
