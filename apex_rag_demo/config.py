from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(_ROOT / ".env")

DATA_DIR = _ROOT / "data"
KB_PATH = DATA_DIR / "kb.json"
CACHE_DIR = _ROOT / ".cache"
INDEX_PATH = CACHE_DIR / "kb_vectors.npz"
MODELS_EMBEDDINGS_DIR = _ROOT / "models" / "embeddings"

CHAT_BASE_URL = os.getenv("CHAT_BASE_URL", "http://localhost:8000/v1")
CHAT_MODEL = os.getenv("CHAT_MODEL", "")

# RAG embeddings: http (default, server on :8081) or sentence-transformers (in-process)
EMBEDDING_BACKEND = os.getenv("RAG_EMBEDDING_BACKEND", "http").lower()
SENTENCE_TRANSFORMERS_MODEL = os.getenv(
    "SENTENCE_TRANSFORMERS_MODEL",
    "sentence-transformers/all-MiniLM-L6-v2",
)

EMBED_BASE_URL = os.getenv("EMBED_BASE_URL", "http://localhost:8081/v1")
EMBED_SERVER_PORT = int(os.getenv("EMBED_SERVER_PORT", "8081"))
EMBED_MODEL = os.getenv(
    "EMBED_MODEL",
    SENTENCE_TRANSFORMERS_MODEL,
)

# Vector store: chroma (Docker) or numpy file cache (.cache/kb_vectors.npz)
RAG_VECTOR_STORE = os.getenv("RAG_VECTOR_STORE", "chroma").lower()
CHROMA_HOST = os.getenv("CHROMA_HOST", "localhost")
CHROMA_PORT = int(os.getenv("CHROMA_PORT", "8002"))
CHROMA_COLLECTION = os.getenv("CHROMA_COLLECTION", "apex_kb")

RAG_KEYWORD_FALLBACK = os.getenv("RAG_KEYWORD_FALLBACK", "true").lower() in (
    "1",
    "true",
    "yes",
)

# Dev gateway (see axs-b2b-control .env.dev). Override with localhost when running APIs locally.
APEX_SEARCH_BASE_URL = os.getenv(
    "APEX_SEARCH_BASE_URL",
    "https://api.apex-dev.axsdevops.io/search",
).rstrip("/")
APEX_ADMIN_BASE_URL = os.getenv(
    "APEX_ADMIN_BASE_URL",
    "https://api.apex-dev.axsdevops.io/admin",
).rstrip("/")
APEX_ADMIN_SWAGGER_URL = os.getenv(
    "APEX_ADMIN_SWAGGER_URL",
    "https://api.apex-dev.axsdevops.io/admin/swagger/v1/swagger.json",
)
APEX_SEARCH_SWAGGER_URL = os.getenv(
    "APEX_SEARCH_SWAGGER_URL",
    "https://api.apex-dev.axsdevops.io/search/swagger/v1/swagger.json",
)
APEX_EVENTS_BASE_URL = os.getenv(
    "APEX_EVENTS_BASE_URL",
    "https://api.apex-dev.axsdevops.io/events",
).rstrip("/")
APEX_EVENTS_SWAGGER_URL = os.getenv(
    "APEX_EVENTS_SWAGGER_URL",
    "https://api.apex-dev.axsdevops.io/events/swagger/v1/swagger.json",
)
APEX_INVENTORY_BASE_URL = os.getenv(
    "APEX_INVENTORY_BASE_URL",
    "https://api.apex-dev.axsdevops.io/inventory",
).rstrip("/")
APEX_INVENTORY_SWAGGER_URL = os.getenv(
    "APEX_INVENTORY_SWAGGER_URL",
    "https://api.apex-dev.axsdevops.io/inventory/swagger/v1/swagger.json",
)
APEX_MARKETING_BASE_URL = os.getenv(
    "APEX_MARKETING_BASE_URL",
    "https://api.apex-dev.axsdevops.io/marketing",
).rstrip("/")
APEX_MARKETING_SWAGGER_URL = os.getenv(
    "APEX_MARKETING_SWAGGER_URL",
    "https://api.apex-dev.axsdevops.io/marketing/swagger/v1/swagger.json",
)
APEX_BEARER_TOKEN = os.getenv("APEX_BEARER_TOKEN", "")
APEX_MOCK = os.getenv("APEX_MOCK", "false").lower() in ("1", "true", "yes")

# Required for create client venue when not parsed from the user message
DEMO_CLIENT_ID = os.getenv("DEMO_CLIENT_ID", "")

# Live POST to admin APIs (organization / client-venue create). Default: dry-run preview only.
DEMO_EXECUTE_WRITES = os.getenv("DEMO_EXECUTE_WRITES", "false").lower() in (
    "1",
    "true",
    "yes",
)

TOP_K = int(os.getenv("RAG_TOP_K", "2"))
