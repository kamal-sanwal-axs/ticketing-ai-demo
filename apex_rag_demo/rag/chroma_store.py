from __future__ import annotations

import hashlib
import json

from apex_rag_demo.config import (
    CHROMA_COLLECTION,
    EMBEDDING_EXPECTED_DIMENSION,
    KB_PATH,
)
from apex_rag_demo.rag.chroma_client import (
    create_collection,
    delete_collection,
    get_collection,
    get_http_client,
)
from apex_rag_demo.rag.chroma_metrics import chroma_collection_metadata
from apex_rag_demo.rag.embeddings import embed_texts
from apex_rag_demo.rag.kb import KbChunk, load_kb

_KB_HASH_META = "kb_sha256"


def _kb_fingerprint(chunks: list[KbChunk]) -> str:
    payload = json.dumps(
        [{"id": c.id, "text": c.text} for c in chunks],
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def get_client():
    return get_http_client()


def ensure_collection_synced(client=None):
    client = client or get_client()
    chunks = load_kb()
    fingerprint = _kb_fingerprint(chunks)

    try:
        collection = get_collection(client, CHROMA_COLLECTION)
    except Exception:
        collection = None

    stored = (collection.metadata or {}).get(_KB_HASH_META) if collection else None
    if (
        collection is not None
        and stored == fingerprint
        and collection.count() == len(chunks)
    ):
        return collection

    try:
        delete_collection(client, CHROMA_COLLECTION)
    except Exception:
        pass

    collection = create_collection(
        client,
        CHROMA_COLLECTION,
        metadata=chroma_collection_metadata(
            {
                "description": f"KB from {KB_PATH.name}",
                _KB_HASH_META: fingerprint,
            },
        ),
    )
    vectors = embed_texts([c.text for c in chunks])
    if vectors and EMBEDDING_EXPECTED_DIMENSION > 0:
        dim = len(vectors[0])
        if dim != EMBEDDING_EXPECTED_DIMENSION:
            print(
                f"--- WARNING: embedding dim {dim} != EMBEDDING_EXPECTED_DIMENSION "
                f"{EMBEDDING_EXPECTED_DIMENSION}. Re-sync Chroma after changing "
                f"SENTENCE_TRANSFORMERS_MODEL; chat GGUF (Qwen 3B) is unrelated. ---",
                flush=True,
            )
    collection.add(
        ids=[c.id for c in chunks],
        documents=[c.text for c in chunks],
        embeddings=vectors,
    )
    return collection


def query_chroma(question: str, top_k: int) -> list[str]:
    client = get_client()
    collection = ensure_collection_synced(client)
    query_vectors = embed_texts([question])
    result = collection.query(
        query_embeddings=query_vectors,
        n_results=min(top_k, max(collection.count(), 1)),
        include=["documents"],
    )
    documents = result.get("documents") or []
    if not documents or not documents[0]:
        return []
    return list(documents[0])
