from __future__ import annotations

import hashlib
import json

import chromadb

from apex_rag_demo.config import (
    CHROMA_COLLECTION,
    CHROMA_HOST,
    CHROMA_PORT,
    KB_PATH,
)
from apex_rag_demo.rag.embeddings import embed_texts
from apex_rag_demo.rag.kb import KbChunk, load_kb

_KB_HASH_META = "kb_sha256"


def _kb_fingerprint(chunks: list[KbChunk]) -> str:
    payload = json.dumps(
        [{"id": c.id, "text": c.text} for c in chunks],
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def get_client() -> chromadb.HttpClient:
    return chromadb.HttpClient(host=CHROMA_HOST, port=CHROMA_PORT)


def ensure_collection_synced(client: chromadb.HttpClient | None = None) -> chromadb.Collection:
    client = client or get_client()
    chunks = load_kb()
    fingerprint = _kb_fingerprint(chunks)

    try:
        collection = client.get_collection(name=CHROMA_COLLECTION)
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
        client.delete_collection(CHROMA_COLLECTION)
    except Exception:
        pass

    collection = client.create_collection(
        name=CHROMA_COLLECTION,
        metadata={
            "description": f"KB from {KB_PATH.name}",
            _KB_HASH_META: fingerprint,
        },
    )
    vectors = embed_texts([c.text for c in chunks])
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
