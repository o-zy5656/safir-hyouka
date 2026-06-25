#!/bin/bash
# Railway デプロイ後、デモデータを投入する（Railway Shell で実行）
set -euo pipefail
cd "$(dirname "$0")/.."
python -m scripts.seed_demo
echo "デモデータ投入完了"
