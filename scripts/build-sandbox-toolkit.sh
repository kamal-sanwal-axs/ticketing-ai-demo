#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
docker build -t ticketing-ai-demo-sandbox-toolkit:local "$ROOT/docker/sandbox-toolkit"
echo "Built ticketing-ai-demo-sandbox-toolkit:local"
