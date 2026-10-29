from __future__ import annotations

import os
import re
from functools import lru_cache

os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
os.environ.setdefault("LOKY_MAX_CPU_COUNT", "1")

from apex_rag_demo.config import RAG_RERANK_ENABLED, RAG_RERANK_MODEL

_KB_INTENT_TAG = re.compile(r"\bintent=([a-z_]+)\b", re.I)
# Tie-break when cross-encoder scores are flat (~0.01–0.03 on TestRail boilerplate).
_INTENT_HINT_BOOST = 0.04


@lru_cache(maxsize=1)
def _cross_encoder():
    from sentence_transformers import CrossEncoder

    return CrossEncoder(RAG_RERANK_MODEL)


def rerank_texts(
    query: str,
    documents: list[str],
    top_n: int,
    *,
    intent_hint: str | None = None,
) -> list[str]:
    """Cross-encoder rerank after bi-encoder vector retrieval."""
    if not documents:
        return []
    if not RAG_RERANK_ENABLED or len(documents) <= top_n:
        return documents[:top_n]

    print("--- RERANKING DOCS (Cross-Encoder) ---", flush=True)
    print(f"Model: {RAG_RERANK_MODEL}", flush=True)
    if intent_hint:
        print(f"Intent hint boost (KB metadata): {intent_hint}", flush=True)
    model = _cross_encoder()
    pairs = [[query, doc] for doc in documents]
    scores = model.predict(pairs)
    scored_docs: list[tuple[float, str]] = []
    for raw_score, doc in zip(scores, documents, strict=True):
        score = float(raw_score)
        if intent_hint:
            m = _KB_INTENT_TAG.search(doc)
            if m and m.group(1).lower() == intent_hint.strip().lower():
                score += _INTENT_HINT_BOOST
        scored_docs.append((score, doc))
    ranked = sorted(scored_docs, key=lambda row: row[0], reverse=True)
    for i, (score, doc) in enumerate(ranked[:top_n]):
        preview = doc.replace("\n", " ")[:120]
        print(f"[Rank {i + 1}] score={float(score):.4f} {preview}...", flush=True)

    return [doc for _, doc in ranked[:top_n]]
