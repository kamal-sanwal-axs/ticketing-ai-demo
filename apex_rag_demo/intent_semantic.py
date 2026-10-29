"""Intent routing via sentence-transformers (always in-process; independent of RAG_EMBEDDING_BACKEND)."""

from __future__ import annotations

from functools import lru_cache

from apex_rag_demo.config import (
    CONVERSATIONAL_MIN_SCORE,
    CONVERSATIONAL_VS_OPS_MARGIN,
    INTENT_SEMANTIC_ENABLED,
    INTENT_SEMANTIC_MARGIN,
    INTENT_SEMANTIC_MIN_SCORE,
    SENTENCE_TRANSFORMERS_MODEL,
)
from apex_rag_demo.intent_helpers import (
    guard_api_intent,
    is_assistant_meta_question,
    is_greeting,
)
from apex_rag_demo.planning import INTENTS
from apex_rag_demo.response_formatters import strip_ui_region

# Exemplar phrases per intent — embedded once after model download.
_INTENT_EXEMPLARS: dict[str, list[str]] = {
    "marketing_events": [
        "show all events",
        "show published events with price codes and ticket types",
        "list every event",
        "show me events",
        "show me events after October 2026",
        "what events are published",
        "browse marketing events catalog",
        "list marketing events",
        "events after this month",
    ],
    "search_customers": [
        "search customers for email",
        "find customer account",
        "lookup fan by email",
        "show me customers named Kamal",
        "show fans with inventory holds",
        "show best available for customer Kamal",
    ],
    "search_orders": [
        "search orders for customer",
        "find order by email",
        "lookup order number",
        "list orders matching",
    ],
    "search_events": [
        "search events for Splash House",
        "find events matching artist name",
        "events named Coachella",
        "lookup event by name",
    ],
    "create_event": [
        "create a new event",
        "add event at client venue",
        "schedule new show on calendar",
        "make a new event",
    ],
    "get_event": [
        "get event details for uuid",
        "show event 8f0a2f5c-9f45-4a7e-93f2-2f6a3f1f2b10",
        "event details for id",
    ],
    "inventory_zones": [
        "inventory zones for event",
        "price levels and sections for event",
        "show best available for event",
        "best available tickets for this event",
    ],
    "list_client_venues": [
        "list all client venues",
        "show client venue registry",
    ],
    "list_users": [
        "list users",
        "show admin users",
    ],
    "publish_event": [
        "publish event to live",
        "publish AINV-2422",
        "publish this event",
    ],
    "update_event": [
        "rename event title",
        "update event headliners",
    ],
    "explain": [
        "how does publish work",
        "what is a client venue",
        "help me understand apex",
        "can you buy one seat for me",
        "purchase a ticket for a fan",
    ],
}

_CONVERSATIONAL_PHRASES: list[str] = [
    "hello",
    "hi there",
    "hey",
    "good morning",
    "good afternoon",
    "how are you",
    "thanks",
    "thank you",
    "nice to meet you",
    "what can you do",
    "how can you help me",
    "getting started",
]

_WRITE_LLM_INTENTS = frozenset(
    {
        "create_event",
        "create_organization",
        "create_client_venue",
        "publish_event",
        "update_event",
        "delete_event",
        "reset_inventory_publish",
    },
)


def _embed_intent_texts(texts: list[str]) -> list[list[float]]:
    """Intent router always uses local sentence-transformers (same weights as embed_server)."""
    from apex_rag_demo.rag.embeddings import embed_texts_inprocess

    return embed_texts_inprocess(texts, log_call=False)


def _cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return -1.0
    return sum(x * y for x, y in zip(a, b, strict=True))


@lru_cache(maxsize=1)
def _exemplar_rows() -> list[tuple[str, str, list[float]]]:
    phrases: list[str] = []
    intents: list[str] = []
    for intent, intent_phrases in _INTENT_EXEMPLARS.items():
        if intent not in INTENTS:
            continue
        for phrase in intent_phrases:
            intents.append(intent)
            phrases.append(phrase)
    if not phrases:
        return []
    vectors = _embed_intent_texts(phrases)
    return list(zip(intents, phrases, vectors, strict=True))


@lru_cache(maxsize=1)
def _exemplar_index() -> tuple[list[str], list[list[float]]]:
    rows = _exemplar_rows()
    if not rows:
        return [], []
    intents = [r[0] for r in rows]
    vectors = [r[2] for r in rows]
    return intents, vectors


def warm_intent_semantic_index() -> None:
    """Download ST weights if needed and build the exemplar embedding index."""
    if not INTENT_SEMANTIC_ENABLED:
        return
    from apex_rag_demo.rag.embeddings import ensure_sentence_transformer_downloaded

    ensure_sentence_transformer_downloaded()
    _exemplar_index()
    print(
        f"--- INTENT SEMANTIC ready ({SENTENCE_TRANSFORMERS_MODEL}, "
        f"{len(_exemplar_index()[0])} exemplars) ---",
        flush=True,
    )


def semantic_closest_exemplar(question: str) -> tuple[str, str, float] | None:
    """Best matching (intent, exemplar phrase, cosine score)."""
    bare = strip_ui_region(question).strip()
    if len(bare) < 4:
        return None
    rows = _exemplar_rows()
    if not rows:
        return None
    q_vec = _embed_intent_texts([bare])[0]
    best: tuple[str, str, float] | None = None
    for intent, phrase, vec in rows:
        score = _cosine(q_vec, vec)
        if best is None or score > best[2]:
            best = (intent, phrase, score)
    return best


