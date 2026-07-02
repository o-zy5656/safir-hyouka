# あなたがやること — 公開まで（初心者向け）

**まずこちらを開いてください（画面の順番どおりに進められます）：**

## 👉 [`GUIDE_PUBLISH_BEGINNER.md`](./GUIDE_PUBLISH_BEGINNER.md)

所要時間の目安：40〜60分

---

## 超短縮版（何をするかだけ）

| 順番 | どこで | 何をする |
|------|--------|----------|
| 1 | ターミナル | コードを GitHub に `push` |
| 2 | Railway | API（`backend`）+ PostgreSQL をデプロイ |
| 3 | Vercel | 画面（`frontend`）をデプロイ |
| 4 | Railway | Vercel の URL を `CORS_ORIGINS` に追加 |
| 5 | ブラウザ | Vercel の URL を開いて確認 |

**公開 URL は Vercel のアドレスです。**  
ログインは不要（デモモードで自動入室）です。

---

## すでに GitHub リポジトリはあります

```
https://github.com/o-zy5656/safir-hyouka
```

`git push origin main` で最新コードを送ってから、Railway / Vercel で「Import」してください。

---

## 困ったら

[`GUIDE_PUBLISH_BEGINNER.md`](./GUIDE_PUBLISH_BEGINNER.md) の **セクション 8（よくあるトラブル）** を見るか、  
「ステップ ○ で ○○ というエラー」と教えてください。
