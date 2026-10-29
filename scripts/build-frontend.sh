#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT/frontend"
if [[ ! -d node_modules ]]; then
  npm install --registry https://registry.npmjs.org
fi
npm run build
echo "Built UI → apex_rag_demo/web/static/dist/"
