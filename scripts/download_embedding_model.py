#!/usr/bin/env python3
"""Download the sentence-transformers model into models/embeddings/."""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from dotenv import load_dotenv

load_dotenv(_ROOT / ".env")

from apex_rag_demo.config import MODELS_EMBEDDINGS_DIR, SENTENCE_TRANSFORMERS_MODEL


def main() -> None:
    from apex_rag_demo.download_models import (
        download_embedding_model,
        download_rerank_model,
        warm_intent_router,
    )

    download_embedding_model()
    download_rerank_model()
    warm_intent_router()


if __name__ == "__main__":
    main()
