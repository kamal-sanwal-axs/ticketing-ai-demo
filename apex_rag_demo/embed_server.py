"""OpenAI-compatible embedding API on port 8081 (sentence-transformers)."""

from __future__ import annotations

from functools import lru_cache
from typing import Union

from fastapi import FastAPI
from pydantic import BaseModel

from apex_rag_demo.api_call_log import log_api_call
from apex_rag_demo.config import EMBED_SERVER_PORT, SENTENCE_TRANSFORMERS_MODEL
from apex_rag_demo.rag.embeddings import embed_texts_inprocess

app = FastAPI(title="APEX demo embedding server", version="1.0")


class EmbeddingRequest(BaseModel):
    model: str = ""
    input: Union[str, list[str]]


class EmbeddingData(BaseModel):
    object: str = "embedding"
    index: int
    embedding: list[float]


class EmbeddingResponse(BaseModel):
    object: str = "list"
    data: list[EmbeddingData]
    model: str


@lru_cache(maxsize=1)
def _warm_model() -> None:
    embed_texts_inprocess(["warmup"], log_call=False)


@app.on_event("startup")
def startup() -> None:
    _warm_model()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "model": SENTENCE_TRANSFORMERS_MODEL}


@app.post("/v1/embeddings", response_model=EmbeddingResponse)
def create_embeddings(body: EmbeddingRequest) -> EmbeddingResponse:
    texts = body.input if isinstance(body.input, list) else [body.input]
    vectors = embed_texts_inprocess(texts, log_call=False)
    model_name = body.model or SENTENCE_TRANSFORMERS_MODEL
    result = EmbeddingResponse(
        data=[
            EmbeddingData(index=i, embedding=vec) for i, vec in enumerate(vectors)
        ],
        model=model_name,
    )
    log_api_call(
        call_type="EMBEDDING",
        method="POST",
        url=f"http://localhost:{EMBED_SERVER_PORT}/v1/embeddings",
        request_body=body.model_dump(),
        response_body=result.model_dump(),
    )
    return result
