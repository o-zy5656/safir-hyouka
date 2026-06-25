# PostgreSQL セットアップ手順（macOS）

人事考課システムのデータを保存する PostgreSQL の入れ方です。

> **今すぐ試すだけなら**: PostgreSQL は不要です。  
> `./scripts/setup_dev.sh` で **SQLite**（ファイル1つ）が使われ、同じ画面を試せます。  
> 本番（200〜300名）では PostgreSQL を使います。

---

## 開発用クイックスタート（SQLite・PostgreSQL 不要）

```bash
cd safir_hyouka
./scripts/setup_dev.sh
```

データは `backend/safir_hyouka.db` に保存されます。

---

## 方法A: Docker（PostgreSQL・開発向け）

Docker Desktop を入れている場合、いちばん手軽です。

### 1. Docker Desktop をインストール

https://www.docker.com/products/docker-desktop/

インストール後、Docker Desktop を起動してください。

### 2. データベースを起動

プロジェクトのルート（`safir_hyouka`）で:

```bash
docker compose up -d
```

### 3. 動作確認

```bash
docker compose ps
```

`db` が `running` になっていれば OK です。

### 4. 停止・再開

```bash
docker compose stop      # 停止
docker compose start     # 再開
docker compose down      # 停止＋コンテナ削除（データは volume に残る）
```

接続情報（`.env` の `DATABASE_URL` を以下に変更）:

```
DATABASE_URL=postgresql+psycopg://safir:safir@localhost:5432/safir_hyouka
```

---

## 方法B: Postgres.app（Macに直接入れる・GUIあり）

https://postgresapp.com/ からダウンロードしてインストール。

1. Postgres.app を起動し「Initialize」
2. メニューの PostgreSQL バージョン横の象マーク → Terminal で `psql` を使えるようにする
3. ターミナルで次を実行:

```sql
CREATE USER safir WITH PASSWORD 'safir';
CREATE DATABASE safir_hyouka OWNER safir;
```

---

## 方法C: Homebrew（ターミナルに慣れている場合）

```bash
# Homebrew が無い場合: https://brew.sh/ の手順でインストール
brew install postgresql@16
brew services start postgresql@16

createuser -s safir 2>/dev/null || true
psql postgres -c "ALTER USER safir WITH PASSWORD 'safir';"
psql postgres -c "CREATE DATABASE safir_hyouka OWNER safir;"
```

---

## アプリ側のセットアップ（DB起動後）

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env

# デモデータ投入
python -m scripts.seed_demo

# API起動
uvicorn app.main:app --reload --app-dir .
```

別ターミナルでフロントエンド:

```bash
cd frontend
npm install
npm run dev
```

http://localhost:5173 を開き、デモアカウントでログイン:

| 役割 | 社員ID | パスワード |
|------|--------|-----------|
| 本人 | E001 | pass123 |
| 評価者1 | E010 | pass123 |
| 評価者2 | E020 | pass123 |

---

## 本番（事業所内サーバー）のイメージ

- Linux サーバーに PostgreSQL をインストール
- データはサーバー内のディスクに保存（社外に出さない）
- 定期的なバックアップ（`pg_dump`）を人事担当と決める
- パスワードは開発用の `safir` とは別の強いものに変更

---

## よくあるエラー

### `connection refused` / 接続できない

- PostgreSQL が起動しているか確認（Docker なら `docker compose ps`）
- `.env` の `DATABASE_URL` が正しいか確認

### `role "safir" does not exist`

- 上記のユーザー作成 SQL を実行

### `database "safir_hyouka" does not exist`

```sql
CREATE DATABASE safir_hyouka OWNER safir;
```

---

## PostgreSQL とは（おさらい）

アプリのデータ（社員・考課内容・提出状態）を**安全に預かる倉庫**です。
Excel のように1ファイルで渡すのではなく、アプリ（FastAPI）が読み書きします。
