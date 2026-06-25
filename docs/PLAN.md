# サフィール人事考課システム — 設計プラン（v1）

## 1. システム概要

| 項目 | 内容 |
|------|------|
| 目的 | 本人・評価者（最大2名）の考課入力を3ペインワークスペースで効率化 |
| 規模 | 200〜300名 |
| 配置 | 事業所内サーバー（オンプレ）、社内LAN |
| 技術 | Python FastAPI + React + PostgreSQL |
| AI | 不使用 |

## 2. 考課フロー

```
本人（自己評価提出・ロック）
  ↓
評価者1（自己評価参照しながら考課提出・ロック）
  ↓
評価者2（自己評価＋評1参照。評1確定後に入力可 → 提出・ロック）
```

- 提出後は即ロック。修正は人事・経営層が差し戻し。
- 考課期間: 年2回（夏季・冬季）。期間開始時にテンプレート版を固定。

## 3. 画面構成（3ペイン）

### 本人用

```
┌─────────────┬──────────────────────┬─────────────┐
│ 左: 属性     │ 中: 自己評価フォーム    │ 右: 提出状況  │
│ ・配属       │ 10項目×4段階採点       │ ・期限       │
│ ・職種       │ 理念・スローガン       │ ・提出ボタン  │
│ ・氏名       │ 実践内容・達成度コメント │ ・提出済み表示 │
│ ・勤続年数   │                      │ ・差し戻し通知 │
└─────────────┴──────────────────────┴─────────────┘
```

### 評価者1・2共通

```
┌─────────────┬──────────────────────┬─────────────┐
│ 左: 一覧     │ 中: 考課入力フォーム   │ 右: 参照     │
│ ・担当者一覧  │ 10項目×4段階採点       │ ・自己評価   │
│ ・進捗状態   │ 特記事項              │ ・評1（評2のみ）│
│ ・選択者属性  │ （自分の列のみ編集可）   │ ・提出・期限  │
└─────────────┴──────────────────────┴─────────────┘
```

### 管理画面（人事・経営層）

- 考課期間の作成・開始
- 社員Excel一括取込
- テンプレートアップロード・プレビュー・次期反映予約
- 差し戻し
- Excel出力（一覧＋個人明細）

## 4. DB設計

### users（ログインアカウント）

| カラム | 型 | 説明 |
|--------|-----|------|
| id | UUID PK | |
| employee_id | VARCHAR UNIQUE | 社員ID（ログイン用） |
| password_hash | VARCHAR | |
| role | ENUM | employee / evaluator1 / evaluator2 / admin |
| is_active | BOOLEAN | |
| must_change_password | BOOLEAN | 初回ログイン時 |

### employees（社員マスタ）

| カラム | 型 | 説明 |
|--------|-----|------|
| id | UUID PK | |
| employee_id | VARCHAR UNIQUE | 社員ID |
| name | VARCHAR | 氏名 |
| assignment | VARCHAR | 配属 |
| job_type | VARCHAR | 職種 |
| years_of_service | INTEGER | 勤続年数 |
| evaluator1_id | UUID FK → employees | 第1評価者 |
| evaluator2_id | UUID FK → employees | 第2評価者 |
| user_id | UUID FK → users | ログイン紐づけ |

### evaluation_periods（考課期間）

| カラム | 型 | 説明 |
|--------|-----|------|
| id | UUID PK | |
| name | VARCHAR | 例: 令和8年度 夏季考課 |
| season | ENUM | summer / winter |
| fiscal_year | INTEGER | 例: 8（令和） |
| self_eval_deadline | TIMESTAMP | 本人提出期限 |
| eval1_deadline | TIMESTAMP | 評価者1提出期限 |
| eval2_deadline | TIMESTAMP | 評価者2提出期限 |
| self_eval_template_id | UUID FK | 固定テンプレート |
| assessment_template_id | UUID FK | 固定テンプレート |
| status | ENUM | draft / active / closed |

### form_templates（評価表テンプレート）

| カラム | 型 | 説明 |
|--------|-----|------|
| id | UUID PK | |
| type | ENUM | self_evaluation / assessment |
| version | VARCHAR | 例: 1.0.0 |
| name | VARCHAR | 表示名 |
| content | JSONB | テンプレート本体 |
| effective_from_period_id | UUID | 適用開始期間（NULL=次回から） |
| created_at | TIMESTAMP | |

### evaluations（考課レコード — 1人×1期間）

