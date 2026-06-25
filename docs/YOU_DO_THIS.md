# あなたがやること（2ステップだけ）

こちらで **コードの整理・Git コミット・デプロイ設定** まで完了しました。  
GitHub / Vercel / Railway への **ログイン** だけ、ブラウザでお願いします。

---

## 済んだこと（自動で完了）

- [x] `safir_hyouka` を独立 Git リポジトリ化
- [x] 初回コミット（78ファイル）
- [x] Vercel 用 `vercel.json` / 環境変数サンプル
- [x] Railway 用 `Procfile` / `railway.toml`
- [x] デモデータ自動投入（`AUTO_SEED_DEMO=true`）
- [x] デモバナー表示（`VITE_DEMO_MODE=true`）
- [x] remote 設定: `https://github.com/o-zy5656/safir-hyouka.git`

---

## ステップ 1: GitHub にリポジトリを作る（2分）

1. 次のリンクを開く（名前は自動入力済み）:

   **https://github.com/new?name=safir-hyouka**

2. **Public** を選ぶ
3. **「Add a README file」は付けない**（空のリポジトリにする）
4. **Create repository** をクリック

---

## ステップ 2: push する（1分）

ターミナルで:

```bash
cd /Users/kawamuraakihiko/Desktop/My-First-Project/safir_hyouka
git push -u origin main
```

GitHub のログインを求められたら認証してください。

> push が成功したら、次のステップ（Vercel / Railway）に進めます。  
> 完了したら「push できた」と教えてください。Vercel / Railway の設定を案内します。

---

## ステップ 3以降: Vercel + Railway（push 成功後）

詳細は [`DEPLOY_VERCEL.md`](./DEPLOY_VERCEL.md) 参照。要点だけ:

### Railway（API・デモ DB）

1. https://railway.app → GitHub 連携
2. `safir-hyouka` → **Root Directory: `backend`**
3. PostgreSQL を Add
4. Variables:

   | 変数 | 値 |
   |------|-----|
   | `DATABASE_URL` | PostgreSQL から自動 |
   | `SECRET_KEY` | 適当な長い文字列 |
   | `AUTO_SEED_DEMO` | `true` |
   | `DEV_ALLOW_UNSUBMIT` | `true` |
   | `CORS_ORIGINS` | 後で Vercel URL を追加 |

5. 公開 URL を控える

### Vercel（画面）

1. https://vercel.com → Import `safir-hyouka`
2. **Root Directory: `frontend`**
3. Variables:

   | 変数 | 値 |
   |------|-----|
   | `VITE_API_BASE` | Railway の URL |
   | `VITE_DEMO_MODE` | `true` |

4. Deploy → 提出 URL 確定

---

## デモログイン（課題提出用）

| ロール | 社員ID | パスワード |
|--------|--------|------------|
| 本人 | E001 | pass123 |
| 評価者1 | E010 | pass123 |
| 評価者2 | E020 | pass123 |
| 管理者 | ADMIN001 | admin123 |

**実在の個人情報は Vercel に載せないでください。**
