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
# HuggingFace / sentence-transformers cache (default: repo parent, e.g. /Users/kamals/models/embeddings)
LOCAL_MODELS_ROOT = Path(os.getenv("LOCAL_MODELS_ROOT", str(_ROOT.parent)))
MODELS_EMBEDDINGS_DIR = LOCAL_MODELS_ROOT / "embeddings"
INTENT_SEMANTIC_ENABLED = os.getenv("INTENT_SEMANTIC_ENABLED", "true").lower() in (
    "1",
    "true",
    "yes",
)
INTENT_SEMANTIC_MIN_SCORE = float(os.getenv("INTENT_SEMANTIC_MIN_SCORE", "0.42"))
INTENT_SEMANTIC_MARGIN = float(os.getenv("INTENT_SEMANTIC_MARGIN", "0.06"))
# Current message vs recent chat: below → new topic (drop history + Chroma role hints).
TOPIC_SHIFT_MAX_SIMILARITY = float(os.getenv("TOPIC_SHIFT_MAX_SIMILARITY", "0.52"))
# Keep a prior turn only if it is at least this similar to the current message.
TOPIC_HISTORY_MIN_SIMILARITY = float(os.getenv("TOPIC_HISTORY_MIN_SIMILARITY", "0.40"))
CONVERSATIONAL_MIN_SCORE = float(os.getenv("CONVERSATIONAL_MIN_SCORE", "0.38"))
CONVERSATIONAL_VS_OPS_MARGIN = float(os.getenv("CONVERSATIONAL_VS_OPS_MARGIN", "0.04"))

CHAT_BASE_URL = os.getenv("CHAT_BASE_URL", "http://localhost:8000/v1")
CHAT_MODEL = os.getenv("CHAT_MODEL", "")
CHAT_TEMPERATURE = float(os.getenv("CHAT_TEMPERATURE", "0.2"))
# Classify / plan / JSON extraction (defaults to CHAT_TEMPERATURE if unset)
CHAT_TEMPERATURE_ROUTING = float(
    os.getenv("CHAT_TEMPERATURE_ROUTING", os.getenv("CHAT_TEMPERATURE", "0.2")),
)
CHAT_HISTORY_MAX_MESSAGES = int(os.getenv("CHAT_HISTORY_MAX_MESSAGES", "10"))
# llama.cpp n_ctx budgeting (~chars/4). Default targets 2048 ctx with room for completion.
CHAT_CONTEXT_MAX_TOKENS = int(os.getenv("CHAT_CONTEXT_MAX_TOKENS", "1700"))
CHAT_CONTEXT_MAX_TOKENS_ROUTING = int(
    os.getenv("CHAT_CONTEXT_MAX_TOKENS_ROUTING", os.getenv("CHAT_CONTEXT_MAX_TOKENS", "1500")),
)
CHAT_MESSAGE_MAX_CHARS = int(os.getenv("CHAT_MESSAGE_MAX_CHARS", "1200"))
CHAT_MESSAGE_MAX_CHARS_ROUTING = int(
    os.getenv("CHAT_MESSAGE_MAX_CHARS_ROUTING", "450"),
)
CHAT_CHROMA_MAX_CHARS = int(os.getenv("CHAT_CHROMA_MAX_CHARS", "1400"))
CHAT_CHROMA_MAX_CHARS_ROUTING = int(os.getenv("CHAT_CHROMA_MAX_CHARS_ROUTING", "500"))
CHAT_HISTORY_MAX_MESSAGES_ROUTING = int(os.getenv("CHAT_HISTORY_MAX_MESSAGES_ROUTING", "6"))
CHAT_SUMMARY_LLM_ENABLED = os.getenv("CHAT_SUMMARY_LLM_ENABLED", "true").lower() in (
    "1",
    "true",
    "yes",
)
CHAT_SUMMARY_MAX_MESSAGES = int(os.getenv("CHAT_SUMMARY_MAX_MESSAGES", "8"))
CHAT_RAW_LOG_MAX_MESSAGES = int(os.getenv("CHAT_RAW_LOG_MAX_MESSAGES", "40"))
ORCHESTRATOR_MAX_ROUNDS = int(os.getenv("ORCHESTRATOR_MAX_ROUNDS", "3"))
CHAT_TOP_P = float(os.getenv("CHAT_TOP_P", "0.9"))
CHAT_TOP_K = int(os.getenv("CHAT_TOP_K", "40"))
CHAT_STREAM = os.getenv("CHAT_STREAM", "true").lower() in ("1", "true", "yes")
_logprobs_raw = os.getenv("CHAT_LOGPROBS", "5").strip().lower()
if _logprobs_raw in ("", "0", "false", "no", "off"):
    CHAT_LOGPROBS: int | None = None
