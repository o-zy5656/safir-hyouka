#!/bin/bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "=== サフィール人事考課: 開発環境セットアップ ==="

USE_DOCKER_DB=0
if command -v docker >/dev/null 2>&1 && [ "${USE_POSTGRES:-}" = "1" ]; then
  USE_DOCKER_DB=1
  echo "[DB] Docker で PostgreSQL を起動..."
  docker compose up -d
  sleep 3
fi

if [ "$USE_DOCKER_DB" = 0 ]; then
  echo "[DB] SQLite を使用（PostgreSQL 未使用）"
  echo "      後から PostgreSQL に切り替える場合: docs/POSTGRESQL_SETUP.md"
fi

echo "[1/3] Python 仮想環境をセットアップ..."
cd backend
if [ ! -d .venv ]; then
  python3 -m venv .venv
fi
source .venv/bin/activate
python -m pip install -q --upgrade pip
pip install -q -r requirements.txt

if [ ! -f .env ]; then
  cp .env.example .env
fi

if [ "$USE_DOCKER_DB" = 1 ]; then
  grep -q '^DATABASE_URL=postgresql' .env || echo "DATABASE_URL=postgresql+psycopg://safir:safir@localhost:5432/safir_hyouka" >> .env
fi

echo "[2/3] デモデータを投入..."
python -m scripts.seed_demo

echo "[3/3] フロントエンドの依存関係..."
cd "$ROOT/frontend"
npm install --silent

echo ""
echo "=== セットアップ完了 ==="
echo ""
echo "次のコマンドを別ターミナル2つで実行:"
echo ""
echo "  # ターミナル1: API"
echo "  cd $ROOT/backend && source .venv/bin/activate && uvicorn app.main:app --reload --app-dir ."
echo ""
echo "  # ターミナル2: 画面"
echo "  cd $ROOT/frontend && npm run dev"
echo ""
echo "ブラウザ: http://localhost:5173"
echo "ログイン例: E001 / pass123"
