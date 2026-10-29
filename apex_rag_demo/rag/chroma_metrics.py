"""Chroma HNSW space + distance → similarity (matches L2-normalized embedder output)."""

from __future__ import annotations

import math

from apex_rag_demo.config import CHROMA_HNSW_SPACE


def chroma_collection_metadata(extra: dict | None = None) -> dict:
    """Collection metadata for create_collection (includes hnsw:space)."""
    meta = {"hnsw:space": CHROMA_HNSW_SPACE}
    if extra:
        meta.update(extra)
    return meta


def distance_to_similarity(distance: float, *, space: str | None = None) -> float:
    """
    Map Chroma query distance to a 0..1-ish score (higher = closer).

    With normalize_embeddings=True (sentence-transformers), prefer hnsw:space=cosine.
    """
    space = (space or CHROMA_HNSW_SPACE).lower().strip()
    d = max(0.0, float(distance))

    if space == "cosine":
        # Chroma cosine distance for unit vectors: ~ 1 - cos_sim
        return max(0.0, min(1.0, 1.0 - d))
    if space in ("ip", "inner_product", "dot"):
        # Inner product space: larger is closer; Chroma may return negative ip as distance
        return max(0.0, min(1.0, 1.0 / (1.0 + math.exp(-d)) if d != 0 else 1.0))
    if space == "l2":
        # Unit vectors: L2^2 = 2(1 - cos_sim)  =>  sim ≈ 1 - d^2/2 for small d
        return max(0.0, min(1.0, 1.0 - (d * d) / 2.0))
    return max(0.0, min(1.0, 1.0 - d))
