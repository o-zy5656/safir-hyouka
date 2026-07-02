"""考課結果を賞与 Excel テンプレートへ反映する CLI。

使い方:
  cd backend
  export BONUS_WORKBOOK_TEMPLATE_PATH='/path/to/【秀成会】R7.夏季賞与(確定）.xlsx'
  python -m scripts.reflect_bonus_workbook
  python -m scripts.reflect_bonus_workbook --dry-run
  python -m scripts.reflect_bonus_workbook --output /tmp/bonus_reflect.xlsx
"""

from __future__ import annotations

import argparse
from pathlib import Path

from app.config import settings
from app.database import SessionLocal
from app.models import EvaluationPeriod, PeriodStatus
from app.services.facilities import list_all_facilities
from app.services.bonus_workbook import reflect_evaluations_to_bonus_workbook


def main() -> None:
    facility_keys = [facility.key for facility in list_all_facilities() if facility.bonus_enabled]
    parser = argparse.ArgumentParser(description="賞与 Excel へ考課結果を反映")
    parser.add_argument("--facility", default=facility_keys[0] if facility_keys else "sohara", choices=facility_keys or None)
    parser.add_argument("--dry-run", action="store_true", help="書き込みせず照合結果のみ表示")
    parser.add_argument("--output", type=Path, help="出力先（省略時はテンプレート名_考課反映.xlsx）")
    args = parser.parse_args()

    if not settings.bonus_workbook_template_path.strip():
        raise SystemExit("BONUS_WORKBOOK_TEMPLATE_PATH が未設定です")

    db = SessionLocal()
    try:
        period = db.query(EvaluationPeriod).filter(EvaluationPeriod.status == PeriodStatus.ACTIVE).first()
        if not period:
            raise SystemExit("実施中の考課期間がありません")

        data, result = reflect_evaluations_to_bonus_workbook(
            db,
            period,
            facility_key=args.facility,
            dry_run=args.dry_run,
        )
    finally:
        db.close()

    print(f"施設: {result.facility}")
    print(f"反映行数: {result.updated_rows}")
    if result.matched_employees:
        print("反映:", ", ".join(result.matched_employees))
    if result.unmatched_employees:
        print("未照合（DB）:", ", ".join(result.unmatched_employees))
    if result.unmatched_excel_names:
        print("未使用（Excel）:", ", ".join(result.unmatched_excel_names))
    for warning in result.warnings:
        print("警告:", warning)

    if args.dry_run:
        return

    template_path = Path(settings.bonus_workbook_template_path.strip())
    output = args.output or template_path.with_name(f"{template_path.stem}_考課反映.xlsx")
    output.write_bytes(data or b"")
    print(f"出力: {output}")


if __name__ == "__main__":
    main()
