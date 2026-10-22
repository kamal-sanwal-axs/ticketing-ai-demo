#!/usr/bin/env bash
# OpenAI-compatible embeddings on http://localhost:8081/v1 (sentence-transformers).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
PORT="${EMBED_SERVER_PORT:-8081}"
if [[ ! -x "$ROOT/.venv/bin/python" ]]; then
  echo "Missing $ROOT/.venv — run: python3 -m venv .venv && pip install -r requirements.txt"
  exit 1
fi
exec "$ROOT/.venv/bin/uvicorn" apex_rag_demo.embed_server:app \
  --host 0.0.0.0 \
  --port "$PORT"
