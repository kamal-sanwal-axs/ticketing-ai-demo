#!/usr/bin/env bash
# Run the web UI with the project venv (not ~/.venv-llama-cpp).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
if [[ ! -x "$ROOT/.venv/bin/python" ]]; then
  echo "Missing $ROOT/.venv — run: python3 -m venv .venv && pip install -r requirements.txt"
  exit 1
fi
exec "$ROOT/.venv/bin/uvicorn" apex_rag_demo.web.app:app --reload --port "${PORT:-8080}"
