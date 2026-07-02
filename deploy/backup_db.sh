#!/bin/bash
# PostgreSQL バックアップ（Docker / OS 直接の両方に対応）
set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-/opt/safir_hyouka/backups}"
STAMP="$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"

if docker ps --format '{{.Names}}' 2>/dev/null | grep -qx safir_hyouka_db; then
  docker exec safir_hyouka_db pg_dump -U safir safir_hyouka > "$BACKUP_DIR/safir_hyouka_${STAMP}.sql"
  echo "Docker バックアップ: $BACKUP_DIR/safir_hyouka_${STAMP}.sql"
elif command -v pg_dump >/dev/null 2>&1; then
  pg_dump -U safir safir_hyouka > "$BACKUP_DIR/safir_hyouka_${STAMP}.sql"
  echo "pg_dump バックアップ: $BACKUP_DIR/safir_hyouka_${STAMP}.sql"
else
  echo "PostgreSQL バックアップ方法が見つかりません（Docker コンテナ名 safir_hyouka_db または pg_dump）" >&2
  exit 1
fi

if [ -d /opt/safir_hyouka/backend/templates ]; then
  tar czf "$BACKUP_DIR/templates_${STAMP}.tar.gz" -C /opt/safir_hyouka/backend templates/
  echo "テンプレート: $BACKUP_DIR/templates_${STAMP}.tar.gz"
fi
