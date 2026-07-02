"""指定社員IDのパスワードを初期値にリセットする（CLI）。"""

from __future__ import annotations

import argparse
import sys

from app.config import settings
from app.database import SessionLocal
from app.main import hash_password, migrate_schema
from app.models import User


def main() -> None:
    parser = argparse.ArgumentParser(description="職員パスワードを初期値にリセット")
    parser.add_argument("employee_id", help="社員ID（例: hq001）")
    parser.add_argument(
        "--password",
        default="",
        help="新しい仮パスワード（省略時は DEFAULT_EMPLOYEE_PASSWORD）",
    )
    args = parser.parse_args()

    employee_id = args.employee_id.strip()
    if not employee_id:
        print("社員IDを指定してください。", file=sys.stderr)
        sys.exit(1)

    new_password = args.password.strip() or settings.default_employee_password
    if len(new_password) < 8:
        print("パスワードは8文字以上にしてください。", file=sys.stderr)
        sys.exit(1)

    migrate_schema()
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.employee_id == employee_id).first()
        if not user:
            print(f"ユーザーが見つかりません: {employee_id}", file=sys.stderr)
            sys.exit(1)

        user.password_hash = hash_password(new_password)
        user.must_change_password = True
        user.is_active = True
        db.commit()
        print(f"{employee_id} のパスワードをリセットしました。")
        print(f"  仮パスワード: {new_password}")
        print("  次回ログイン時にパスワード変更が必要です。")
    finally:
        db.close()


if __name__ == "__main__":
    main()
