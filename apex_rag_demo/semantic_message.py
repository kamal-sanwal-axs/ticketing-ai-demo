"""Whole-message semantics: pool line/paragraph units so one keyword cannot dominate."""

from __future__ import annotations

import math
import re

from apex_rag_demo.intent_semantic import _cosine
from apex_rag_demo.response_formatters import strip_ui_region


def semantic_units(text: str, *, max_units: int = 14) -> list[str]:
    """Full message plus non-trivial lines and sentences for embedding."""
    bare = strip_ui_region(text).strip()
    if not bare:
        return []
    seen: set[str] = set()
    units: list[str] = []

    def add(part: str) -> None:
        p = part.strip()
        if not p or p in seen:
            return
        if len(p) < 3:
            return
        seen.add(p)
        units.append(p)

    add(bare)
    for line in re.split(r"[\n\r]+", bare):
        add(line)
    for sentence in re.split(r"(?<=[.!?])\s+", bare):
        add(sentence)
    return units[:max_units]


def embed_pooled_message(text: str) -> list[float]:
    """Mean-pool normalized embeddings of all semantic units (L2-normalized)."""
    from apex_rag_demo.intent_semantic import _embed_intent_texts

    units = semantic_units(text)
    if not units:
        return []
    vecs = _embed_intent_texts(units)
    if not vecs:
        return []
    dim = len(vecs[0])
    acc = [0.0] * dim
    for vec in vecs:
        for i, val in enumerate(vec):
            acc[i] += val
    norm = math.sqrt(sum(x * x for x in acc)) or 1.0
    return [x / norm for x in acc]


def asymmetric_message_similarity(current: str, prior: str) -> float:
    """
    How well the current message aligns with a prior turn.
    Each current unit must match some prior unit; one shared word cannot carry the whole score.
    """
    from apex_rag_demo.intent_semantic import _embed_intent_texts

    cur_units = semantic_units(current)
    prior_units = semantic_units(prior)
    if not cur_units or not prior_units:
        return 0.0
    cur_vecs = _embed_intent_texts(cur_units)
    prior_vecs = _embed_intent_texts(prior_units)
    if not cur_vecs or not prior_vecs:
        return 0.0
    unit_scores: list[float] = []
    for cv in cur_vecs:
        unit_scores.append(max(_cosine(cv, pv) for pv in prior_vecs))
    return sum(unit_scores) / len(unit_scores)


def history_similarity_to_prior_users(question: str, prior_user_texts: list[str]) -> float:
    if not prior_user_texts:
        return 0.0
    scores = [asymmetric_message_similarity(question, prior) for prior in prior_user_texts[-5:]]
    return max(scores) if scores else 0.0
