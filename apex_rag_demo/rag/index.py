from __future__ import annotations

import numpy as np

from apex_rag_demo.config import (
    CACHE_DIR,
    INDEX_PATH,
    RAG_KEYWORD_FALLBACK,
    RAG_RETRIEVE_K,
    RAG_VECTOR_STORE,
    TOP_K,
)
from apex_rag_demo.rag.rerank import rerank_texts
from apex_rag_demo.rag.embeddings import embed_texts
from apex_rag_demo.rag.kb import KbChunk, load_kb

# Re-export for callers
__all__ = ["KbChunk", "load_kb", "retrieve", "build_or_load_index"]


def _normalize(vectors: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    norms = np.where(norms == 0, 1, norms)
    return vectors / norms


def build_or_load_index() -> tuple[list[KbChunk], np.ndarray]:
    chunks = load_kb()
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    if INDEX_PATH.exists():
        data = np.load(INDEX_PATH, allow_pickle=True)
        stored_chunks = data["chunks"].tolist()
        if len(stored_chunks) == len(chunks) and all(
            a["id"] == b.id and a["text"] == b.text
            for a, b in zip(stored_chunks, chunks, strict=True)
        ):
            return chunks, data["vectors"]

    try:
        vectors = np.array(embed_texts([c.text for c in chunks]), dtype=np.float32)
        vectors = _normalize(vectors)
    except Exception:
        if not RAG_KEYWORD_FALLBACK:
            raise
        vectors = np.zeros((len(chunks), 1), dtype=np.float32)
    np.savez(
        INDEX_PATH,
        vectors=vectors,
        chunks=np.array([{"id": c.id, "text": c.text} for c in chunks], dtype=object),
    )
    return chunks, vectors


def _keyword_retrieve(question: str, chunks: list[KbChunk], top_k: int) -> list[str]:
    terms = {t.lower() for t in question.split() if len(t) > 2}
    scored: list[tuple[int, str]] = []
    for chunk in chunks:
        text_lower = chunk.text.lower()
        score = sum(1 for t in terms if t in text_lower)
        scored.append((score, chunk.text))
    scored.sort(key=lambda x: -x[0])
    return [text for _, text in scored[:top_k]]


def _retrieve_numpy(question: str, fetch_k: int) -> list[str]:
    chunks, matrix = build_or_load_index()
    if matrix.shape[1] == 1:
        return _keyword_retrieve(question, chunks, fetch_k)
    q = np.array(embed_texts([question]), dtype=np.float32)
    q = _normalize(q)[0]
    scores = matrix @ q
    order = np.argsort(-scores)[:fetch_k]
    return [chunks[i].text for i in order]


def _log_bi_encoder_candidates(candidates: list[str]) -> None:
    print("--- RETRIEVING DOCS (Bi-Encoder) ---", flush=True)
    for i, doc in enumerate(candidates):
        preview = doc.replace("\n", " ")[:120]
        print(f"[Bi-Encoder {i + 1}] {preview}...", flush=True)


def retrieve_bi_encoder_candidates(question: str, fetch_k: int) -> list[str]:
    """Phase 1: vector / HNSW fetch (Chroma apex_kb or numpy), no cross-encoder."""
    if RAG_VECTOR_STORE == "chroma":
        try:
            from apex_rag_demo.rag.chroma_store import query_chroma

            candidates = query_chroma(question, fetch_k)
            _log_bi_encoder_candidates(candidates)
            return candidates
        except Exception:
            if not RAG_KEYWORD_FALLBACK:
                raise
            try:
                candidates = _retrieve_numpy(question, fetch_k)
                _log_bi_encoder_candidates(candidates)
                return candidates
            except Exception:
                candidates = _keyword_retrieve(question, load_kb(), fetch_k)
                _log_bi_encoder_candidates(candidates)
                return candidates

    try:
        candidates = _retrieve_numpy(question, fetch_k)
        _log_bi_encoder_candidates(candidates)
        return candidates
    except Exception:
        if not RAG_KEYWORD_FALLBACK:
            raise
        candidates = _keyword_retrieve(question, load_kb(), fetch_k)
        _log_bi_encoder_candidates(candidates)
        return candidates


def rerank_retrieval_candidates(
    question: str,
    candidates: list[str],
    top_k: int = TOP_K,
    *,
    intent_hint: str | None = None,
) -> list[str]:
    """Phase 2: cross-encoder rerank (sentence-transformers CrossEncoder)."""
    return rerank_texts(question, candidates, top_k, intent_hint=intent_hint)


def retrieve(question: str, top_k: int = TOP_K) -> list[str]:
    fetch_k = max(top_k, RAG_RETRIEVE_K)
    candidates = retrieve_bi_encoder_candidates(question, fetch_k)
    return rerank_retrieval_candidates(question, candidates, top_k)
