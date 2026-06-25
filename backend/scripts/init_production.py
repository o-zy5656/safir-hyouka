"""本番環境の初回セットアップ（テーブル作成・テンプレート登録・管理者アカウント）。

使い方:
  cd backend
  source .venv/bin/activate
  export ADMIN_EMPLOYEE_ID=ADMIN001
  export ADMIN_PASSWORD='強力なパスワード'
  python -m scripts.init_production

※ デモ用の seed_demo は本番では実行しないでください。
"""

import os
import sys

from app.database import Base, SessionLocal, engine
from app.main import hash_password, load_assessment_template, load_self_template
from app.models import FormTemplate, TemplateType, User, UserRole


def main():
    admin_id = os.environ.get("ADMIN_EMPLOYEE_ID", "").strip()
    admin_password = os.environ.get("ADMIN_PASSWORD", "").strip()
    if not admin_id or not admin_password:
        print("環境変数 ADMIN_EMPLOYEE_ID と ADMIN_PASSWORD を設定してください。", file=sys.stderr)
        sys.exit(1)
    if len(admin_password) < 8:
        print("ADMIN_PASSWORD は 8 文字以上にしてください。", file=sys.stderr)
        sys.exit(1)

    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    existing_admin = db.query(User).filter(User.role == UserRole.ADMIN).first()
    if existing_admin:
        print(f"管理者は既に存在します: {existing_admin.employee_id}")
        print("追加の管理者が必要な場合は DB または管理手順で作成してください。")
        return

    if not db.query(FormTemplate).first():
        db.add_all(
            [
                FormTemplate(
                    type=TemplateType.SELF_EVALUATION,
                    version=load_self_template().get("version", "1.0.0"),
                    name=load_self_template().get("title", "自己評価表"),
                    content=load_self_template(),
                ),
                FormTemplate(
                    type=TemplateType.ASSESSMENT,
                    version=load_assessment_template().get("version", "1.0.0"),
                    name=load_assessment_template().get("title", "考課表"),
                    content=load_assessment_template(),
                ),
            ]
        )
        db.flush()
        print("評価表テンプレートを登録しました。")

    admin = User(
        employee_id=admin_id,
        password_hash=hash_password(admin_password),
        role=UserRole.ADMIN,
        must_change_password=False,
    )
    db.add(admin)
    db.commit()
    print("本番初期化が完了しました。")
    print(f"  管理者ログイン: {admin_id}")
    print("  次の作業:")
    print("    1. 管理画面で考課期間を作成・開始")
    print("    2. 社員 Excel を取込")
    print("    3. 評価者アカウントのロール設定（必要に応じて DB で evaluator1/2 に変更）")


if __name__ == "__main__":
    main()
