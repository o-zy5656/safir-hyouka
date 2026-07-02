# 本番デプロイ手順（オンプレ・社内LAN）

事業所内サーバーへ **サフィール人事考課システム v1** を配置する手順です。  
想定: Ubuntu 22.04 / 24.04 LTS（他の Linux でも概ね同様）。

## 1. 構成イメージ

```
社内PCブラウザ
    │
    ▼  http://hyouka.local  (ポート80)
┌─────────────────────────────────────┐
│  nginx                               │
│  ・静的ファイル (frontend/dist)     │
│  ・/api/* → 127.0.0.1:8000          │
└──────────────┬──────────────────────┘
               ▼
┌─────────────────────────────────────┐
│  uvicorn (systemd)                   │
│  FastAPI  backend/                   │
└──────────────┬──────────────────────┘
               ▼
┌─────────────────────────────────────┐
│  PostgreSQL 16                       │
│  （Docker または OS 直接インストール）│
└─────────────────────────────────────┘
```

- 規模 200〜300 名向け。**SQLite は本番非推奨**（PostgreSQL 必須）。
- HTTPS は社内ポリシーに応じて nginx に証明書を設定（社内 CA / 自己署名可）。

## 2. サーバー要件

| 項目 | 推奨 |
|------|------|
| CPU | 2コア以上 |
| メモリ | 4 GB 以上 |
| ディスク | 20 GB 以上（DB・ログ余裕） |
| OS | Ubuntu 22.04 / 24.04 LTS |
| ネットワーク | 社内LANのみ公開（インターネット非公開推奨） |

## 3. ソフトウェアのインストール

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip nginx git

# Node.js はビルド時のみ必要（サーバーに常駐させない運用可）
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs
```

PostgreSQL は **方法A（Docker）** または **方法B（OS 直接）** を選択。

### 方法A: Docker で PostgreSQL（推奨・手軽）

```bash
sudo apt install -y docker.io docker-compose-plugin
sudo usermod -aG docker $USER   # 再ログイン後に有効
```

### 方法B: OS に PostgreSQL を直接インストール

```bash
sudo apt install -y postgresql postgresql-contrib
sudo -u postgres createuser -P safir
sudo -u postgres createdb -O safir safir_hyouka
```

## 4. 専用ユーザーと配置

```bash
sudo useradd -r -m -d /opt/safir_hyouka -s /bin/bash safir
sudo mkdir -p /opt/safir_hyouka
sudo chown safir:safir /opt/safir_hyouka
```

ソースを配置（git または zip コピー）:

```bash
sudo -u safir git clone <リポジトリURL> /opt/safir_hyouka
# または rsync / scp で safir_hyouka/ 一式をコピー
```

以降のコマンドは `safir` ユーザーで実行する例:

```bash
sudo -iu safir
cd /opt/safir_hyouka
```

## 5. PostgreSQL の起動

### 方法A: docker-compose.prod.yml

```bash
cd /opt/safir_hyouka
echo "POSTGRES_PASSWORD=$(openssl rand -base64 24)" > .env.db
docker compose -f docker-compose.prod.yml --env-file .env.db up -d
```

接続文字列（`backend/.env` に記載）:

```
DATABASE_URL=postgresql+psycopg://safir:<.env.dbのパスワード>@127.0.0.1:5432/safir_hyouka
```

### 方法B: OS 直接インストール

`backend/.env` の例:

```
DATABASE_URL=postgresql+psycopg://safir:<パスワード>@127.0.0.1:5432/safir_hyouka
```

## 6. バックエンドのセットアップ

```bash
cd /opt/safir_hyouka/backend
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
cp .env.example .env
```

`backend/.env` を本番用に編集:

```env
DATABASE_URL=postgresql+psycopg://safir:＜DBパスワード＞@127.0.0.1:5432/safir_hyouka
SECRET_KEY=＜openssl rand -hex 32 で生成＞
ACCESS_TOKEN_EXPIRE_MINUTES=480
DEV_ALLOW_UNSUBMIT=false
PRODUCTION_MODE=true
DEFAULT_EMPLOYEE_PASSWORD=changeme123
TEMPLATES_DIR=templates
DEFAULT_FACILITY_FILTER=サフィールいなは
ADMIN_JOB_TITLES=施設長
HQ_EVALUATOR_EMPLOYEE_ID=hq001
RETIRED_ARCHIVES_DIR=data/retired_employees
```

| 変数 | 本番の値 |
|------|----------|
| `SECRET_KEY` | 必ずランダムな長い文字列に変更 |
| `DEV_ALLOW_UNSUBMIT` | **false**（開発用の提出取消を無効化） |
| `PRODUCTION_MODE` | **true**（設定漏れを起動時に検出） |
| `DEFAULT_EMPLOYEE_PASSWORD` | 社員取込時の初期パスワード（運用方針に合わせて変更） |

設定確認:

```bash
cd backend && source .venv/bin/activate
python -m scripts.preflight_production
```

### 初回 DB 初期化

**サフィールいなは（名簿 Excel がある場合 — 推奨）**

```bash
# 名簿をサーバーに配置（例）
scp 名簿.xlsx safir@hyouka-server:/opt/safir_hyouka/data/meibo.xlsx

