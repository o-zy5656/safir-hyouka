# サフィール人事考課システム

人事考課を3ペインワークスペースで進める Web アプリケーション（v1 骨格）。

## 構成

- `backend/` — FastAPI + PostgreSQL
- `frontend/` — React + TypeScript（Vite）
- `docs/DEPLOYMENT.md` — **本番デプロイ（社内サーバー）**
- `docs/DEPLOY_VERCEL.md` — **課題提出用 Vercel 公開（デモデータのみ）**
- `docs/YOU_DO_THIS.md` — **あなたがやること（GitHub push のみ）**
- `docs/UAT_CHECKLIST.md` — **受入テストチェックリスト**
- `docs/POSTGRESQL_SETUP.md` — PostgreSQL セットアップ（開発向け）
- `docs/TEMPLATE_GUIDE.md` — 評価表テンプレート差し替え手順（非エンジニア向け）
- `backend/templates/` — 自己評価表・考課表 JSON テンプレート

## 起動方法（開発）

### クイックスタート（PostgreSQL 不要・SQLite）

```bash
./scripts/setup_dev.sh
```

その後、README 末尾の2コマンドで API と画面を起動。

### PostgreSQL を使う場合

Docker または Postgres.app で DB を起動し、`backend/.env` の `DATABASE_URL` を PostgreSQL 用に変更。
詳細は **`docs/POSTGRESQL_SETUP.md`** を参照。

### 手動セットアップ

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python -m scripts.seed_demo
uvicorn app.main:app --reload --app-dir .
```

```bash
cd frontend
npm install
npm run dev
```

ブラウザで http://localhost:5173 を開く。

## テンプレート差し替え

評価表の変更は `backend/templates/` 内の JSON を差し替えます。
詳細は `docs/TEMPLATE_GUIDE.md` を参照してください。

## 社員Excel取込

列形式は `docs/PLAN.md` 8章を参照。サンプルファイル:

- `docs/employee_import_template.xlsx`（`python -m scripts.generate_import_template` で再生成可）

新規社員の初期パスワードは `changeme123`（`backend/.env` の `DEFAULT_EMPLOYEE_PASSWORD` で変更可）。

## デプロイ方針（二層構成）

| 用途 | 手順 | データ |
|------|------|--------|
| **学校課題・公開デモ** | [`docs/DEPLOY_VERCEL.md`](docs/DEPLOY_VERCEL.md) | 架空データのみ（`seed_demo`） |
| **本番（実運用）** | [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md) | 実社員データ・社内 LAN |

Vercel には **個人情報を載せない** でください。画面上部のデモバナー（`VITE_DEMO_MODE=true`）で明示します。

## 本番デプロイ（社内サーバー）

事業所内サーバーへの配置手順は **`docs/DEPLOYMENT.md`** を参照。

- nginx + uvicorn（systemd）+ PostgreSQL
- 初回: `python -m scripts.init_production`（`seed_demo` は本番で使わない）
- 設定例: `deploy/nginx.conf.example`, `deploy/safir-hyouka-api.service`

## 受入テスト（本番前）

**`docs/UAT_CHECKLIST.md`** に沿って、考課フロー全体を確認してください。

## v1 実装状況

- [x] 設計プラン
- [x] JSON テンプレート（令和8年度 夏季）
- [x] 認証・本人ワークスペース（下書き・提出）
- [x] 評価者ワークスペース（一覧・参照・下書き保存・提出）
- [x] 管理画面（期間・社員取込・差し戻し・Excel出力）
- [x] 本番デプロイ手順（`docs/DEPLOYMENT.md`）
