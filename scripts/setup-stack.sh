#!/usr/bin/env bash
# Idempotent local stack setup: Python venv, .env, data dirs, SQLite paths,
# Docker (Chroma + Neo4j) when available, model download, Chroma sync.
#
# Usage:
#   ./scripts/setup-stack.sh              # full setup (checks only; does not start llama/web)
#   ./scripts/setup-stack.sh --help
#   ./scripts/setup-stack.sh --skip-docker
#   ./scripts/setup-stack.sh --skip-sync --skip-models
#
# Llama.cpp chat uses a separate venv (not project .venv). Set:
#   LLAMA_VENV=~/.venv-llama-cpp
#   LLAMA_MODEL_PATH=/path/to/model.gguf

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

SKIP_DOCKER=0
SKIP_MODELS=0
SKIP_SYNC=0
SKIP_KG_SYNC=0
SETUP_LLAMA_VENV=0
MIN_PYTHON=3.10

LLAMA_VENV="${LLAMA_VENV:-$HOME/.venv-llama-cpp}"

log() { printf '[setup] %s\n' "$*"; }
warn() { printf '[setup] WARN: %s\n' "$*" >&2; }
err() { printf '[setup] ERROR: %s\n' "$*" >&2; exit 1; }

usage() {
  sed -n '2,20p' "$0" | sed 's/^# \?//'
  exit 0
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --help|-h) usage ;;
    --skip-docker) SKIP_DOCKER=1; shift ;;
    --skip-models) SKIP_MODELS=1; shift ;;
    --skip-sync) SKIP_SYNC=1; shift ;;
    --skip-kg-sync) SKIP_KG_SYNC=1; shift ;;
    --setup-llama-venv) SETUP_LLAMA_VENV=1; shift ;;
    *) err "Unknown option: $1 (try --help)" ;;
  esac
done

python_version_ok() {
  local v major minor
  v="$("$1" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
  major="${v%%.*}"
  minor="${v#*.}"
  [[ "$major" -ge 3 && "$minor" -ge 10 ]] 2>/dev/null || [[ "$major" -gt 3 ]] 2>/dev/null
}

find_python() {
  for cmd in python3.12 python3.11 python3.10 python3; do
    if command -v "$cmd" >/dev/null 2>&1 && python_version_ok "$cmd"; then
      echo "$cmd"
      return 0
    fi
  done
  return 1
}

check_python() {
  log "Checking Python (>= ${MIN_PYTHON})…"
  PY="$(find_python)" || err "Need Python ${MIN_PYTHON}+. Install via python.org or Homebrew."
  log "Using $PY ($("$PY" --version))"
  export PY
}

setup_project_venv() {
  log "Project venv: $ROOT/.venv"
  if [[ ! -d "$ROOT/.venv" ]]; then
    "$PY" -m venv "$ROOT/.venv"
  fi
  # shellcheck disable=SC1091
  source "$ROOT/.venv/bin/activate"
  log "Upgrading pip…"
  pip install -q --upgrade pip
  log "Installing requirements.txt (may take several minutes)…"
  pip install -q -r "$ROOT/requirements.txt"
  deactivate
  log "Project venv ready."
}

setup_env_file() {
  if [[ ! -f "$ROOT/.env" ]]; then
    if [[ -f "$ROOT/.env.example" ]]; then
      cp "$ROOT/.env.example" "$ROOT/.env"
      log "Created .env from .env.example"
    else
      warn "No .env.example — create .env manually."
    fi
  else
    log ".env already exists (unchanged)"
  fi
}

env_get() {
  local key="$1" default="${2:-}"
  if [[ -f "$ROOT/.env" ]]; then
    local line
    line="$(grep -E "^${key}=" "$ROOT/.env" 2>/dev/null | tail -1 || true)"
    if [[ -n "$line" ]]; then
      echo "${line#*=}" | sed 's/^["'\''"]//;s/["'\''"]$//'
      return 0
    fi
  fi
  echo "$default"
}

setup_data_dirs() {
  log "Data directories (Chroma, Neo4j, LangGraph SQLite)…"
  mkdir -p \
    "$ROOT/data/chroma" \
    "$ROOT/data/neo4j/data" \
    "$ROOT/data/neo4j/logs" \
    "$ROOT/data/neo4j/import" \
    "$ROOT/data/langgraph" \
    "$ROOT/data/session_graph" \
    "$ROOT/models/embeddings" 2>/dev/null || true
  local cp sp
  cp="$(env_get LANGGRAPH_CHECKPOINT_PATH "data/langgraph/checkpoints.sqlite")"
  sp="$(env_get LANGGRAPH_STORE_PATH "data/langgraph/store.sqlite")"
  mkdir -p "$(dirname "$ROOT/$cp")" "$(dirname "$ROOT/$sp")"
  log "SQLite paths: $cp , $sp (created on first app run if missing)"
}

