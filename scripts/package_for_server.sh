#!/bin/bash
# テストサーバーへコピーする用のアーカイブを作成
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="${1:-$ROOT/../safir_hyouka_deploy_$(date +%Y%m%d).tar.gz}"

cd "$ROOT"
tar czf "$OUT" \
  --exclude='.git' \
  --exclude='backend/.venv' \
  --exclude='backend/safir_hyouka.db' \
  --exclude='backend/data/retired_employees/*.json' \
  --exclude='backend/data/retired_employees/*.xlsx' \
  --exclude='frontend/node_modules' \
  --exclude='frontend/dist' \
  --exclude='.env' \
  --exclude='backend/.env' \
  .

echo "作成しました: $OUT"
echo "サーバーで: tar xzf $(basename "$OUT") -C /opt/safir_hyouka"
