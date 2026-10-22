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
    from sentence_transformers import SentenceTransformer

    MODELS_EMBEDDINGS_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Model: {SENTENCE_TRANSFORMERS_MODEL}")
    print(f"Cache: {MODELS_EMBEDDINGS_DIR}")
    SentenceTransformer(
        SENTENCE_TRANSFORMERS_MODEL,
        cache_folder=str(MODELS_EMBEDDINGS_DIR),
    )
    print("Download complete.")


if __name__ == "__main__":
    main()
