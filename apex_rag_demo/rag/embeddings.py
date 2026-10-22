from __future__ import annotations

from functools import lru_cache

from apex_rag_demo.config import (
    EMBEDDING_BACKEND,
    MODELS_EMBEDDINGS_DIR,
    SENTENCE_TRANSFORMERS_MODEL,
)


@lru_cache(maxsize=1)
def _sentence_transformer():
    from sentence_transformers import SentenceTransformer

    MODELS_EMBEDDINGS_DIR.mkdir(parents=True, exist_ok=True)
    return SentenceTransformer(
        SENTENCE_TRANSFORMERS_MODEL,
        cache_folder=str(MODELS_EMBEDDINGS_DIR),
    )


_HTTP_BACKENDS = frozenset({"http", "llama", "openai"})


def embed_texts_inprocess(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    model = _sentence_transformer()
    vectors = model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
    return vectors.tolist()


def embed_texts(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    if EMBEDDING_BACKEND in _HTTP_BACKENDS:
        from apex_rag_demo.clients.llama import embed_texts as http_embed

        return http_embed(texts)
    return embed_texts_inprocess(texts)