elif _logprobs_raw in ("true", "yes", "on"):
    CHAT_LOGPROBS = 5
elif _logprobs_raw.isdigit():
    CHAT_LOGPROBS = int(_logprobs_raw)
else:
    CHAT_LOGPROBS = None

# RAG embeddings: http (default, server on :8081) or sentence-transformers (in-process)
EMBEDDING_BACKEND = os.getenv("RAG_EMBEDDING_BACKEND", "http").lower()
SENTENCE_TRANSFORMERS_MODEL = os.getenv(
    "SENTENCE_TRANSFORMERS_MODEL",
    "BAAI/bge-small-en-v1.5",
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
CHROMA_SESSION_COLLECTION = os.getenv("CHROMA_SESSION_COLLECTION", "apex_session_intents")
CHROMA_STATE_COLLECTION = os.getenv("CHROMA_STATE_COLLECTION", "apex_graph_state")
CHROMA_AGENT_ROLES_COLLECTION = os.getenv("CHROMA_AGENT_ROLES_COLLECTION", "apex_agent_roles")
CHROMA_INTENT_ROUTES_COLLECTION = os.getenv(
    "CHROMA_INTENT_ROUTES_COLLECTION",
    "apex_intent_routes",
)
CHROMA_INTENT_ROUTE_TOP_K = int(os.getenv("CHROMA_INTENT_ROUTE_TOP_K", "3"))
CHROMA_INTENT_ROUTE_MIN_SCORE = float(os.getenv("CHROMA_INTENT_ROUTE_MIN_SCORE", "0.72"))
CHROMA_SYSTEM_ENRICH_TOP_K = int(os.getenv("CHROMA_SYSTEM_ENRICH_TOP_K", "3"))
# Chroma HNSW: cosine (default, use with L2-normalized ST vectors), l2, or ip
CHROMA_HNSW_SPACE = os.getenv("CHROMA_HNSW_SPACE", "cosine").lower().strip()
# Optional: warn on sync if embed dim != this (384 = bge-small-en-v1.5 / MiniLM). Not related to chat GGUF size.
EMBEDDING_EXPECTED_DIMENSION = int(os.getenv("EMBEDDING_EXPECTED_DIMENSION", "384"))

SESSION_MEMORY_ENABLED = os.getenv("SESSION_MEMORY_ENABLED", "true").lower() in (
    "1",
    "true",
    "yes",
)
SESSION_MEMORY_TOP_K = int(os.getenv("SESSION_MEMORY_TOP_K", "3"))
# Chroma L2 distance — lower is closer; tune per embedding model.
SESSION_MEMORY_REUSE_MAX_DISTANCE = float(
    os.getenv("SESSION_MEMORY_REUSE_MAX_DISTANCE", "0.55"),
)

# Knowledge graph (Neo4j) — hybrid memory alongside Chroma vectors
KG_NEO4J_ENABLED = os.getenv("KG_NEO4J_ENABLED", "false").lower() in ("1", "true", "yes")
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "changeme")
_raw_ontology = os.getenv("KG_ONTOLOGY_PATH", "data/kg/ontology/ticketing_apex.json")
_ontology_path = Path(_raw_ontology)
KG_ONTOLOGY_PATH = _ontology_path if _ontology_path.is_absolute() else _ROOT / _ontology_path
KG_GLINER_MODEL = os.getenv("KG_GLINER_MODEL", "urchade/gliner_medium-v2.1")
KG_GLINER_THRESHOLD = float(os.getenv("KG_GLINER_THRESHOLD", "0.45"))
KG_GLINER_ENABLED = os.getenv("KG_GLINER_ENABLED", "true").lower() in ("1", "true", "yes")
KG_ENRICH_MAX_HITS = int(os.getenv("KG_ENRICH_MAX_HITS", "8"))

