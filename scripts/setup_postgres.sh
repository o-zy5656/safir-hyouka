#!/bin/bash
# Docker + PostgreSQL セットアップ（B案）
# 前提: Docker Desktop をインストールし、起動していること
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "=== Docker + PostgreSQL セットアップ ==="

if ! command -v docker >/dev/null 2>&1; then
  echo ""
  echo "ERROR: Docker が見つかりません。"
  echo ""
  echo "次の手順で Docker Desktop をインストールしてください:"
  echo "  1. https://www.docker.com/products/docker-desktop/ を開く"
  echo "  2. 「Download for Mac」をクリック（お使いの Mac に合わせて Apple Silicon / Intel）"
  echo "  3. ダウンロードした .dmg を開き、Docker を Applications にドラッグ"
  echo "  4. Applications から Docker を起動（初回は数分かかります）"
  echo "  5. メニューバーにクジラのアイコンが出たら、このスクリプトを再実行"
  echo ""
  exit 1
fi

if ! docker info >/dev/null 2>&1; then
  echo ""
  echo "ERROR: Docker は入っていますが、起動していません。"
  echo "  → Applications から「Docker」を起動し、クジラアイコンが安定するまで待ってから再実行してください。"
  echo ""
  exit 1
fi

echo "[1/5] PostgreSQL コンテナを起動..."
docker compose up -d

echo "[2/5] DB の準備を待機..."
for i in $(seq 1 30); do
  if docker compose exec -T db pg_isready -U safir -d safir_hyouka >/dev/null 2>&1; then
    echo "      接続 OK"
    break
  fi
  if [ "$i" -eq 30 ]; then
    echo "ERROR: PostgreSQL の起動がタイムアウトしました"
    docker compose logs db
    exit 1
  fi
  sleep 1
done

echo "[3/5] backend/.env を PostgreSQL 用に更新..."
ENV_FILE="$ROOT/backend/.env"
if grep -q '^DATABASE_URL=sqlite' "$ENV_FILE" 2>/dev/null; then
  sed -i '' 's|^DATABASE_URL=sqlite.*|DATABASE_URL=postgresql+psycopg://safir:safir@localhost:5432/safir_hyouka|' "$ENV_FILE"
elif ! grep -q '^DATABASE_URL=postgresql' "$ENV_FILE" 2>/dev/null; then
  echo "DATABASE_URL=postgresql+psycopg://safir:safir@localhost:5432/safir_hyouka" >> "$ENV_FILE"
fi
echo "      DATABASE_URL=postgresql+psycopg://safir:safir@localhost:5432/safir_hyouka"

echo "[4/5] Python 環境とデモデータ..."
cd "$ROOT/backend"
source .venv/bin/activate
pip install -q -r requirements.txt
python -m scripts.seed_demo

echo "[5/5] 接続テスト..."
python -c "
from sqlalchemy import create_engine, text
from app.config import settings
engine = create_engine(settings.database_url)
with engine.connect() as conn:
    n = conn.execute(text('SELECT COUNT(*) FROM users')).scalar()
    print(f'      users テーブル: {n} 件')
"

echo ""
echo "=== 完了 ==="
echo ""
echo "PostgreSQL が使える状態になりました（費用: Docker Personal 想定で 0円）。"
echo ""
echo "起動コマンド:"
echo "  cd $ROOT/backend && source .venv/bin/activate && uvicorn app.main:app --reload --app-dir ."
echo "  cd $ROOT/frontend && npm run dev"
echo ""
echo "停止（DBのみ）: docker compose stop"
echo "再開:         docker compose start"