def semantic_intent_scores(question: str) -> dict[str, float]:
    """Max cosine per intent using pooled message units (not a single bloated vector)."""
    bare = strip_ui_region(question).strip()
    if len(bare) < 4:
        return {}
    intents, vectors = _exemplar_index()
    if not intents:
        return {}
    from apex_rag_demo.semantic_message import embed_pooled_message, semantic_units

    q_vec = embed_pooled_message(bare)
    if not q_vec:
        return {}
    unit_vecs = _embed_intent_texts(semantic_units(bare))
    scored: dict[str, float] = {}
    for intent, vec in zip(intents, vectors, strict=True):
        pool_score = _cosine(q_vec, vec)
        unit_scores = [_cosine(uv, vec) for uv in unit_vecs] if unit_vecs else [pool_score]
        # Pooled vector + worst unit must agree (reduces single-keyword hijacks).
        combined = 0.55 * pool_score + 0.45 * (sum(unit_scores) / len(unit_scores))
        scored[intent] = max(scored.get(intent, -1.0), combined)
    return scored


def semantic_intent_hint(question: str) -> str | None:
    if not INTENT_SEMANTIC_ENABLED:
        return None
    try:
        scored = semantic_intent_scores(question)
        if not scored:
            return None
        ranked = sorted(scored.items(), key=lambda item: item[1], reverse=True)
        top_intent, top_score = ranked[0]
        second_score = ranked[1][1] if len(ranked) > 1 else -1.0
        if top_score < INTENT_SEMANTIC_MIN_SCORE:
            return None
        if top_score - second_score < INTENT_SEMANTIC_MARGIN:
            return None
        return top_intent
    except Exception as exc:
        print(f"--- INTENT SEMANTIC skipped: {exc} ---", flush=True)
        return None


def conversational_and_operational_scores(question: str) -> tuple[float, float]:
    """Max sentence-transformer similarity to greeting vs API-operation exemplars."""
    bare = strip_ui_region(question).strip()
    if len(bare) < 2:
        return 1.0, 0.0
    from apex_rag_demo.rag.embeddings import similarity_to_references

    conv_sims = similarity_to_references(bare, _CONVERSATIONAL_PHRASES)
    conv_best = max(conv_sims) if conv_sims else 0.0
    op_scores = semantic_intent_scores(bare)
    operational = [score for intent, score in op_scores.items() if intent != "explain"]
    op_best = max(operational) if operational else 0.0
    return conv_best, op_best


def is_conversational_message(question: str) -> bool:
    """Greetings/small-talk — no APEX API call (sentence-transformers + regex)."""
    bare = strip_ui_region(question).strip()
    from apex_rag_demo.compound_request import is_compound_operational_request

    if is_compound_operational_request(question):
        return False
    if is_greeting(bare) or is_assistant_meta_question(bare):
        return True
    if not INTENT_SEMANTIC_ENABLED or len(bare) < 2:
        return False
    try:
        conv, op = conversational_and_operational_scores(bare)
        if conv >= CONVERSATIONAL_MIN_SCORE and conv >= op + CONVERSATIONAL_VS_OPS_MARGIN:
            print(
                f"--- INTENT SEMANTIC conversational=True conv={conv:.2f} op={op:.2f} ---",
                flush=True,
            )
            return True
    except Exception as exc:
        print(f"--- INTENT SEMANTIC conversational check skipped: {exc} ---", flush=True)
    return False


def semantic_intent_override(bare_question: str, llm_intent: str) -> str | None:
    if llm_intent not in _WRITE_LLM_INTENTS:
        return None
    hint = semantic_intent_hint(bare_question)
    if not hint or hint == llm_intent:
        return None
    from apex_rag_demo.crud_policy import WriteKind, write_kind_for_intent

    if write_kind_for_intent(hint) == WriteKind.READ:
        return hint
    return None


def reconcile_classified_intent(llm_intent: str, question: str) -> str:
    """Regex guards first, then sentence-transformer intent when LLM/confidence disagrees."""
    if is_conversational_message(question):
        return "explain"
    guarded = guard_api_intent(llm_intent, question)
    if guarded != llm_intent:
        return guarded

    hint = semantic_intent_hint(question)
    if not hint or hint == guarded:
        return guarded

    from apex_rag_demo.crud_policy import WriteKind, write_kind_for_intent

    hint_kind = write_kind_for_intent(hint)
    llm_kind = write_kind_for_intent(guarded)

    if guarded == "explain" and hint_kind == WriteKind.READ and not is_conversational_message(question):
        print(f"--- INTENT SEMANTIC reconcile explain → {hint} ---", flush=True)
        return hint

    if llm_kind != WriteKind.READ and hint_kind == WriteKind.READ:
        print(f"--- INTENT SEMANTIC reconcile {guarded} → {hint} ---", flush=True)
        return hint

    return guarded


def format_semantic_hint_block(question: str) -> str:
    if not INTENT_SEMANTIC_ENABLED:
        return ""
    hint = semantic_intent_hint(question)
    if not hint:
        return ""
    scores = semantic_intent_scores(question)
    top_score = scores.get(hint, 0.0)
    return (
        f"Sentence-transformer routing hint (validate against the user message; not binding alone): "
        f"intent={hint} (score≈{top_score:.2f})"
    )
