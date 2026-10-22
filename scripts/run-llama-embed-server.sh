#!/usr/bin/env bash
# llama.cpp embedding server on http://localhost:8081/v1 (GGUF + --embedding).
# Set in .env: RAG_EMBEDDING_BACKEND=llama  EMBED_MODEL=<your-embed-gguf>
set -euo pipefail
PORT="${EMBED_SERVER_PORT:-8081}"
MODEL="${LLAMA_EMBED_GGUF:-$HOME/models/nomic-embed/nomic-embed-text-v1.5.f16.gguf}"
PYTHON="${LLAMA_PYTHON:-$HOME/.venv-llama-cpp/bin/python}"
if [[ ! -x "$PYTHON" ]]; then
  echo "llama-cpp venv not found at $PYTHON"
  exit 1
fi
exec "$PYTHON" -m llama_cpp.server --embedding --model "$MODEL" --port "$PORT"