cd /opt/safir_hyouka/backend
source .venv/bin/activate
export ROSTER_XLSX_PATH=/opt/safir_hyouka/data/meibo.xlsx
python -m scripts.import_inaha_roster
# 再取込時: python -m scripts.import_inaha_roster --force
```

取込後、施設長 **i9213** などで管理画面にログイン。初期パスワードは `DEFAULT_EMPLOYEE_PASSWORD`。

**汎用（管理者のみ先に作る場合）**

```bash
export ADMIN_EMPLOYEE_ID=ADMIN001
export ADMIN_PASSWORD='＜8文字以上の強力なパスワード＞'
python -m scripts.init_production
```

> **注意**: `scripts.seed_demo` はデモ用です。**本番では実行しないでください。**

## 7. フロントエンドのビルド

```bash
cd /opt/safir_hyouka
chmod +x scripts/build_prod.sh
./scripts/build_prod.sh
```

成果物: `frontend/dist/`  
API は同一オリジン（nginx 経由）のため、`VITE_API_BASE` の設定は不要です。

## 8. nginx の設定

```bash
sudo cp /opt/safir_hyouka/deploy/nginx.conf.example /etc/nginx/sites-available/safir-hyouka
sudo ln -s /etc/nginx/sites-available/safir-hyouka /etc/nginx/sites-enabled/
```

`/etc/nginx/sites-available/safir-hyouka` の `server_name` と `root` パスを環境に合わせて編集。

```bash
sudo nginx -t
sudo systemctl enable nginx
sudo systemctl reload nginx
```

社内 DNS で `hyouka.local` などの名前をサーバー IP に向けます。

## 9. API の常駐（systemd）

```bash
sudo cp /opt/safir_hyouka/deploy/safir-hyouka-api.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable safir-hyouka-api
sudo systemctl start safir-hyouka-api
sudo systemctl status safir-hyouka-api
```

ログ確認:

```bash
journalctl -u safir-hyouka-api -f
```

## 10. 動作確認

1. ブラウザで `http://<サーバー名>/` を開く
2. `ADMIN001` でログイン
3. 管理画面 → **考課期間** を作成・開始
4. **社員取込** で Excel をアップロード（`docs/employee_import_template.xlsx` 参照）
5. 本人・評価者アカウントでログインし、入力〜提出を確認

API ヘルスチェック:

```bash
curl -s http://127.0.0.1/api/health
# nginx 経由
curl -s http://127.0.0.1/api/health
```

## 11. 運用開始チェックリスト

- [ ] `SECRET_KEY` を本番用に変更済み
- [ ] `DEV_ALLOW_UNSUBMIT=false`
- [ ] PostgreSQL のパスワードをデフォルトから変更済み
- [ ] 管理者パスワードを安全に保管
- [ ] 社員取込 Excel の評価者 ID が正しい
- [ ] 評価者ユーザーの `role` が `evaluator1` / `evaluator2` に設定されている
- [ ] サーバーは社内LANのみ到達可能
- [ ] DB バックアップ手順を確立（下記）

### 評価者ロールについて

社員 Excel 取込時に、次のいずれかでロールが設定されます。

1. **ロール列**（任意）: `本人` / `評価者1` / `評価者2`
2. **自動判定**: ロール列がない場合、他行の「評価者1/2社員ID」に登場する ID を評価者に設定
3. **管理画面**: 「ユーザー」タブから個別に変更可能

取込後、管理画面で評価者が正しいロールになっているか確認してください。

## 12. バックアップ

### PostgreSQL（Docker）

```bash
docker exec safir_hyouka_db pg_dump -U safir safir_hyouka > backup_$(date +%Y%m%d).sql
```

### PostgreSQL（OS 直接）

```bash
pg_dump -U safir safir_hyouka > backup_$(date +%Y%m%d).sql
```

### テンプレート JSON

```bash
tar czf templates_$(date +%Y%m%d).tar.gz -C /opt/safir_hyouka/backend templates/
```

