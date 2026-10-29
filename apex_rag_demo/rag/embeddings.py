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


def ensure_sentence_transformer_downloaded() -> str:
    """Load (and download if needed) the Hugging Face sentence-transformers weights."""
    _sentence_transformer()
    return SENTENCE_TRANSFORMERS_MODEL


def similarity_to_references(query: str, references: list[str]) -> list[float]:
    """Cosine similarities query→each reference (sentence-transformers ``model.similarity``)."""
    if not references:
        return []
    model = _sentence_transformer()
    sentences = [query] + references
    embeddings = model.encode(sentences, normalize_embeddings=True, convert_to_tensor=True)
    matrix = model.similarity(embeddings[0:1], embeddings[1:])
    return matrix[0].cpu().tolist()


_HTTP_BACKENDS = frozenset({"http", "llama", "openai"})


def embed_texts_inprocess(texts: list[str], *, log_call: bool = True) -> list[list[float]]:
    if not texts:
        return []
    model = _sentence_transformer()
    vectors = model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
    rows = vectors.tolist()
    if log_call:
        from apex_rag_demo.api_call_log import log_api_call

        request_body = {"model": SENTENCE_TRANSFORMERS_MODEL, "input": texts}
        response_body = {
            "object": "list",
            "data": [
                {"object": "embedding", "index": i, "embedding": row}
                for i, row in enumerate(rows)
            ],
        }
        log_api_call(
            call_type="EMBEDDING",
            method="IN_PROCESS",
            url=f"sentence-transformers://{SENTENCE_TRANSFORMERS_MODEL}",
            request_body=request_body,
            response_body=response_body,
        )
    return rows


def embed_texts(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    if EMBEDDING_BACKEND in _HTTP_BACKENDS:
        from apex_rag_demo.clients.llama import embed_texts as http_embed

        return http_embed(texts)
    return embed_texts_inprocess(texts)
