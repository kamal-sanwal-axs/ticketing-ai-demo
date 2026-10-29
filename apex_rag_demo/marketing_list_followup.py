"""Follow-ups on a prior marketing events table (group/sort) — no new admin POST."""

from __future__ import annotations

import re
from typing import Any

from apex_rag_demo.rag.session_memory import (
    load_last_client_venues_payload,
    load_last_marketing_payload,
)
from apex_rag_demo.response_formatters import strip_ui_region

_PRONOUN_FOLLOWUP_RE = re.compile(
    r"\b(them|those|these|that list|the events|above|below|same events|prior list)\b",
    re.I,
)
_REFORMAT_VERB_RE = re.compile(
    r"\b(group(?:ed)?|bucket|sort|organize|organise|break\s+down|cluster|arrange)\b",
    re.I,
)
_NOW_FOLLOWUP_RE = re.compile(r"^\s*now\b", re.I)
_GROUP_BY_ORG_RE = re.compile(
    r"\b(by|per)\s+(their\s+)?(organization|organisations?|org\b|orgs\b|"
    r"principal|contractual|client|hierarchy)\b|"
    r"\bgroup\s+(them|those|these|events)\s+by\s+(their\s+)?(organization|org)\b|"
    r"\b(organization|org)\s+(group|bucket|column)\b",
    re.I,
)
_GROUP_BY_DATE_RE = re.compile(
    r"\b(by|per)\s+(start\s+date|date|month|week)\b|"
    r"\bgroup\s+by\s+start\b",
    re.I,
)
_CREATE_ORG_RE = re.compile(
    r"\b(create|add|make|register|new)\s+(an?\s+)?(organization|organisation|org)\b",
    re.I,
)
_PIE_CHART_RE = re.compile(r"\bpie\s+chart\b|\bpie\b.*\bchart\b", re.I)
_CLIENT_VENUE_REF = re.compile(r"\bclient\s+venues?\b", re.I)
_WIDEN_LIST_RE = re.compile(
    r"\b(no events?|none\b|empty\b|zero\b|couldn'?t group|can't group|"
    r"get events above|events above|without (the )?filter|remove (the )?filter|"
    r"show (me )?all|widen|broader)\b",
    re.I,
)


def looks_like_explicit_create_organization(question: str) -> bool:
    return bool(_CREATE_ORG_RE.search(strip_ui_region(question)))


def looks_like_marketing_list_reformat(question: str) -> bool:
    bare = strip_ui_region(question)
    if _GROUP_BY_ORG_RE.search(bare) or _GROUP_BY_DATE_RE.search(bare):
        return True
    if _REFORMAT_VERB_RE.search(bare) and (
        _PRONOUN_FOLLOWUP_RE.search(bare) or _NOW_FOLLOWUP_RE.search(bare)
    ):
        return True
    return False


def resolve_marketing_group_by(question: str) -> str | None:
    bare = strip_ui_region(question)
    if _GROUP_BY_ORG_RE.search(bare):
        return "organization"
    if _GROUP_BY_DATE_RE.search(bare) or wants_timeline_group(bare):
        return "start_date"
    if _REFORMAT_VERB_RE.search(bare):
        return "organization"
    return None


def wants_timeline_group(bare: str) -> bool:
    from apex_rag_demo.ui_schema import wants_event_timeline_chart

    return wants_event_timeline_chart(bare)


def looks_like_widen_marketing_list(question: str) -> bool:
    return bool(_WIDEN_LIST_RE.search(strip_ui_region(question)))


def session_had_marketing_list(session_focus: dict[str, Any] | None) -> bool:
    focus = session_focus or {}
    return bool(focus.get("hasMarketingList") or focus.get("lastIntent") == "marketing_events")


def looks_like_client_venue_display_followup(question: str) -> bool:
    bare = strip_ui_region(question)
    if not _CLIENT_VENUE_REF.search(bare):
        return False
    return (
        looks_like_marketing_list_reformat(bare)
        or bool(_PIE_CHART_RE.search(bare))
        or bool(_REFORMAT_VERB_RE.search(bare) and re.search(r"\bresponse\b", bare, re.I))
    )


def session_had_client_venue_list(session_focus: dict[str, Any] | None) -> bool:
    focus = session_focus or {}
    return bool(focus.get("hasClientVenueList") or focus.get("lastIntent") == "list_client_venues")


def try_marketing_list_followup_step(
    question: str,
    *,
    session_focus: dict[str, Any] | None,
    user_id: str = "",
    session_id: str = "",
) -> dict[str, Any] | None:
    """Re-display or widen prior marketing list — never create_organization."""
    bare = strip_ui_region(question)
    if looks_like_explicit_create_organization(bare):
        return None

    if looks_like_client_venue_display_followup(bare):
        had_cv = session_had_client_venue_list(session_focus)
        cached_cv = load_last_client_venues_payload(user_id, session_id) if user_id and session_id else None
        if had_cv or cached_cv:
            group_by = resolve_marketing_group_by(bare) or "organization"
            plan: dict[str, Any] = {
                "_followup_group_by": group_by,
                "_reuse_session_list": True,
                "_list_kind": "client_venues",
            }
            if _PIE_CHART_RE.search(bare):
                plan["_pie_chart"] = True
            print("--- ORCHESTRATOR client-venue follow-up: regroup cached list ---", flush=True)
            return {
                "orchestrator_action": "finish",
                "intent": "list_client_venues",
                "action_plan": plan,
                "orchestrator_reason": "client_venue_list_reformat",
            }

    had_list = session_had_marketing_list(session_focus)
    cached = load_last_marketing_payload(user_id, session_id) if user_id and session_id else None
    if not had_list and not cached:
        return None

    if looks_like_widen_marketing_list(bare):
        print("--- ORCHESTRATOR marketing follow-up: widen list (clear date filter) ---", flush=True)
        return {
            "orchestrator_action": "call_api",
            "intent": "marketing_events",
            "action_plan": {"pageSize": 25, "_followup_widen": True},
            "orchestrator_reason": "marketing_widen_list",
        }

    if not looks_like_marketing_list_reformat(bare):
        return None

    group_by = resolve_marketing_group_by(bare) or "organization"
    print(f"--- ORCHESTRATOR marketing follow-up: group by {group_by} (session cache) ---", flush=True)
    plan: dict[str, Any] = {
        "_followup_group_by": group_by,
        "_reuse_session_list": True,
    }
    if group_by == "organization":
        plan["_display_org_hierarchy"] = True
    return {
        "orchestrator_action": "finish",
        "intent": "marketing_events",
        "action_plan": plan,
        "orchestrator_reason": "marketing_list_reformat",
    }


def apply_marketing_session_reuse(state: dict[str, Any]) -> dict[str, Any]:
    """Inject cached marketing or client-venue payload for follow-up display."""
    plan = state.get("action_plan") if isinstance(state.get("action_plan"), dict) else {}
    if not plan.get("_reuse_session_list") and not plan.get("_followup_group_by"):
        return state
    user_id = str(state.get("user_id") or "")
    session_id = str(state.get("session_id") or "")
    if plan.get("_list_kind") == "client_venues" or state.get("intent") == "list_client_venues":
        cached = load_last_client_venues_payload(user_id, session_id)
        if cached:
            return {
                **state,
                "intent": "list_client_venues",
                "api_payload": cached,
                "api_error": None,
            }
        return state
    cached = load_last_marketing_payload(user_id, session_id)
    if not cached:
        return state
    return {**state, "intent": "marketing_events", "api_payload": cached, "api_error": None}
