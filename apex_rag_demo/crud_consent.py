from __future__ import annotations

from typing import Any

from apex_rag_demo.crud_policy import (
    mutation_executes_live,
    requires_human_confirmation,
    write_kind_for_intent,
    WriteKind,
)
from apex_rag_demo.mutation_token import issue_mutation_token, verify_mutation_token


def _plans_match(stored: dict[str, Any], current: dict[str, Any]) -> bool:
    for key, value in (stored or {}).items():
        if current.get(key) != value:
            return False
    return True


def build_pending_confirmation(
    intent: str,
    plan: dict[str, Any],
    preview: dict[str, Any] | None = None,
) -> dict[str, Any]:
    kind = write_kind_for_intent(intent)
    token = issue_mutation_token(intent, plan)
    return {
        "_pending_confirmation": True,
        "intent": intent,
        "writeKind": kind.value,
        "plan": plan,
        "preview": preview or {},
        "mutation_token": token,
        "message": (
            f"This {kind.value} requires your confirmation before it runs in apex-dev. "
            "Review the details, then click Confirm."
        ),
    }


def consent_allows_execution(
    intent: str,
    *,
    mutations_dry_run: bool,
    confirm_mutation: bool,
    mutation_token: str | None,
    action_plan: dict[str, Any],
) -> tuple[bool, str | None]:
    kind = write_kind_for_intent(intent)
    if kind == WriteKind.READ:
        return True, None

    if not mutation_executes_live(
        intent,
        confirm_mutation=confirm_mutation,
        mutations_dry_run=mutations_dry_run,
    ):
        return True, None  # dry-run path in clients

    if kind == WriteKind.RESET:
        return True, None

    if requires_human_confirmation(intent):
        if not confirm_mutation:
            return False, "confirmation_required"
        if not mutation_token:
            return False, "missing_mutation_token"
        verified = verify_mutation_token(mutation_token)
        if not verified:
            return False, "invalid_mutation_token"
        if verified.get("intent") != intent:
            return False, "intent_mismatch"
        if not _plans_match(verified.get("plan") or {}, action_plan):
            return False, "plan_mismatch"
        return True, None

    return True, None
