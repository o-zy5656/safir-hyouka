#!/bin/bash
# GitHub へ初回 push（リポジトリ作成後に1回実行）
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

REPO_URL="${1:-https://github.com/o-zy5656/safir-hyouka.git}"

if [ ! -d .git ]; then
  git init
  git branch -M main
fi

if ! git remote get-url origin >/dev/null 2>&1; then
  git remote add origin "$REPO_URL"
fi

git add .
if git diff --cached --quiet; then
  echo "コミットする変更がありません。"
else
  git -c user.name="河村昭彦" \
      -c user.email="kawamuraakihiko@users.noreply.github.com" \
      commit -m "$(cat <<'EOF'
サフィール人事考課システム v1

FastAPI + React の3ペイン考課ワークスペース。
課題提出用 Vercel / 本番社内サーバーの二層構成に対応。
EOF
)"
fi

echo ""
echo "=== 次の操作 ==="
echo "1. ブラウザで GitHub リポジトリを作成（未作成の場合）:"
echo "   https://github.com/new?name=safir-hyouka"
echo ""
echo "2. push を実行:"
echo "   git push -u origin main"
echo ""
