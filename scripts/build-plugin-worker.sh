#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
docker compose --profile plugins build plugin-worker
echo "Built ${PLUGIN_DOCKER_IMAGE:-ticketing-ai-demo-plugin-worker:local}"
