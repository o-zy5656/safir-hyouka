"""本番・テストサーバー投入前の設定チェック。

使い方:
  cd backend && source .venv/bin/activate
  python -m scripts.preflight_production
"""

from __future__ import annotations

import sys
from pathlib import Path

from app.config import settings

WEAK_SECRETS = {"dev-secret-key", "change-me-in-production", "change-me"}
WEAK_PASSWORDS = {"changeme123", "password", "12345678"}


def main() -> int:
    errors: list[str] = []
    warnings: list[str] = []

    if settings.database_url.startswith("sqlite"):
        errors.append("DATABASE_URL は PostgreSQL を指定してください（SQLite は本番非推奨）")

    if settings.dev_allow_unsubmit:
        errors.append("DEV_ALLOW_UNSUBMIT=false にしてください")

    if settings.secret_key.strip() in WEAK_SECRETS:
        errors.append("SECRET_KEY を openssl rand -hex 32 などで変更してください")

    if settings.default_employee_password.strip() in WEAK_PASSWORDS:
        warnings.append(
            "DEFAULT_EMPLOYEE_PASSWORD が初期値のままです。取込前に変更することを推奨します"
        )

    if not settings.production_mode:
        warnings.append("PRODUCTION_MODE=true を設定すると起動時に設定漏れを検出できます")

    templates_dir = Path(settings.templates_dir)
    if not templates_dir.is_dir():
        errors.append(f"テンプレートディレクトリが見つかりません: {templates_dir}")
    else:
        required = [
            "self_evaluation_r8_summer.json",
            "assessment_r8_summer.json",
            "self_evaluation_r8_summer_facility_director.json",
            "assessment_r8_summer_facility_director.json",
        ]
        missing = [name for name in required if not (templates_dir / name).exists()]
        if missing:
            errors.append(f"テンプレート JSON が不足: {', '.join(missing)}")

    archives_dir = Path(settings.retired_archives_dir)
    try:
        archives_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        errors.append(f"退職アーカイブ保存先を作成できません: {archives_dir} ({exc})")

    if settings.production_mode:
        try:
            settings.validate_runtime()
        except RuntimeError as exc:
            errors.append(str(exc))

    print("=== 本番前チェック ===")
    if warnings:
        print("\n[警告]")
        for msg in warnings:
            print(f"  ! {msg}")
    if errors:
        print("\n[要修正]")
        for msg in errors:
            print(f"  x {msg}")
        print(f"\n結果: NG ({len(errors)} 件)")
        return 1

    print("\n結果: OK")
    if warnings:
        print(f"（警告 {len(warnings)} 件 — 可能なら解消してください）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