# LangGraph persistence (checkpointer + store for plugins / thread state)
LANGGRAPH_RUNTIME_ENABLED = os.getenv("LANGGRAPH_RUNTIME_ENABLED", "true").lower() in (
    "1",
    "true",
    "yes",
)
LANGGRAPH_CHECKPOINT_PATH = os.getenv(
    "LANGGRAPH_CHECKPOINT_PATH",
    "data/langgraph/checkpoints.sqlite",
)
LANGGRAPH_STORE_PATH = os.getenv(
    "LANGGRAPH_STORE_PATH",
    "data/langgraph/store.sqlite",
)

# Declarative custom plugins (HTTP allowlist + optional sandboxed scripts)
_PLUGIN_HOSTS_RAW = os.getenv(
    "PLUGIN_ALLOWED_HOST_SUFFIXES",
    "api.apex-dev.axsdevops.io,localhost,127.0.0.1",
)
PLUGIN_ALLOWED_HOST_SUFFIXES = tuple(
    h.strip() for h in _PLUGIN_HOSTS_RAW.split(",") if h.strip()
)
PLUGIN_HTTP_TIMEOUT_SEC = float(os.getenv("PLUGIN_HTTP_TIMEOUT_SEC", "30"))
PLUGIN_SCRIPT_ENABLED = os.getenv("PLUGIN_SCRIPT_ENABLED", "true").lower() in ("1", "true", "yes")
PLUGIN_SCRIPT_MAX_BYTES = int(os.getenv("PLUGIN_SCRIPT_MAX_BYTES", "16384"))
PLUGIN_SCRIPT_TIMEOUT_SEC = float(os.getenv("PLUGIN_SCRIPT_TIMEOUT_SEC", "5"))
# auto (prefer Docker worker image) | docker | subprocess | inprocess (dev only)
PLUGIN_SANDBOX_BACKEND = os.getenv("PLUGIN_SANDBOX_BACKEND", "auto").strip().lower()
PLUGIN_DOCKER_IMAGE = os.getenv(
    "PLUGIN_DOCKER_IMAGE",
    "ticketing-ai-demo-plugin-worker:local",
).strip()
PLUGIN_TENANT_STRICT = os.getenv("PLUGIN_TENANT_STRICT", "true").lower() in ("1", "true", "yes")

# Docker sandbox toolkit (on-the-fly Python / React in disposable containers)
SANDBOX_TOOLKIT_ENABLED = os.getenv("SANDBOX_TOOLKIT_ENABLED", "true").lower() in (
    "1",
    "true",
    "yes",
)
SANDBOX_TOOLKIT_IMAGE = os.getenv(
    "SANDBOX_TOOLKIT_IMAGE",
    "ticketing-ai-demo-sandbox-toolkit:local",
).strip()
SANDBOX_TOOLKIT_TIMEOUT_SEC = int(os.getenv("SANDBOX_TOOLKIT_TIMEOUT_SEC", "120"))
_SANDBOX_PIP = os.getenv(
    "SANDBOX_PIP_ALLOWLIST",
    "pandas,numpy,matplotlib,httpx,pillow",
)
SANDBOX_PIP_ALLOWLIST = frozenset(p.strip().lower() for p in _SANDBOX_PIP.split(",") if p.strip())
_SANDBOX_NPM = os.getenv(
    "SANDBOX_NPM_ALLOWLIST",
    "react,react-dom,recharts",
)
SANDBOX_NPM_ALLOWLIST = frozenset(p.strip().lower() for p in _SANDBOX_NPM.split(",") if p.strip())
SANDBOX_MAX_SOURCE_BYTES = int(os.getenv("SANDBOX_MAX_SOURCE_BYTES", "65536"))

