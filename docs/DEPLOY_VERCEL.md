# Vercel 公開（課題提出用）デプロイ手順

学校課題で **Vercel への公開が指定されている** 場合の手順です。

> **重要**: Vercel 上には **架空のデモデータのみ** を載せてください。  
> 実在の氏名・評価内容・社員 ID など **個人情報・人事データは載せない** でください。  
> 本番運用（実データ）は **`docs/DEPLOYMENT.md`**（社内サーバー）を使用します。

---

## 1. 二層デプロイの考え方

| 用途 | 配置 | データ |
|------|------|--------|
| **課題提出・デモ** | Vercel（画面）+ Railway 等（API） | `seed_demo` の架空データのみ |
| **本番運用** | 社内サーバー（オンプレ） | 実社員データ |

```
【課題提出用】
  ブラウザ → Vercel（React）
              ↓ VITE_API_BASE
            Railway / Render（FastAPI）
              ↓
            Neon / Railway PostgreSQL（デモ DB）

【本番】
  ブラウザ → 社内 nginx → FastAPI → 社内 PostgreSQL
```

同じソースコードを使い、**環境変数とデータ** だけ切り替えます。

---

## 2. 個人情報・セキュリティ（レポートに書ける内容）

課題レポートでは、次の方針を明記すると評価されやすいです。

1. **目的の分離**: 公開デモは「機能実証」、本番は「社内 LAN のみ」
2. **データの分離**: デモ DB には `seed_demo` の架空人物のみ（山田太郎、評価者一郎 等）
3. **表示の明示**: `VITE_DEMO_MODE=true` で画面上部にデモバナーを表示
4. **本番データ非公開**: 実 Excel・実評価は社内サーバーにのみ存在
5. **認証**: JWT によるロール別アクセス（本人 / 評価者 / 管理者）

---

## 3. 事前準備

- [GitHub](https://github.com) アカウント
- [Vercel](https://vercel.com) アカウント（GitHub 連携）
- [Railway](https://railway.app) または [Render](https://render.com) アカウント（API 用・無料枠可）
- [Neon](https://neon.tech) など PostgreSQL（Railway 内蔵 DB でも可）

---

## 4. デモ API のデプロイ（Railway 例）

Vercel は **静的サイト + Serverless** のため、FastAPI は別サービスに載せます。

### 4-1. PostgreSQL

Neon または Railway で DB を作成し、接続 URL を控えます。

### 4-2. Railway にバックエンドをデプロイ

1. GitHub にリポジトリを push
2. Railway → New Project → Deploy from GitHub → リポジトリ選択
3. **Root Directory**: `backend`
4. **Start Command**（`Procfile` がある場合は自動）:
   ```
   uvicorn app.main:app --host 0.0.0.0 --port $PORT --app-dir .
   ```
5. **Variables**（`backend/.env.demo.example` 参照）:

   | 変数 | 値 |
   |------|-----|
   | `DATABASE_URL` | PostgreSQL 接続 URL |
   | `SECRET_KEY` | ランダム文字列 |
   | `DEV_ALLOW_UNSUBMIT` | `true` |
   | `CORS_ORIGINS` | 後で Vercel URL を追加 |
   | `DEFAULT_EMPLOYEE_PASSWORD` | `pass123` |

6. デプロイ後、Railway の公開 URL を控える（例: `https://xxx.up.railway.app`）

### 4-3. デモデータ投入

Railway の Shell またはローカルから DB 接続して:

```bash
cd backend
source .venv/bin/activate
# DATABASE_URL を Railway のものに設定
python -m scripts.seed_demo
```

> **`init_production` や実社員 Excel はデモ環境では使わない**

### 4-4. 動作確認

```bash
curl https://xxx.up.railway.app/api/health
# → {"status":"ok"}
```

---

## 5. Vercel にフロントエンドをデプロイ

### 5-1. Vercel プロジェクト作成

1. [Vercel Dashboard](https://vercel.com/dashboard) → Add New → Project
2. GitHub リポジトリを import
3. **Framework Preset**: Vite
4. **Root Directory**: `frontend`
5. **Build Command**: `npm run build`
6. **Output Directory**: `dist`

### 5-2. 環境変数

Vercel → Project → Settings → Environment Variables:

| 名前 | 値 | 例 |
|------|-----|-----|
| `VITE_API_BASE` | Railway の API URL（末尾スラッシュなし） | `https://xxx.up.railway.app` |
| `VITE_DEMO_MODE` | `true` | デモバナー表示 |

`frontend/.env.vercel.example` を参照。

### 5-3. CORS の更新

Railway の `CORS_ORIGINS` に Vercel の URL を追加して再デプロイ:

```
CORS_ORIGINS=https://your-app.vercel.app,https://your-app-xxx.vercel.app,http://localhost:5173
```

（Preview デプロイ URL も必要なら追加）

### 5-4. デプロイ

Deploy を実行。完了後:

```
https://your-app.vercel.app
```

---

## 6. デモ用ログイン（提出時に記載）

| ロール | 社員ID | パスワード |
|--------|--------|------------|
| 本人 | E001 | pass123 |
| 評価者1 | E010 | pass123 |
| 評価者2 | E020 | pass123 |
| 管理者 | ADMIN001 | admin123 |

画面上部に **「デモ環境 — 架空のサンプルデータです」** バナーが出ていれば OK。

---

## 7. 課題レポートに書く例

> 本システムは二層構成とした。課題提出用に Vercel 上へ UI を公開するが、  
> 人事考課データには個人情報が含まれるため、公開環境には架空のデモデータのみを配置した。  
> 実運用を想定した構成（PostgreSQL・社内 LAN・nginx）は別途 `DEPLOYMENT.md` に設計し、  
> 公開デモと本番でデータおよび配置を分離することでプライバシーリスクを抑えた。

---

## 8. トラブルシューティング

| 症状 | 対処 |
|------|------|
| ログインできない | `VITE_API_BASE` が正しいか、Railway API が起動しているか |
| CORS エラー | Railway の `CORS_ORIGINS` に Vercel の URL を追加 |
| 画面は出るが API 404 | `VITE_API_BASE` に `/api` を付けない（付けるのは path 側） |
| ビルド失敗 | Root Directory が `frontend` か確認 |

---

## 9. 本番（社内）との関係

| 項目 | Vercel デモ | 社内本番 |
|------|-------------|----------|
| 手順書 | 本ファイル | `DEPLOYMENT.md` |
| データ | `seed_demo` | 実社員 Excel |
| 初期化 | `seed_demo` | `init_production` |
| 公開範囲 | インターネット | 社内 LAN のみ |
| デモバナー | 表示 | 非表示 |

---

## 関連ドキュメント

- [DEPLOYMENT.md](./DEPLOYMENT.md) — 社内サーバー本番
- [UAT_CHECKLIST.md](./UAT_CHECKLIST.md) — 機能確認
- [PLAN.md](./PLAN.md) — 設計概要