docker_available() {
  command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1
}

compose_cmd() {
  if docker compose version >/dev/null 2>&1; then
    echo "docker compose"
  elif command -v docker-compose >/dev/null 2>&1; then
    echo "docker-compose"
  else
    return 1
  fi
}

wait_http() {
  local url="$1" label="$2" max="${3:-60}"
  local i=0
  while [[ "$i" -lt "$max" ]]; do
    if curl -sf --max-time 2 "$url" >/dev/null 2>&1; then
      log "$label is up ($url)"
      return 0
    fi
    sleep 2
    i=$((i + 2))
  done
  warn "$label not ready after ${max}s ($url)"
  return 1
}

setup_docker_services() {
  if [[ "$SKIP_DOCKER" -eq 1 ]]; then
    warn "Skipping Docker (--skip-docker)"
    return 0
  fi
  if ! docker_available; then
    warn "Docker not installed or daemon not running."
    warn "  Install: https://docs.docker.com/get-docker/"
    warn "  Chroma (:8002) and Neo4j (:7474/:7687) will not start."
    warn "  You can use RAG_VECTOR_STORE=numpy in .env for offline vectors (limited)."
    return 0
  fi
  local compose
  compose="$(compose_cmd)" || err "docker compose not found (install Docker Desktop or compose plugin)"
  log "Starting Chroma + Neo4j via $compose…"
  (cd "$ROOT" && $compose up -d chroma neo4j)
  wait_http "http://localhost:${CHROMA_PORT:-8002}/api/v1/heartbeat" "Chroma" 90 || true
  wait_http "http://localhost:${NEO4J_HTTP_PORT:-7474}" "Neo4j Browser" 120 || true
}

download_models() {
  if [[ "$SKIP_MODELS" -eq 1 ]]; then
    warn "Skipping model download (--skip-models)"
    return 0
  fi
  # shellcheck disable=SC1091
  source "$ROOT/.venv/bin/activate"
  log "Downloading embedding + rerank models…"
  "$ROOT/.venv/bin/python" "$ROOT/scripts/download_embedding_model.py"
  deactivate
}

sync_chroma_index() {
  if [[ "$SKIP_SYNC" -eq 1 ]]; then
    warn "Skipping Chroma sync (--skip-sync)"
    return 0
  fi
  local backend
  backend="$(env_get RAG_EMBEDDING_BACKEND "http")"
  if [[ "$backend" == "http" || "$backend" == "llama" ]]; then
    if ! curl -sf --max-time 2 "http://localhost:${EMBED_SERVER_PORT:-8081}/health" >/dev/null 2>&1; then
      warn "Embed server not on :${EMBED_SERVER_PORT:-8081} (RAG_EMBEDDING_BACKEND=$backend)."
      warn "  Start: ./scripts/run-embed-server.sh"
      warn "  Or set RAG_EMBEDDING_BACKEND=sentence-transformers in .env and re-run sync."
    fi
  fi
  if ! curl -sf --max-time 2 "http://localhost:${CHROMA_PORT:-8002}/api/v1/heartbeat" >/dev/null 2>&1; then
    warn "Chroma not reachable on :${CHROMA_PORT:-8002} — skip sync_index (start Docker first)."
    return 0
  fi
  # shellcheck disable=SC1091
  source "$ROOT/.venv/bin/activate"
  log "Syncing KB into Chroma…"
  "$ROOT/.venv/bin/python" -m apex_rag_demo.rag.sync_index
  deactivate
}

sync_kg_if_enabled() {
  if [[ "$SKIP_KG_SYNC" -eq 1 ]]; then
    return 0
  fi
  local kg
  kg="$(env_get KG_NEO4J_ENABLED "false")"
  case "$(echo "$kg" | tr '[:upper:]' '[:lower:]')" in
    1|true|yes) ;;
    *) log "KG_NEO4J_ENABLED=$kg — skipping sync_kg_index"; return 0 ;;
  esac
  if ! curl -sf --max-time 2 "http://localhost:${NEO4J_HTTP_PORT:-7474}" >/dev/null 2>&1; then
    warn "Neo4j not up — skip sync_kg_index"
    return 0
  fi
  # shellcheck disable=SC1091
  source "$ROOT/.venv/bin/activate"
  log "Syncing KB into Neo4j (GLiNER)…"
  "$ROOT/.venv/bin/python" -m apex_rag_demo.rag.sync_kg_index || warn "sync_kg_index failed (check NEO4J_PASSWORD / .env)"
  deactivate
}

