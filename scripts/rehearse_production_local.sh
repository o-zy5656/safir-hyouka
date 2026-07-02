#!/bin/bash
# テストサーバーがなくても Mac 上で本番に近い構成を試す（PostgreSQL + 名簿取込）
#
# 前提: Docker Desktop が起動していること
#
# 使い方:
#   cd safir_hyouka
#   ./scripts/rehearse_production_local.sh
#
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "=== 本番リハーサル（ローカル Mac） ==="

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker Desktop をインストールして起動してください。" >&2
  echo "https://www.docker.com/products/docker-desktop/" >&2
  exit 1
fi

# DB パスワード（ローカル専用）
if [ ! -f .env.db ]; then
  echo "POSTGRES_PASSWORD=$(openssl rand -base64 16 | tr -d '/+=' | head -c 20)" > .env.db
  echo ".env.db を作成しました"
fi
# shellcheck disable=SC1091
source .env.db

echo "[1/6] PostgreSQL 起動..."
docker compose -f docker-compose.prod.yml --env-file .env.db up -d
sleep 3

echo "[2/6] Python 環境..."
cd backend
if [ ! -d .venv ]; then
  python3 -m venv .venv
fi
source .venv/bin/activate
pip install -q --upgrade pip
pip install -q -r requirements.txt

echo "[3/6] backend/.env（PostgreSQL 用）..."
if [ ! -f .env ]; then
  cp .env.example .env
fi

SECRET="$(openssl rand -hex 32)"
export REHEARSE_SECRET="$SECRET"
export REHEARSE_DB_PASSWORD="$POSTGRES_PASSWORD"
python3 <<'PY'
import os
import re
from pathlib import Path

env = Path(".env")
text = env.read_text() if env.exists() else ""
pw = os.environ["REHEARSE_DB_PASSWORD"]
secret = os.environ["REHEARSE_SECRET"]
repl = {
    r"^DATABASE_URL=.*": f"DATABASE_URL=postgresql+psycopg://safir:{pw}@127.0.0.1:5432/safir_hyouka",
    r"^SECRET_KEY=.*": f"SECRET_KEY={secret}",
    r"^DEV_ALLOW_UNSUBMIT=.*": "DEV_ALLOW_UNSUBMIT=false",
    r"^PRODUCTION_MODE=.*": "PRODUCTION_MODE=true",
}
for pat, val in repl.items():
    if re.search(pat, text, re.M):
        text = re.sub(pat, val, text, flags=re.M)
    else:
        text += f"\n{val}\n"
env.write_text(text)
PY

echo "[4/6] 本番前チェック..."
python -m scripts.preflight_production

ROSTER="${ROSTER_XLSX_PATH:-}"
if [ -z "$ROSTER" ]; then
  DEFAULT="$HOME/Library/CloudStorage/Dropbox/safir_tool/人事考課/名簿.xlsx"
  if [ -f "$DEFAULT" ]; then
    ROSTER="$DEFAULT"
  fi
fi

echo "[5/6] 名簿取込..."
if [ -n "$ROSTER" ] && [ -f "$ROSTER" ]; then
  export ROSTER_XLSX_PATH="$ROSTER"
  python -m scripts.import_inaha_roster --force
else
  echo "  名簿 Excel が見つかりません。スキップします。"
  echo "  後で: export ROSTER_XLSX_PATH=/path/to/名簿.xlsx"
  echo "        python -m scripts.import_inaha_roster"
fi

echo "[6/6] フロントビルド..."
cd "$ROOT"
./scripts/build_prod.sh

echo ""
echo "=== リハーサル環境 OK ==="
echo ""
echo "起動（2ターミナル）:"
echo "  # API"
echo "  cd $ROOT/backend && source .venv/bin/activate"
echo "  uvicorn app.main:app --host 127.0.0.1 --port 8000 --app-dir ."
echo ""
echo "  # 画面（dist を配信 — 簡易）"
echo "  cd $ROOT/frontend/dist && python3 -m http.server 8080"
echo ""
echo "ブラウザ: http://127.0.0.1:8080"
echo "（API は vite proxy なしのため、別途 nginx または VITE_API_BASE=http://127.0.0.1:8000 で dev 起動も可）"
echo ""
echo "ログイン例: i9213 / changeme123（取込後）"
echo "UAT: cd backend && python -m scripts.run_uat"
