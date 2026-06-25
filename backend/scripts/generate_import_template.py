"""社員取込用 Excel テンプレートを生成する。

使い方:
  cd backend
  source .venv/bin/activate
  python -m scripts.generate_import_template
"""

from pathlib import Path

from openpyxl import Workbook

HEADERS = [
    "社員ID",
    "氏名",
    "配属",
    "職種",
    "勤続年数",
    "評価者1社員ID",
    "評価者2社員ID",
    "ロール",
]

SAMPLE_ROWS = [
    ["E001", "山田 太郎", "サフィール苑", "介護職", 5, "E010", "E020", "本人"],
    ["E010", "評価者 一郎", "本部", "管理職", 10, "E010", "E020", "評価者1"],
    ["E020", "評価者 二郎", "本部", "管理職", 12, "E010", "E020", "評価者2"],
]


def main():
    wb = Workbook()
    ws = wb.active
    ws.title = "社員一覧"
    ws.append(HEADERS)
    for row in SAMPLE_ROWS:
        ws.append(row)

    out_dir = Path(__file__).resolve().parents[2] / "docs"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "employee_import_template.xlsx"
    wb.save(out_path)
    print(f"テンプレートを作成しました: {out_path}")


if __name__ == "__main__":
    main()
