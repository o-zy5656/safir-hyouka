# Docker Desktop インストール手順（Mac）

## 費用

- **Personal（個人・小規模開発）**: 無料
- 今回の用途（自分の Mac で開発用 DB）は通常 **0円**

## 手順

### 1. ダウンロード

https://www.docker.com/products/docker-desktop/

「Download for Mac」をクリック。

| Mac の種類 | 選ぶもの |
|-----------|----------|
| M1 / M2 / M3 / M4（Appleシリコン） | Apple Chip |
| 古い Intel Mac | Intel Chip |

※ 不明な場合: メニュー → このMacについて → チップまたはプロセッサ で確認

### 2. インストール

1. ダウンロードした `Docker.dmg` を開く
2. Docker アイコンを **Applications** フォルダへドラッグ
3. Applications から **Docker** を起動
4. 初回は利用規約に同意、管理者パスワードを入力（求められた場合）
5. メニューバー（画面上部）に **クジラのアイコン** が出れば OK

### 3. PostgreSQL を起動

Docker が起動したら、ターミナルで:

```bash
cd /Users/kawamuraakihiko/Desktop/My-First-Project/safir_hyouka
./scripts/setup_postgres.sh
```

これで PostgreSQL が起動し、デモデータが入ります。

### 4. アプリを起動

```bash
# ターミナル1
cd backend && source .venv/bin/activate && uvicorn app.main:app --reload --app-dir .

# ターミナル2
cd frontend && npm run dev
```

http://localhost:5173 — ログイン: `E001` / `pass123`

## よくある質問

**Q. 使わないときは？**  
Docker Desktop を終了するとメモリを節約できます（クジラアイコン → Quit Docker Desktop）。  
DB データは消えません（次回起動で `docker compose start`）。

**Q. SQLite に戻せる？**  
`backend/.env` の `DATABASE_URL` を `sqlite:///./safir_hyouka.db` に戻せば OK。

**Q. データはどこに？**  
Docker の volume（`safir_hyouka_pgdata`）内。Mac 上の Docker 管理領域に保存されます。
