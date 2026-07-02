# 初心者向け：Vercel 公開までの完全ガイド

このガイドは、**プログラミングに不慣れでも**、順番どおりに進めれば  
「インターネット上にデモサイトを公開できる」ように書いています。

所要時間の目安：**40〜60分**（アカウント作成含む）

---

## 0. まず理解しておくこと（3分）

このシステムは **2か所** に分かれて公開します。

```
【あなたの PC】          【インターネット上】

  コード（GitHub）  ──→   Vercel … 画面（ブラウザで見る部分）
                    ──→   Railway … API（データのやり取り）
                              ↓
                         PostgreSQL … 仮名のデモデータだけ
```

| サービス | 役割 | 無料枠 |
|----------|------|--------|
| **GitHub** | コードを保管・共有 | あり |
| **Railway** | API（バックエンド）を動かす | あり（制限あり） |
| **Vercel** | 画面（フロントエンド）を配信 | あり |

**重要：** 公開するのは **架空のデモデータだけ** です。実在の氏名は載せません。

---

## 1. 事前準備（アカウント作成）

次の3つのアカウントを用意してください（すべて無料で始められます）。

1. **GitHub** … https://github.com/signup  
2. **Railway** … https://railway.app （「Login with GitHub」が簡単）  
3. **Vercel** … https://vercel.com/signup （「Continue with GitHub」が簡単）

> すでに GitHub リポジトリ `o-zy5656/safir-hyouka` がある場合は、  
> そのアカウントでログインしてください。

---

## 2. コードを GitHub に送る（push）

### 2-1. ターミナルを開く

Mac の場合：**ターミナル** アプリを開きます。

### 2-2. プロジェクトフォルダへ移動

次をコピーして Enter：

```bash
cd /Users/kawamuraakihiko/Desktop/My-First-Project/safir_hyouka
```

### 2-3. 個人情報が含まれていないか確認

次のコマンドで、`.env` が一覧に **出てこなければ OK** です：

```bash
git status
```

`backend/data/bonus_amounts/inaha.json` なども **出てこない** ことが望ましいです（gitignore 済み）。

### 2-4. 変更をコミットして push

```bash
git add .
git commit -m "公開デモ: 仮名データ・ログイン不要・賞与表ワークスペース"
git push origin main
```

**うまくいったとき：** エラーなく終わり、GitHub のページを更新するとファイルが増えています。

**ログインを求められたとき：** GitHub のユーザー名とパスワード（またはトークン）を入力します。

**push できたら** → ステップ 3 へ進んでください。

---

## 3. Railway に API をデプロイする

### 3-1. 新しいプロジェクトを作る

1. ブラウザで https://railway.app を開く  
2. 左上 **「New Project」** をクリック  
3. **「Deploy from GitHub repo」** を選ぶ  
4. 初回は **GitHub 連携** を許可する  
5. 一覧から **`safir-hyouka`**（または `o-zy5656/safir-hyouka`）を選ぶ  

### 3-2. バックエンド用に設定する

デプロイが始まったら：

1. サービス（四角いカード）をクリック  
2. **Settings** タブを開く  
3. **Root Directory** に `backend` と入力して保存  

これで「`backend` フォルダだけ」を API として動かします。

### 3-3. PostgreSQL（データベース）を追加

1. プロジェクト画面に戻る（左上のプロジェクト名）  
2. **「+ New」** → **「Database」** → **「Add PostgreSQL」**  
3. PostgreSQL のカードが増えます  

### 3-4. 環境変数（Variables）を設定する

**API のサービス**（PostgreSQL ではない方）をクリック → **Variables** タブ。

次を **1行ずつ** 追加します（Raw Editor が使えると楽です）。

| 変数名 | 値 | 説明 |
|--------|-----|------|
| `DATABASE_URL` | `${{Postgres.DATABASE_URL}}` | PostgreSQL と連携（Railway の参照変数） |
| `SECRET_KEY` | （下記コマンドで生成した文字列） | 認証用の秘密鍵 |
| `AUTO_SEED_DEMO` | `true` | 初回起動時にデモデータ投入 |
| `DEMO_MODE` | `true` | ログイン不要モード |
| `DEMO_GUEST_EMPLOYEE_ID` | `ADMIN001` | 自動ログインするデモ用ID |
| `FACILITIES_CONFIG_PATH` | `data/facilities.demo.json` | 仮名施設マスタ |
| `BONUS_WORKBOOK_TEMPLATE_PATH` | （空欄のまま） | デモでは Excel 不要 |
| `BONUS_NAME_ALIASES` | `{}` | 実名エイリアスを無効化 |
| `DEV_ALLOW_UNSUBMIT` | `true` | デモ用 |
| `DEFAULT_EMPLOYEE_PASSWORD` | `pass123` | デモ用（手動ログイン時） |
| `CORS_ORIGINS` | `http://localhost:5173` | いったんこれで OK（後で Vercel URL を追加） |

**SECRET_KEY の作り方（ターミナル）：**

```bash
openssl rand -hex 32
```

表示された長い文字列をコピーして `SECRET_KEY` に貼り付けます。

> **DATABASE_URL の補足：**  
> Railway では `${{Postgres.DATABASE_URL}}` と書くと、PostgreSQL の URL が自動で入ります。  
> サービス名が `Postgres` でない場合は、PostgreSQL カードの **Variables** にある  
> `DATABASE_URL` をコピーして、API 側の `DATABASE_URL` に貼っても構いません。

### 3-5. 公開 URL を取得する

