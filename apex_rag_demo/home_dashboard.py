"""axs-apex-home (APEX v2 dashboard) and axs-b2b-dashboard (v1) — TestRail-aligned guidance."""

from __future__ import annotations

import re
from typing import Any

from apex_rag_demo.response_formatters import strip_ui_region

_HOME_DASHBOARD_RE = re.compile(
    r"("
    r"\b(axs[- ]?apex[- ]?home|apex home|home page|homepage)\b|"
    r"\b(axs[- ]?apex[- ]?dashboard|home dashboard)\b|"
    r"\bupcoming events\b.*\b(home|dashboard)\b|"
    r"\btestrail\s+C9203\b|"
    r"\bhome[- ]layout[- ]shell\b|"
    r"\bview all events\b.*\bhome\b"
    r")",
    re.I,
)

_B2B_DASHBOARD_RE = re.compile(
    r"("
    r"\b(axs[- ]?b2b[- ]?dashboard|b2b dashboard|ticketing dashboard)\b|"
    r"\bdashboard_QA\d|"
    r"/dashboard\b.*\b(v1|ticketing)\b"
    r")",
    re.I,
)

_UPCOMING_ON_HOME_RE = re.compile(
    r"\b(upcoming|no upcoming)\b.*\bevents?\b|\bhome\b.*\bupcoming\b",
    re.I,
)


def looks_like_home_dashboard_question(question: str) -> bool:
    bare = strip_ui_region(question)
    if _B2B_DASHBOARD_RE.search(bare):
        return False
    return bool(_HOME_DASHBOARD_RE.search(bare))


def looks_like_b2b_dashboard_question(question: str) -> bool:
    return bool(_B2B_DASHBOARD_RE.search(strip_ui_region(question)))


def home_requests_upcoming_events_api(question: str) -> bool:
    return bool(_UPCOMING_ON_HOME_RE.search(strip_ui_region(question)))


def format_home_dashboard_guidance() -> str:
    return "\n".join(
        [
            "**axs-apex-home** (APEX v2 — also called the home **dashboard**; remote `home_QA_APEX`):",
            "",
            "| TestRail | What it covers | Assistant |",
            "|----------|----------------|-----------|",
            "| **C9203PILOT** | Layout shell renders routed content (QAA-9203) | UI smoke — `explain` |",
            "| HOME-FUNC-* | Upcoming events, empty state, errors (unit tests) | **marketing_events** / **search_events** for live lists |",
            "",
            "The home page loads upcoming events via events API hooks — this chat uses **marketing_events** "
            "or **search events matching …** instead of driving the React UI.",
            "",
            "Try: `show all events`, `show on-sale events`, or `what does the home dashboard show?`",
            "",
            "Note: **C9200PILOT** is the **events** MFE dashboard shell (`axs-apex-events`), not home.",
        ],
    )


def format_b2b_dashboard_guidance() -> str:
    return "\n".join(
        [
            "**axs-b2b-dashboard** (v1 ticketing remote `dashboard_QA5_US` / prod hosts):",
            "",
            "Legacy B2B home/dashboard (greeting, offers, knowledge base cards). "
            "No TestRail export in-repo — catalog rows **B2B-DASH-*** map unit tests.",
            "",
            "This assistant does not mount v1 dashboard UI. Use **search_orders**, **search_customers**, "
            "or **search events** for operational data on apex-dev.",
        ],
    )


def build_home_dashboard_display() -> dict[str, Any]:
    return {
        "type": "article",
        "title": "APEX home dashboard (axs-apex-home)",
        "badge": "explain",
        "level": "info",
        "paragraphs": [
            "TestRail C9203PILOT — layout shell. Functional upcoming-events behavior is covered by HOME-FUNC catalog rows; "
            "live event data comes from marketing/search APIs in this assistant.",
        ],
        "sections": [
            {
                "title": "TestRail (home)",
                "table": {
                    "columns": [
                        {"key": "id", "label": "Case"},
                        {"key": "scope", "label": "Scope"},
                    ],
                    "rows": [
                        {"id": "C9203PILOT", "scope": "Default layout + routed child (integration UI)"},
                        {"id": "HOME-FUNC-01", "scope": "Homepage / upcoming events section renders"},
                        {"id": "HOME-FUNC-07", "scope": "Empty state — no upcoming events"},
                        {"id": "HOME-FUNC-05", "scope": "Events query error message"},
                    ],
                },
            },
        ],
        "citations": [
            {
                "label": "Spec home-layout-shell",
                "href": "axs-apex-home/tests/integration/specifications/home-layout-shell.md",
                "status": "doc",
            },
        ],
    }


def build_b2b_dashboard_display() -> dict[str, Any]:
    return {
        "type": "article",
        "title": "B2B dashboard (v1)",
        "badge": "explain",
        "level": "info",
        "paragraphs": [format_b2b_dashboard_guidance()],
    }