| カラム | 型 | 説明 |
|--------|-----|------|
| id | UUID PK | |
| period_id | UUID FK | |
| employee_id | UUID FK | 被評価者 |
| self_eval_status | ENUM | draft / submitted / returned |
| eval1_status | ENUM | pending / draft / submitted / returned |
| eval2_status | ENUM | pending / draft / submitted / returned |
| self_eval_data | JSONB | 採点・自由記述 |
| eval1_data | JSONB | |
| eval2_data | JSONB | |
| self_eval_submitted_at | TIMESTAMP | |
| eval1_submitted_at | TIMESTAMP | |
| eval2_submitted_at | TIMESTAMP | |

### audit_logs（監査ログ）

| カラム | 型 | 説明 |
|--------|-----|------|
| id | UUID PK | |
| user_id | UUID | |
| action | VARCHAR | submit / return / import 等 |
| target_type | VARCHAR | |
| target_id | UUID | |
| detail | JSONB | |
| created_at | TIMESTAMP | |

## 5. API一覧（v1）

### 認証

| Method | Path | 説明 |
|--------|------|------|
| POST | /api/auth/login | 社員ID + パスワード |
| POST | /api/auth/change-password | 初回パスワード変更 |
| GET | /api/auth/me | ログインユーザー情報 |

### 本人

| Method | Path | 説明 |
|--------|------|------|
| GET | /api/me/workspace | 属性・期間・提出状況 |
| GET | /api/me/self-evaluation | 自己評価データ取得 |
| PUT | /api/me/self-evaluation | 下書き保存 |
| POST | /api/me/self-evaluation/submit | 提出 |

### 評価者

| Method | Path | 説明 |
|--------|------|------|
| GET | /api/evaluator/assignments | 担当者一覧＋進捗 |
| GET | /api/evaluator/assignments/{id} | 詳細（属性・参照・考課データ） |
| PUT | /api/evaluator/assignments/{id} | 下書き保存 |
| POST | /api/evaluator/assignments/{id}/submit | 提出 |

### 管理

| Method | Path | 説明 |
|--------|------|------|
| GET | /api/admin/periods | 考課期間一覧 |
| POST | /api/admin/periods | 期間作成 |
| POST | /api/admin/periods/{id}/activate | 期間開始 |
| POST | /api/admin/employees/import | Excel一括取込 |
| GET | /api/admin/templates | テンプレート一覧 |
| POST | /api/admin/templates | アップロード＋検証 |
| POST | /api/admin/templates/{id}/schedule | 次期適用予約 |
| POST | /api/admin/evaluations/{id}/return | 差し戻し |
| GET | /api/admin/periods/{id}/export | Excel出力 |

### テンプレート（参照）

| Method | Path | 説明 |
|--------|------|------|
| GET | /api/templates/self-evaluation | 現行自己評価テンプレート |
| GET | /api/templates/assessment | 現行考課テンプレート |

## 6. テンプレートJSON構造

`backend/templates/` に配置。管理画面から差し替え時も同一スキーマ。

- `self_evaluation_*.json` — 本人用（自己採点列 + 自由記述）
- `assessment_*.json` — 考課用（評価者1・2列 + 特記事項）

詳細は `backend/templates/` 内のファイルを参照。

## 7. v1 / v2 境界

### v1（今回）

- 上記API・3ペインUIのコア
- JSONテンプレート（ファイル配置 + 簡易管理API）
- 社員Excel取込（決めた列形式）
- 考課期間（夏季/冬季）
- Excel出力

### v2以降

- テンプレート管理画面の本格化
- 非エンジニア向け手順書（スクショ付き）
- 期限リマインド通知
- スマホ対応（提出確認のみ）
- Word/PDF帳票出力

## 8. 社員Excel取込フォーマット

| 列 | 必須 | 例 |
|----|------|-----|
| 社員ID | ○ | E001 |
| 氏名 | ○ | 山田太郎 |
| 配属 | ○ | サフィール〇〇 |
| 職種 | ○ | 介護職 |
| 勤続年数 | ○ | 5 |
| 評価者1社員ID | ○ | E010 |
| 評価者2社員ID | | E020 |
| ロール | | 本人 / 評価者1 / 評価者2（任意。省略時は評価者IDから自動判定） |

## 9. ディレクトリ構成

```
safir_hyouka/
├── docs/PLAN.md
├── backend/
│   ├── app/
│   ├── templates/
│   └── requirements.txt
├── frontend/
│   └── src/
└── README.md
```
