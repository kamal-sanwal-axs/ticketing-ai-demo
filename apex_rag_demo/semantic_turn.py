"""Pre-LLM sentence-transformer analysis: topic, intent meaning, history gating."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from apex_rag_demo.config import (
    INTENT_SEMANTIC_ENABLED,
    TOPIC_HISTORY_MIN_SIMILARITY,
    TOPIC_SHIFT_MAX_SIMILARITY,
)
from apex_rag_demo.intent_semantic import (
    is_conversational_message,
    semantic_closest_exemplar,
    semantic_intent_hint,
    semantic_intent_scores,
)
from apex_rag_demo.intent_helpers import is_greeting
from apex_rag_demo.rag.intent_chroma import PreLlmRouting
from apex_rag_demo.response_formatters import strip_ui_region


@dataclass(frozen=True)
class SemanticTurnContext:
    conversational_turn: bool
    topic_shift: bool
    history_similarity: float
    intent_hint: str | None
    closest_phrase: str | None
    closest_intent: str | None
    semantic_score: float
    context_block: str
    chat_messages: list[dict[str, Any]]
    pre_llm: PreLlmRouting | None = None


def _user_texts(messages: list[dict[str, Any]]) -> list[str]:
    out: list[str] = []
    for msg in messages or []:
        if str(msg.get("role") or "").lower() != "user":
            continue
        text = str(msg.get("content") or "").strip()
        if text:
            out.append(text)
    return out


def _filter_history_by_topic(
    question: str,
    messages: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Drop turns whose user text is semantically unrelated to the current question."""
    if not messages or not INTENT_SEMANTIC_ENABLED:
        return list(messages or [])
    bare = strip_ui_region(question).strip()
    users = _user_texts(messages)
    if not users:
        return list(messages)
    from apex_rag_demo.semantic_message import asymmetric_message_similarity

    keep_user: set[str] = set()
    for text in users:
        if asymmetric_message_similarity(bare, text) >= TOPIC_HISTORY_MIN_SIMILARITY:
            keep_user.add(text)

    if not keep_user:
        return []

    filtered: list[dict[str, Any]] = []
    for msg in messages:
        role = str(msg.get("role") or "").lower()
        if role == "user":
            if str(msg.get("content") or "").strip() in keep_user:
                filtered.append(msg)
            else:
                filtered = []
        elif role in ("assistant", "tool"):
            if filtered:
                filtered.append(msg)
        else:
            filtered.append(msg)
    return filtered


def prepare_semantic_turn(
    question: str,
    chat_messages: list[dict[str, Any]] | None,
) -> SemanticTurnContext:
    bare = strip_ui_region(question).strip()
    messages = list(chat_messages or [])
    prior_users = _user_texts(messages)

    from apex_rag_demo.compound_request import is_compound_operational_request
    from apex_rag_demo.rag.intent_chroma import resolve_pre_llm_routing

    pre_llm = resolve_pre_llm_routing(question)
    compound = is_compound_operational_request(question)
    conversational = (is_conversational_message(bare) or is_greeting(bare)) and not compound

    if compound:
        intent_hint = "marketing_events"
    elif conversational:
        intent_hint = None
    else:
        intent_hint = semantic_intent_hint(bare) if INTENT_SEMANTIC_ENABLED else None
    closest = semantic_closest_exemplar(bare) if INTENT_SEMANTIC_ENABLED else None
    closest_intent = closest[0] if closest else None
    closest_phrase = closest[1] if closest else None
    closest_score = closest[2] if closest else 0.0

    from apex_rag_demo.semantic_message import history_similarity_to_prior_users

    history_similarity = 0.0
    topic_shift = False
    filtered_messages: list[dict[str, Any]] = []

    if not prior_users:
        topic_shift = True
        filtered_messages = []
    elif conversational:
        topic_shift = True
        filtered_messages = []
        history_similarity = 0.0
    elif INTENT_SEMANTIC_ENABLED:
        try:
            history_similarity = history_similarity_to_prior_users(bare, prior_users)
            topic_shift = history_similarity < TOPIC_SHIFT_MAX_SIMILARITY
        except Exception as exc:
            print(f"--- SEMANTIC TURN topic check skipped: {exc} ---", flush=True)
            topic_shift = True

    if not conversational and prior_users:
        if topic_shift:
            filtered_messages = []
        else:
            filtered_messages = _filter_history_by_topic(bare, messages)

    scores = semantic_intent_scores(bare) if INTENT_SEMANTIC_ENABLED else {}
    top_score = max(scores.values()) if scores else closest_score

    lines = [
        "--- Pre-LLM semantic routing (Chroma intent routes + embeddings; apply BEFORE classify LLM) ---",
        f"User message (authoritative): {bare[:500]}",
    ]
    if pre_llm:
        lines.append(pre_llm.label)
        if pre_llm.hits:
            for h in pre_llm.hits[:2]:
                lines.append(
                    f"Chroma neighbor: intent={h.intent} score={h.score:.2f} "
                    f"prompt=\"{h.prompt[:120]}\"",
                )
    lines.append("--- Sentence-transformer turn analysis ---")
    if conversational:
        lines.append(
            "Conversational turn: YES — greet the user warmly; do NOT call events/marketing/search APIs.",
        )
    elif compound:
        lines.append(
            "Compound operational request: YES — list published/on-sale events, then inventory "
            "(price codes, ticket types, seat-level) per event via orchestrator (do NOT answer from docs).",
        )
    elif intent_hint:
        lines.append(f"Inferred API intent (embedding): {intent_hint} (confidence≈{top_score:.2f})")
    elif closest_intent:
        lines.append(
            f"Nearest exemplar intent: {closest_intent} — “{closest_phrase}” (≈{closest_score:.2f})",
        )
    if topic_shift:
        lines.append(
            "Topic shift: YES — prior turns are about a different subject. "
            "Ignore earlier assistant errors, intents, and API traces. "
            "Route and answer ONLY this message.",
        )
    else:
        lines.append(
            f"Topic shift: no (similarity to recent user turns≈{history_similarity:.2f}). "
            "You may use filtered chat history when it matches this topic.",
        )
    lines.append(
        "Do not blend unrelated prior topics (e.g. create-event failure + list-events) in one answer.",
    )

    print(
        f"--- SEMANTIC TURN conv={conversational} shift={topic_shift} hint={intent_hint} "
        f"hist_sim={history_similarity:.2f} kept_turns={len(filtered_messages)} ---",
        flush=True,
    )

    return SemanticTurnContext(
        conversational_turn=conversational,
        topic_shift=topic_shift,
        history_similarity=history_similarity,
        intent_hint=intent_hint,
        closest_phrase=closest_phrase,
        closest_intent=closest_intent,
        semantic_score=top_score,
        context_block="\n".join(lines),
        chat_messages=filtered_messages,
        pre_llm=pre_llm,
    )
