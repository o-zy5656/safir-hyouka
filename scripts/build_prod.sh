#!/bin/bash
# 本番用フロントエンドビルド
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

echo "=== フロントエンド本番ビルド ==="
cd "$ROOT/frontend"

if [ -f package-lock.json ]; then
  npm ci
else
  npm install
fi

npm run build

echo ""
echo "ビルド完了: $ROOT/frontend/dist"
echo "nginx の root をこのディレクトリに設定してください。"
