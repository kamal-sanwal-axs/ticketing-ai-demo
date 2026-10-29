"""Download local models used by the demo (sentence-transformers for RAG + intent routing)."""

from __future__ import annotations

import argparse


def download_rerank_model() -> None:
    from apex_rag_demo.config import RAG_RERANK_MODEL

    print(f"Rerank model: {RAG_RERANK_MODEL}")
    from sentence_transformers import CrossEncoder

    CrossEncoder(RAG_RERANK_MODEL)
    print("Cross-encoder reranker weights ready.")


def download_embedding_model() -> None:
    from apex_rag_demo.config import LOCAL_MODELS_ROOT, MODELS_EMBEDDINGS_DIR, SENTENCE_TRANSFORMERS_MODEL
    from apex_rag_demo.rag.embeddings import ensure_sentence_transformer_downloaded

    print(f"LOCAL_MODELS_ROOT: {LOCAL_MODELS_ROOT}")
    print(f"Cache: {MODELS_EMBEDDINGS_DIR}")
    print(f"Model: {SENTENCE_TRANSFORMERS_MODEL}")
    ensure_sentence_transformer_downloaded()
    print("sentence-transformers weights ready.")


def warm_intent_router() -> None:
    from apex_rag_demo.intent_semantic import warm_intent_semantic_index

    warm_intent_semantic_index()
    print("Intent semantic index ready.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Download APEX demo local ML models")
    parser.add_argument(
        "--rerank-only",
        action="store_true",
        help="Only download the cross-encoder rerank model",
    )
    parser.add_argument(
        "--intent-only",
        action="store_true",
        help="Only warm the intent-router embedding index (model must exist)",
    )
    args = parser.parse_args()
    if args.rerank_only:
        download_rerank_model()
        return
    if args.intent_only:
        warm_intent_router()
        return
    download_embedding_model()
    download_rerank_model()
    warm_intent_router()


if __name__ == "__main__":
    main()
