# 現状調査結果（2025年6月）

Vercel 公開に向けて、お使いの PC と GitHub の状態を調査しました。

---

## 調査サマリー

| 項目 | 状態 | 意味 |
|------|------|------|
| **本番アプリ** | `safir_hyouka/` に完成 | ✅ デプロイ可能なコードはある |
| **GitHub への公開** | **未登録** | ❌ Vercel は GitHub 連携が一般的 → 先に push が必要 |
| **GitHub アカウント** | `o-zy5656` 存在 | ✅ https://github.com/o-zy5656 |
| **公開リポジトリ** | `oz-y` のみ | 人事考課プロジェクトはまだない |
| **旧 remote** | `kaigo-dx-study` | 親フォルダの設定。private/削除の可能性あり |
| **Vercel CLI** | 未インストール | ブラウザから設定すれば不要 |
| **Railway CLI** | 未インストール | 同上 |

**結論**: コードは揃っているが、**GitHub に上げる作業がまだ**です。  
ここが終われば Vercel / Railway の設定に進めます。

---

## フォルダ構成の整理

```
My-First-Project/          ← ここが Git 管理（別プロジェクト混在）
├── safir_hyouka/          ← ★ 今回の本番アプリ（Git 未登録）
├── サフィール人事考課/      ← 旧試作品（HTML 1枚・別物）
├── 週報/
├── 介護記録チェック/
└── index.html
```

- **課題提出に使うのは `safir_hyouka/` だけ**
- `サフィール人事考課/` は以前の静的 HTML 試作品（混同しない）

---

## 二層デプロイ（再確認）

| 用途 | 置き場所 | データ |
|------|----------|--------|
| **学校課題・Vercel 公開** | Vercel + Railway | 架空データ（E001 等）のみ |
| **本番（実務）** | 社内サーバー | 実社員データ |

詳細: [`DEPLOY_VERCEL.md`](./DEPLOY_VERCEL.md) / [`DEPLOYMENT.md`](./DEPLOYMENT.md)

---

## これからやること（順番どおり）

### ステップ 1: GitHub に新リポジトリを作る（5分）

1. ブラウザで https://github.com/new を開く
2. 設定例:
   - Repository name: `safir-hyouka`
   - Public（課題提出なら Public で OK）
   - README は **追加しない**（空で作成）
3. Create repository

### ステップ 2: safir_hyouka を GitHub に push（10分）

ターミナルで:

```bash
cd /Users/kawamuraakihiko/Desktop/My-First-Project/safir_hyouka

git init
git add .
git commit -m "サフィール人事考課システム v1"

git branch -M main
git remote add origin https://github.com/o-zy5656/safir-hyouka.git
git push -u origin main
```

> GitHub のユーザー名が `o-zy5656` でない場合は URL を読み替えてください。  
> push 時に GitHub ログイン（または Personal Access Token）を求められます。

### ステップ 3: Railway に API（デモ用）（15〜20分）

1. https://railway.app に GitHub でログイン
2. New Project → Deploy from GitHub → `safir-hyouka` を選択
3. 設定:
   - **Root Directory**: `backend`
4. Variables を追加（`backend/.env.demo.example` 参照）:
   - `DATABASE_URL` … Railway の PostgreSQL を Add すると自動付与
   - `SECRET_KEY` … 適当な長い文字列
   - `CORS_ORIGINS` … 後で Vercel URL を入れる（先に `http://localhost:5173` だけでも可）
   - `DEV_ALLOW_UNSUBMIT` … `true`
5. デプロイ後、公開 URL を控える（例: `https://safir-hyouka-production.up.railway.app`）
6. Railway Shell またはローカルから:
   ```bash
   python -m scripts.seed_demo
   ```
7. 確認: `https://＜Railway URL＞/api/health` → `{"status":"ok"}`

### ステップ 4: Vercel に画面（10分）

1. https://vercel.com に GitHub でログイン
2. Add New → Project → `safir-hyouka` を import
3. 設定:
   - **Root Directory**: `frontend`
   - Framework: Vite（自動検出）
   - Build: `npm run build`
   - Output: `dist`
4. Environment Variables:

   | 名前 | 値 |
   |------|-----|
   | `VITE_API_BASE` | Railway の URL（例: `https://xxx.up.railway.app`） |
   | `VITE_DEMO_MODE` | `true` |

5. Deploy
6. 表示された URL（例: `https://safir-hyouka.vercel.app`）を控える

### ステップ 5: CORS をつなぐ（5分）

Railway の Variables で `CORS_ORIGINS` を更新:

```
https://safir-hyouka.vercel.app,http://localhost:5173
```

（Vercel の実際の URL に置き換え）

### ステップ 6: 動作確認

1. Vercel の URL を開く
2. 画面上部に **「デモ環境 — 架空のサンプルデータです」** バナー
3. `E001` / `pass123` でログイン
4. 自己評価 → 評価者1/2 → 管理画面まで試す

### ステップ 7: 課題提出

- **提出 URL**: Vercel の URL
- **デモアカウント**: 本ドキュメント末尾の表
- **レポート**: 「公開はデモデータのみ、本番は社内サーバー」と記載

---

## デモ用ログイン（提出時に記載）

| ロール | 社員ID | パスワード |
|--------|--------|------------|
| 本人 | E001 | pass123 |
| 評価者1 | E010 | pass123 |
| 評価者2 | E020 | pass123 |
| 管理者 | ADMIN001 | admin123 |

---

## よくあるつまずき

| 症状 | 原因 | 対処 |
|------|------|------|
| Vercel でログインできない | API URL 未設定 | `VITE_API_BASE` を確認 |
| CORS エラー | Railway の CORS 未設定 | `CORS_ORIGINS` に Vercel URL |
| Railway で DB エラー | seed 未実行 | `python -m scripts.seed_demo` |
| push できない | GitHub 認証 | PAT または SSH キーを設定 |

---

## 関連ドキュメント

- [DEPLOY_VERCEL.md](./DEPLOY_VERCEL.md) — 詳細手順
- [UAT_CHECKLIST.md](./UAT_CHECKLIST.md) — 機能確認
- [DEPLOYMENT.md](./DEPLOYMENT.md) — 社内本番（課題とは別）

---

## 調査時点の技術メモ

- 親リポジトリ `My-First-Project` の remote: `o-zy5656/kaigo-dx-study`（API 上は非公開 or 不存在）
- `safir_hyouka` は **独立 Git リポジトリ化済み**（2025-06-25）
- 初回コミット済み。remote: `o-zy5656/safir-hyouka`（リポジトリ作成後に push）
- `gh` / `vercel` CLI は未インストール（ブラウザ操作で十分）

## ローカルで完了した作業（2025-06-25）

- [x] `git init` + 初回コミット（78 files）
- [x] `origin` → `https://github.com/o-zy5656/safir-hyouka.git`
- [x] Railway デモ自動 seed（`AUTO_SEED_DEMO`）
- [ ] GitHub リポジトリ作成 → **あなたの操作** → [`YOU_DO_THIS.md`](./YOU_DO_THIS.md)
- [ ] `git push`
- [ ] Vercel + Railway デプロイ
