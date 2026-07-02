# 公開直前チェックリスト（Vercel + Railway）

このドキュメントの手順を完了すると、**あとは Vercel / Railway で「Deploy」を押すだけ**の状態になります。

---

## 実装済みの内容

| 項目 | 内容 |
|------|------|
| 仮名データ | `seed_demo` が架空氏名・デモ施設2件・賞与表サンプルを投入 |
| ログイン不要 | `DEMO_MODE=true` 時、フロントが自動で `ADMIN001` としてログイン |
| 施設マスタ | `data/facilities.demo.json`（デモ施設いなは / そはら） |
| 個人情報保護 | `bonus_amounts/*.json` は git 除外。デモは seed で再生成 |
| デモバナー | `VITE_DEMO_MODE=true` で画面上部に表示 |

---

## あなたが行うこと（公開の最終3ステップ）

### ステップ 1: GitHub に push

```bash
cd /Users/kawamuraakihiko/Desktop/My-First-Project/safir_hyouka
git add .
git commit -m "公開デモ: 仮名データ・ログイン不要・Vercel/Railway 準備"
git push origin main
```

> `.env` や `bonus_amounts/*.json`（実データ）はコミットしないでください。

---

### ステップ 2: Railway に API をデプロイ

1. https://railway.app → New Project → Deploy from GitHub
2. リポジトリ `safir_hyouka` を選択
3. **Root Directory**: `backend`
4. PostgreSQL を Add Service で追加
5. **Variables**（`backend/.env.demo.example` をコピーして編集）:

| 変数 | 値 |
|------|-----|
| `DATABASE_URL` | Railway PostgreSQL の接続 URL |
| `SECRET_KEY` | `openssl rand -hex 32` で生成 |
| `AUTO_SEED_DEMO` | `true` |
| `DEMO_MODE` | `true` |
| `DEMO_GUEST_EMPLOYEE_ID` | `ADMIN001` |
| `FACILITIES_CONFIG_PATH` | `data/facilities.demo.json` |
| `BONUS_WORKBOOK_TEMPLATE_PATH` | （空のまま） |
| `BONUS_NAME_ALIASES` | `{}` |
| `DEV_ALLOW_UNSUBMIT` | `true` |
| `DEFAULT_EMPLOYEE_PASSWORD` | `pass123` |
| `CORS_ORIGINS` | 後で Vercel URL を追加（暫定: `http://localhost:5173`） |

6. Deploy 完了後、公開 URL を控える（例: `https://safir-hyouka-api.up.railway.app`）

7. 動作確認:

```bash
curl https://YOUR-RAILWAY-URL.up.railway.app/api/health
# → {"status":"ok"}

curl -X POST https://YOUR-RAILWAY-URL.up.railway.app/api/auth/demo-login
# → {"access_token":"..."}
```

初回起動時に `AUTO_SEED_DEMO=true` でデモデータが自動投入されます。  
再投入が必要なときは Railway Shell で:

```bash
python -m scripts.seed_demo --force
```

---

### ステップ 3: Vercel に画面をデプロイ

1. https://vercel.com → Add New → Project → GitHub リポジトリ
2. **Root Directory**: `frontend`
3. **Environment Variables**:

| 名前 | 値 |
|------|-----|
| `VITE_API_BASE` | Railway の URL（例: `https://safir-hyouka-api.up.railway.app`） |
| `VITE_DEMO_MODE` | `true` |

4. Deploy

5. Railway の `CORS_ORIGINS` に Vercel URL を追加して再デプロイ:

```
CORS_ORIGINS=https://your-app.vercel.app,http://localhost:5173
```

6. ブラウザで Vercel URL を開く → **ログイン画面なし**で賞与表が表示されれば成功

---

## ローカルでデモ動作を確認する

```bash
# ターミナル1: API（デモ設定）
cd backend
cp .env.demo.example .env.demo
# .env.demo の DATABASE_URL をローカル PostgreSQL または SQLite に変更する場合は
# 別途 .env を編集（デモ確認は PostgreSQL 推奨）

# .env にデモ用を反映（既存 .env を上書きしないよう注意）
# 手動で DEMO_MODE=true, FACILITIES_CONFIG_PATH=data/facilities.demo.json を追加

python -m scripts.seed_demo --force
DEMO_MODE=true FACILITIES_CONFIG_PATH=data/facilities.demo.json \
  uvicorn app.main:app --reload --app-dir .

# ターミナル2: フロント
cd frontend
VITE_DEMO_MODE=true VITE_API_BASE=http://127.0.0.1:8000 npm run dev
```

---

## 課題レポート用の説明（コピペ可）

> 個人情報保護のため、公開環境には架空のデモデータのみを配置した。  
> Vercel 上の UI は `VITE_DEMO_MODE` により自動ログインし、ID・パスワード入力なしで機能を閲覧できる。  
> API・DB は Railway に分離し、本番（実名簿）は社内 LAN のみとした二層構成としている。

---

## トラブルシューティング

| 症状 | 対処 |
|------|------|
| 「デモ用 API に接続できません」 | `VITE_API_BASE` と Railway の起動状態を確認 |
| CORS エラー | Railway の `CORS_ORIGINS` に Vercel URL を追加 |
| 賞与表が空 | `seed_demo --force` を Railway Shell で実行 |
| 実名が表示される | `DEMO_MODE` / `FACILITIES_CONFIG_PATH` / DB がデモ用か確認 |

---

## 関連ファイル

- `backend/.env.demo.example` — Railway 用環境変数テンプレート
- `frontend/.env.vercel.example` — Vercel 用環境変数テンプレート
- `backend/data/facilities.demo.json` — 仮名施設マスタ
- `backend/scripts/seed_demo.py` — 仮名職員・賞与データ投入
- `docs/DEPLOY_VERCEL.md` — 詳細手順
