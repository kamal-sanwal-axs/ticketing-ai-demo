"""Rebuild the KB vector index in ChromaDB (and refresh local cache if used)."""

from __future__ import annotations

import argparse

from apex_rag_demo.config import RAG_VECTOR_STORE
from apex_rag_demo.rag.chroma_store import ensure_collection_synced, get_client
from apex_rag_demo.rag.index import build_or_load_index


def main() -> None:
    parser = argparse.ArgumentParser(description="Sync kb.json into the vector store")
    parser.add_argument(
        "--store",
        choices=("chroma", "numpy", "auto"),
        default="auto",
        help="Vector store to refresh (default: RAG_VECTOR_STORE from .env)",
    )
    args = parser.parse_args()
    store = RAG_VECTOR_STORE if args.store == "auto" else args.store

    if store == "chroma":
        client = get_client()
        collection = ensure_collection_synced(client)
        print(f"Chroma collection '{collection.name}' synced ({collection.count()} chunks).")
        return

    chunks, matrix = build_or_load_index()
    print(f"NumPy cache rebuilt ({len(chunks)} chunks, dim={matrix.shape[1]}).")


if __name__ == "__main__":
    main()
