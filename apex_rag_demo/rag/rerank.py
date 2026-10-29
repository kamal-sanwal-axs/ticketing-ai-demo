from __future__ import annotations

from functools import lru_cache

from apex_rag_demo.config import RAG_RERANK_ENABLED, RAG_RERANK_MODEL


@lru_cache(maxsize=1)
def _cross_encoder():
    from sentence_transformers import CrossEncoder

    return CrossEncoder(RAG_RERANK_MODEL)


def rerank_texts(query: str, documents: list[str], top_n: int) -> list[str]:
    """Cross-encoder rerank after bi-encoder vector retrieval."""
    if not documents:
        return []
    if not RAG_RERANK_ENABLED or len(documents) <= top_n:
        return documents[:top_n]

    print("--- RERANKING DOCS (Cross-Encoder) ---", flush=True)
    print(f"Model: {RAG_RERANK_MODEL}", flush=True)
    model = _cross_encoder()
    pairs = [[query, doc] for doc in documents]
    scores = model.predict(pairs)
    ranked = sorted(
        zip(scores, documents, strict=True),
        key=lambda row: float(row[0]),
        reverse=True,
    )
    for i, (score, doc) in enumerate(ranked[:top_n]):
        preview = doc.replace("\n", " ")[:120]
        print(f"[Rank {i + 1}] score={float(score):.4f} {preview}...", flush=True)

    return [doc for _, doc in ranked[:top_n]]
