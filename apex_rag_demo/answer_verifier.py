"""Verify assistant text only cites UUIDs present in API facts."""

from __future__ import annotations

import re
from typing import Any

_UUID_RE = re.compile(
    r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b",
    re.I,
)


def verify_answer_uuids(answer: str, api_facts: dict[str, Any] | None) -> tuple[bool, list[str]]:
    if not answer or not api_facts:
        return True, []
    allowed = set(api_facts.get("all_uuids") or [])
    if not allowed:
        return True, []
    cited = set(_UUID_RE.findall(answer))
    extra = sorted(cited - allowed)
    return len(extra) == 0, extra


def strip_ungrounded_uuids(answer: str, api_facts: dict[str, Any] | None) -> str:
    ok, extra = verify_answer_uuids(answer, api_facts)
    if ok or not extra:
        return answer
    lines = [
        answer.strip(),
        "",
        "Note: Removed unverified event IDs from the narrative. See the table or API facts for authoritative IDs.",
    ]
    out = lines[0]
    for bad in extra:
        out = out.replace(bad, "—")
    if len(lines) > 2:
        out = "\n".join([out, *lines[1:]])
    return out