check_llama_venv() {
  log "Llama.cpp chat (separate venv: $LLAMA_VENV)"
  if [[ "$SETUP_LLAMA_VENV" -eq 1 ]]; then
    if [[ ! -d "$LLAMA_VENV" ]]; then
      log "Creating llama venv…"
      "$PY" -m venv "$LLAMA_VENV"
    fi
    # shellcheck disable=SC1091
    source "$LLAMA_VENV/bin/activate"
    pip install -q --upgrade pip
    log "Installing llama-cpp-python (CPU wheels; can be slow)…"
    pip install -q 'llama-cpp-python>=0.2.0' || warn "llama-cpp-python install failed — install manually in $LLAMA_VENV"
    deactivate
  fi
  if [[ -x "$LLAMA_VENV/bin/python" ]] && "$LLAMA_VENV/bin/python" -c "import llama_cpp" 2>/dev/null; then
    log "llama-cpp-python OK in $LLAMA_VENV"
  else
    warn "llama-cpp-python not found in $LLAMA_VENV"
    warn "  Create: python3 -m venv $LLAMA_VENV && source $LLAMA_VENV/bin/activate && pip install llama-cpp-python"
    warn "  Or re-run: ./scripts/setup-stack.sh --setup-llama-venv"
  fi
  local model chat_model
  chat_model="$(env_get CHAT_MODEL "")"
  model="${LLAMA_MODEL_PATH:-}"
  if [[ -z "$model" && -n "$chat_model" ]]; then
    for candidate in \
      "$HOME/models/$chat_model" \
      "$HOME/models/Qwen2.5-3B-Instruct-GGUF/$chat_model" \
      "$ROOT/../$chat_model"; do
      if [[ -f "$candidate" ]]; then
        model="$candidate"
        break
      fi
    done
  fi
  if [[ -n "$model" && -f "$model" ]]; then
    log "Chat GGUF found: $model"
  else
    warn "Chat GGUF not found (CHAT_MODEL=$chat_model). See docs/CHAT_MODEL.md"
  fi
  if curl -sf --max-time 2 "http://localhost:8000/v1/models" >/dev/null 2>&1; then
    log "llama.cpp server already listening on :8000"
  else
    warn "llama.cpp not running on :8000. Start manually, e.g.:"
    warn "  source $LLAMA_VENV/bin/activate"
    warn "  python3 -m llama_cpp.server --model \$LLAMA_MODEL_PATH --port 8000 --n_ctx 4096"
  fi
}

check_frontend() {
  if [[ -d "$ROOT/apex_rag_demo/web/static/dist" ]]; then
    log "Frontend dist present"
  else
    if command -v npm >/dev/null 2>&1; then
      log "Building frontend (npm)…"
      (cd "$ROOT" && ./scripts/build-frontend.sh) || warn "Frontend build failed"
    else
      warn "No static/dist — install Node/npm and run ./scripts/build-frontend.sh"
    fi
  fi
}

print_next_steps() {
  cat <<EOF

================================================================================
Setup pass complete. Start services in separate terminals:

  1) Llama chat (:8000) — $LLAMA_VENV
     source $LLAMA_VENV/bin/activate
     python3 -m llama_cpp.server --model <your.gguf> --port 8000 --n_ctx 4096

  2) Embeddings (:8081) — only if RAG_EMBEDDING_BACKEND=http in .env
     cd $ROOT && ./scripts/run-embed-server.sh

  3) Web UI (:8080) — project .venv
     cd $ROOT && ./scripts/run-web.sh

Docker (if used): chroma :8002 , neo4j :7474 / :7687
Docs: docs/SETUP.md , docs/CONFIG.md
================================================================================
EOF
}

main() {
  log "Project root: $ROOT"
  check_python
  setup_env_file
  CHROMA_PORT="$(env_get CHROMA_PORT 8002)"
  EMBED_SERVER_PORT="$(env_get EMBED_SERVER_PORT 8081)"
  NEO4J_HTTP_PORT="$(env_get NEO4J_HTTP_PORT 7474)"
  export CHROMA_PORT EMBED_SERVER_PORT NEO4J_HTTP_PORT
  setup_project_venv
  setup_data_dirs
  setup_docker_services
  download_models
  sync_chroma_index
  sync_kg_if_enabled
  check_llama_venv
  check_frontend
  # shellcheck disable=SC1091
  source "$ROOT/.venv/bin/activate"
  "$ROOT/.venv/bin/python" "$ROOT/scripts/neo4j_ping.py" 2>/dev/null || true
  deactivate
  print_next_steps
}

main "$@"
