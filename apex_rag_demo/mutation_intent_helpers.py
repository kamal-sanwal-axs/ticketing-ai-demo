from __future__ import annotations

import re

from apex_rag_demo.response_formatters import strip_ui_region

_PUBLISH_EVENT_RE = re.compile(
    r"("
    r"\bpublish\s+(the\s+)?events?\b|"
    r"\bpublish\s+it\b|"
    r"\bevents?\s+.*\bpublish\b|"
    r"\bpublish\b.*\bevent\s+id\b|"
    r"\bpublish\b.*\bAINV-\d+\b|"
    r"\bpublish\b.*\b[0-9a-f]{8}\b"
    r")",
    re.I,
)


def looks_like_publish_event_request(bare_question: str) -> bool:
    return bool(_PUBLISH_EVENT_RE.search(bare_question.strip()))


def resolve_mutation_intent_from_session(
    intent: str,
    question: str,
    session_focus: dict | None,
) -> str:
    """Prefer explicit mutation verbs over chroma-recalled read intents."""
    bare = strip_ui_region(question)
    if looks_like_publish_event_request(bare):
        return "publish_event"
    return intent


def is_session_mutation_followup(bare_question: str) -> bool:
    """Do not reuse a prior read intent from Chroma when user is issuing a mutation."""
    return looks_like_publish_event_request(bare_question)