1. API サービスの **Settings** → **Networking**  
2. **「Generate Domain」** をクリック  
3. 表示された URL をメモ（例：`https://safir-hyouka-production-xxxx.up.railway.app`）  

これが **API の住所** です。末尾に `/` は付けません。

### 3-6. 動くか確認する

ターミナルで（`YOUR-API-URL` を自分の URL に置き換え）：

```bash
curl https://YOUR-API-URL.up.railway.app/api/health
```

`{"status":"ok"}` と返れば成功です。

もう一つ：

```bash
curl -X POST https://YOUR-API-URL.up.railway.app/api/auth/demo-login
```

`access_token` が返れば、デモログインも OK です。

**エラーが出るとき：** Railway の **Deployments** → 最新のログ（Logs）を開き、赤いエラーを確認してください。  
よくある原因は `DATABASE_URL` 未設定・`SECRET_KEY` 未設定です。

**データが空のとき：** Railway の API サービス → **Shell** で：

```bash
python -m scripts.seed_demo --force
```

---

## 4. Vercel に画面をデプロイする

### 4-1. プロジェクトをインポート

1. https://vercel.com/dashboard を開く  
2. **「Add New…」** → **「Project」**  
3. **Import** の一覧から **`safir-hyouka`** を選ぶ  

### 4-2. ビルド設定

| 項目 | 値 |
|------|-----|
| Framework Preset | Vite（自動検出されればそのまま） |
| **Root Directory** | `frontend` に変更（Edit を押す） |
| Build Command | `npm run build`（デフォルトのまま） |
| Output Directory | `dist`（デフォルトのまま） |

### 4-3. 環境変数

**Environment Variables** で次を追加：

| 名前 | 値 |
|------|-----|
| `VITE_API_BASE` | ステップ 3-5 でメモした Railway の URL（例：`https://xxxx.up.railway.app`） |
| `VITE_DEMO_MODE` | `true` |

> `VITE_API_BASE` に `/api` は **付けない** でください。

### 4-4. Deploy を押す

1〜3分待つと **Congratulations** と表示されます。

表示された URL（例：`https://safir-hyouka.vercel.app`）が **提出用の公開 URL** です。

---

## 5. Railway と Vercel をつなぐ（CORS 設定）

Vercel の URL が決まったら、もう一度 Railway に戻ります。

1. API サービス → **Variables**  
2. `CORS_ORIGINS` を次のように **書き換え**（自分の Vercel URL に置き換え）：

```
https://safir-hyouka.vercel.app,http://localhost:5173
```

3. 保存すると自動で再デプロイされます  

---

## 6. 最終確認（公開成功のチェック）

ブラウザで **Vercel の URL** を開いてください。

| 確認項目 | 期待する結果 |
|----------|----------------|
| 画面上部 | 黄色い **「デモ環境」** バナーが表示される |
| ログイン画面 | **出ない**（自動で入る） |
| 最初の画面 | **賞与表** が表示される |
| 施設名 | **デモ施設いなは** など仮名 |
| 氏名 | **山田 太郎** など架空の名前 |

課題提出用 URL として、この **Vercel の URL** を提出してください。

---

## 7. 課題レポートに書く例（コピペ可）

> 本システムは Vercel（画面）と Railway（API・DB）の二層構成で公開した。  
> 人事データには個人情報が含まれるため、公開環境には架空のデモデータのみを配置し、  
> `DEMO_MODE` により ID・パスワードなしで機能を閲覧できるようにした。  
> 実運用は社内 LAN のみとし、公開デモと本番でデータを分離している。

---

## 8. よくあるトラブル

### 「デモ用 API に接続できません」と表示される

- Vercel の `VITE_API_BASE` が Railway の URL と一致しているか  
- Railway の API が起動しているか（`/api/health` を curl で確認）  
- 環境変数を変えたあと、Vercel で **Redeploy** したか  

### ブラウザの開発者ツールに CORS エラー

- Railway の `CORS_ORIGINS` に **Vercel の URL 全体** が入っているか（`https://` から）  
- 保存後、1〜2分待ってからブラウザを再読み込み  

### 賞与表が空・エラーになる

- Railway Shell で `python -m scripts.seed_demo --force`  
- `DEMO_MODE=true` と `FACILITIES_CONFIG_PATH=data/facilities.demo.json` を確認  

### Railway のビルドが失敗する

- Root Directory が `backend` か確認  
- Logs に `ModuleNotFoundError` があれば `requirements.txt` が読まれているか確認  

### Vercel のビルドが失敗する

- Root Directory が `frontend` か確認  

---

## 9. 作業の流れ（一覧）

```
[ ] GitHub に push
[ ] Railway: プロジェクト作成 + Root Directory = backend
[ ] Railway: PostgreSQL 追加
[ ] Railway: 環境変数 11個 設定
[ ] Railway: 公開 URL 取得 + /api/health 確認
[ ] Vercel: Root Directory = frontend
[ ] Vercel: VITE_API_BASE + VITE_DEMO_MODE 設定
[ ] Vercel: Deploy → URL 取得
[ ] Railway: CORS_ORIGINS に Vercel URL 追加
[ ] ブラウザで動作確認
```

---

## 10. 困ったとき

ステップ番号と、画面に表示されているエラーメッセージをメモして質問してください。  
例：「ステップ 6 で『デモ用 API に接続できません』と出ます」

関連ドキュメント：

- [`PRE_DEPLOY_VERCEL.md`](./PRE_DEPLOY_VERCEL.md) — 技術者向けチェックリスト  
- [`DEPLOY_VERCEL.md`](./DEPLOY_VERCEL.md) — 設計の説明  