週次バックアップ + 考課期間前後の手動バックアップを推奨。

## 13. 更新手順

```bash
sudo -iu safir
cd /opt/safir_hyouka
git pull   # または新バージョンを配置

# バックエンド
cd backend && source .venv/bin/activate
pip install -r requirements.txt

# フロントエンド
cd .. && ./scripts/build_prod.sh

# API 再起動
sudo systemctl restart safir-hyouka-api
```

DB スキーマ変更がある場合は `alembic upgrade head`（初回は `alembic stamp head`）。起動時の `migrate_schema()` も後方互換のため実行されます。

## 14. サフィールいなは — テストサーバー → パイロット

### サーバーがまだない場合（今すぐできること）

テストサーバー調達前でも、**Mac 上で本番に近い構成**を試せます。

| 順 | 内容 | コマンド / 場所 |
|----|------|-----------------|
| 1 | **現状の開発環境でパイロット** | すでに動いている SQLite + 名簿データで、i1005 / i9213 等で操作確認 |
| 2 | **PostgreSQL リハーサル** | Docker Desktop 起動後: `./scripts/rehearse_production_local.sh` |
| 3 | **UAT 再実行** | `cd backend && python -m scripts.run_uat` |
| 4 | **チェックリスト** | `docs/UAT_CHECKLIST.md` セクション1〜6 |

リハーサルスクリプトは PostgreSQL + `PRODUCTION_MODE=true` + 名簿取込 + フロントビルドまで一括で行います。

### テストサーバー調達時の目安

| 項目 | 最低限 |
|------|--------|
| 用途 | 社内LANのみ（インターネット非公開） |
| OS | Ubuntu 22.04 / 24.04 LTS |
| スペック | CPU 2コア / メモリ 4GB / SSD 20GB |
| 候補 | 事業所内の旧PC、NAS の VM、レンタル VPS（**VPN 経由のみ**） |

調達後は §1〜§13 の手順 + 下記 §14-1 以降で本番同等の確認を行います。

### 14-1. ローカルからサーバーへ配置

```bash
chmod +x scripts/package_for_server.sh
./scripts/package_for_server.sh
# 生成された tar.gz をサーバーへ scp
```

### 14-2. テストサーバーで UAT 再実行

```bash
curl -s http://127.0.0.1/api/health
cd backend && source .venv/bin/activate
python -m scripts.run_uat
```

### 14-3. パイロット10名（例）

| 役割 | 社員ID | 確認内容 |
|------|--------|----------|
| 本人A | i1005 | 自己評価 下書き→提出 |
| 本人B | i2002 | 未入力バリデーション |
| 評価者1 | i9212 または i3001 | 部下の考課 |
| 施設長 | i9213 | 管理画面＋部下考課 |
| 本部 | hq001 | 施設長の二次評価のみ |

全員初期パスワード → **初回ログインで変更**を徹底。

### 14-4. 本番前の必須作業

- [ ] `python -m scripts.preflight_production` が OK
- [ ] 施設長・本部のパスワード変更
- [ ] `./deploy/backup_db.sh` を1回実行して復旧手順を確認
- [ ] `docs/UAT_CHECKLIST.md` セクション7（PostgreSQL・nginx）をテストサーバーで実施

## 15. トラブルシューティング

| 症状 | 確認 |
|------|------|
| 画面は出るがログインできない | `journalctl -u safir-hyouka-api`、DB 接続、`SECRET_KEY` |
| 502 Bad Gateway | API が起動しているか `curl http://127.0.0.1:8000/api/health` |
| 社員取込エラー | Excel 列名・必須列（`docs/PLAN.md` 8章） |
| 評価者が入力できない | 自己評価が提出済みか、評価者ロール・評1提出状況 |

## 16. セキュリティメモ

- サーバーへの SSH は鍵認証 + 限定ユーザーのみ
- ファイアウォールで 80/443 を社内サブネットのみ許可
- `backend/.env` のパーミッションは `600`（`chmod 600 .env`）
- 不要になったデモ DB（`safir_hyouka.db`）は本番サーバーに置かない

## 関連ドキュメント

- [PLAN.md](./PLAN.md) — 設計・API 一覧
- [POSTGRESQL_SETUP.md](./POSTGRESQL_SETUP.md) — DB 接続（開発向け）
- [UAT_CHECKLIST.md](./UAT_CHECKLIST.md) — 受入テストチェックリスト
- [TEMPLATE_GUIDE.md](./TEMPLATE_GUIDE.md) — 評価表 JSON の差し替え
