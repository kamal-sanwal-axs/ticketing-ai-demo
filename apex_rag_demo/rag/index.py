from __future__ import annotations

import json
from dataclasses import dataclass

import numpy as np

from apex_rag_demo.clients.llama import embed_texts
from apex_rag_demo.config import CACHE_DIR, INDEX_PATH, KB_PATH, RAG_KEYWORD_FALLBACK, TOP_K


@dataclass
class KbChunk:
    id: str
    text: str


def load_kb() -> list[KbChunk]:
    raw = json.loads(KB_PATH.read_text(encoding="utf-8"))
    return [KbChunk(id=item["id"], text=item["text"]) for item in raw]


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


def retrieve(question: str, top_k: int = TOP_K) -> list[str]:
    chunks, matrix = build_or_load_index()
    if matrix.shape[1] == 1:
        return _keyword_retrieve(question, chunks, top_k)
    try:
        q = np.array(embed_texts([question]), dtype=np.float32)
        q = _normalize(q)[0]
        scores = matrix @ q
        order = np.argsort(-scores)[:top_k]
        return [chunks[i].text for i in order]
    except Exception:
        if not RAG_KEYWORD_FALLBACK:
            raise
        return _keyword_retrieve(question, chunks, top_k)