DYNAMIC_TOOLS_ENABLED = os.getenv("DYNAMIC_TOOLS_ENABLED", "true").lower() in ("1", "true", "yes")

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
APEX_RESOURCES_BASE_URL = os.getenv(
    "APEX_RESOURCES_BASE_URL",
    "https://api.apex-dev.axsdevops.io/resources",
).rstrip("/")
APEX_RESOURCES_SWAGGER_URL = os.getenv(
    "APEX_RESOURCES_SWAGGER_URL",
    "https://api.apex-dev.axsdevops.io/resources/swagger/v1/swagger.json",
)
# B2B admin user list query params (axs-b2b-admin defaults)
RESOURCES_CLIENT_ID = int(os.getenv("RESOURCES_CLIENT_ID", "11"))
RESOURCES_AXS_CLIENT_ID = int(os.getenv("RESOURCES_AXS_CLIENT_ID", "4"))
RESOURCES_USERS_PAGE_SIZE = int(os.getenv("RESOURCES_USERS_PAGE_SIZE", "50"))
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
APEX_MANIFEST_BASE_URL = os.getenv(
    "APEX_MANIFEST_BASE_URL",
    "https://api.apex-dev.axsdevops.io/manifest",
).rstrip("/")
APEX_MANIFEST_SWAGGER_URL = os.getenv(
    "APEX_MANIFEST_SWAGGER_URL",
    "https://api.apex-dev.axsdevops.io/manifest/swagger/v1/swagger.json",
)
APEX_REPORTS_BASE_URL = os.getenv(
    "APEX_REPORTS_BASE_URL",
    "https://api.apex-dev.axsdevops.io/reports",
).rstrip("/")
APEX_REPORTS_SWAGGER_URL = os.getenv(
    "APEX_REPORTS_SWAGGER_URL",
    "https://api.apex-dev.axsdevops.io/reports/swagger/v1/swagger.json",
)
# Numeric AXS context id for unified-api-reports when not parsed from the chat message.
REPORTS_DEFAULT_CONTEXT_ID = os.getenv("REPORTS_DEFAULT_CONTEXT_ID", "")
REPORTS_DEFAULT_REGION_ID = os.getenv("REPORTS_DEFAULT_REGION_ID", "1")
APEX_BEARER_TOKEN = os.getenv("APEX_BEARER_TOKEN", "")
APEX_MOCK = os.getenv("APEX_MOCK", "false").lower() in ("1", "true", "yes")

# Required for create client venue when not parsed from the user message
DEMO_CLIENT_ID = os.getenv("DEMO_CLIENT_ID", "")

# When true, all mutations stay dry-run (reads still call APIs). Otherwise writes follow CRUD policy.
_mdr_env = os.getenv("DEMO_MUTATIONS_DRY_RUN", "").strip().lower()
if _mdr_env in ("1", "true", "yes"):
    DEMO_MUTATIONS_DRY_RUN = True
elif _mdr_env in ("0", "false", "no"):
    DEMO_MUTATIONS_DRY_RUN = False
else:
    DEMO_MUTATIONS_DRY_RUN = False
    _legacy_execute = os.getenv("DEMO_EXECUTE_WRITES", "").strip().lower()
    if _legacy_execute in ("0", "false", "no"):
        DEMO_MUTATIONS_DRY_RUN = True
    elif _legacy_execute in ("1", "true", "yes"):
        DEMO_MUTATIONS_DRY_RUN = False

TOP_K = int(os.getenv("RAG_TOP_K", "2"))
RAG_RETRIEVE_K = int(os.getenv("RAG_RETRIEVE_K", "10"))
RAG_RERANK_ENABLED = os.getenv("RAG_RERANK_ENABLED", "true").lower() in (
    "1",
    "true",
    "yes",
)
RAG_RERANK_MODEL = os.getenv(
    "RAG_RERANK_MODEL",
    "BAAI/bge-reranker-base",
)

MARKETING_LIST_PAGE_SIZE = int(os.getenv("MARKETING_LIST_PAGE_SIZE", "25"))
MARKETING_EVENT_ENRICH_MAX = int(os.getenv("MARKETING_EVENT_ENRICH_MAX", "24"))
# When Marketing GET /v1/events is forbidden, list via Search (min ~2 chars)
MARKETING_FALLBACK_SEARCH_QUERY = os.getenv("MARKETING_FALLBACK_SEARCH_QUERY", "event")
