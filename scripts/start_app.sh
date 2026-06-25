#!/bin/bash
# アプリ起動用（画面 + API）
# 前提: Docker で PostgreSQL が動いていること（docker compose start）
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

echo "=== サフィール人事考課 アプリ起動 ==="

# PostgreSQL 確認
if command -v docker >/dev/null 2>&1; then
  if ! docker compose -f "$ROOT/docker-compose.yml" ps --status running 2>/dev/null | grep -q safir_hyouka_db; then
    echo "PostgreSQL を起動します..."
    docker compose -f "$ROOT/docker-compose.yml" start 2>/dev/null || docker compose -f "$ROOT/docker-compose.yml" up -d
  fi
fi

echo ""
echo "次の2つを、ターミナルを2つ開いてそれぞれ実行してください:"
echo ""
echo "【ターミナル1】API"
echo "  cd $ROOT/backend"
echo "  source .venv/bin/activate"
echo "  uvicorn app.main:app --reload --app-dir ."
echo ""
echo "【ターミナル2】画面"
echo "  cd $ROOT/frontend"
echo "  npm run dev"
echo ""
echo "起動後、ブラウザで開く:"
echo "  http://127.0.0.1:5173"
echo ""
echo "ログイン: E001 / pass123"
echo ""
echo "※ ターミナルを閉じるとアプリも止まります"
