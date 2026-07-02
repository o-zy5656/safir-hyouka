"""原本_考課表.doc から評価者用考課表 JSON を生成。

使い方:
  cd backend
  python -m scripts.convert_assessment_template_from_doc
  python -m scripts.convert_assessment_template_from_doc /path/to/原本_考課表.doc
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

from app.database import SessionLocal
from app.main import migrate_schema
from app.models import EvaluationPeriod, FormTemplate, PeriodStatus
from app.services.template_validator import validate_template

DEFAULT_DOC = Path(
    "/Users/kawamuraakihiko/Library/CloudStorage/Dropbox/サフィール関係/"
    "河村、太田共有/自己評価シート/原本_考課表.doc"
)
OUTPUT = Path(__file__).resolve().parent.parent / "templates" / "assessment_r8_summer.json"

LABELS = ["①", "②", "③", "④", "⑤", "⑥", "⑦", "⑧", "⑨", "⑩"]
NAME_OVERRIDES = {
    "③": "協調（チーム力）",
    "④": "責任感",
    "⑤": "積極性",
    "⑥": "報告、連絡、相談",
}


def extract_text(doc_path: Path) -> str:
    return subprocess.check_output(
        ["textutil", "-convert", "txt", "-stdout", str(doc_path)],
        text=True,
    )


def normalize_name(raw: str, label: str) -> str:
    if label in NAME_OVERRIDES:
        return NAME_OVERRIDES[label]
    return re.sub(r"\s+", "", raw)


def parse_items(text: str) -> list[dict]:
    lines = [ln.strip() for ln in text.splitlines()]
    start = next(i for i, ln in enumerate(lines) if ln == "①")
    chunk = lines[start:]
    items: list[dict] = []
    idx = 0

    for n, label in enumerate(LABELS):
        if chunk[idx] != label:
            raise ValueError(f"項目 {label} の解析に失敗しました（位置 {idx}）")
        idx += 1

        raw_name = chunk[idx]
        idx += 1
        if label == "③" and idx < len(chunk) and chunk[idx] == "チーム力":
            idx += 1

        element_parts: list[str] = []
        while idx < len(chunk) and not chunk[idx].startswith("・"):
            token = chunk[idx]
            if token in LABELS or token == "合計":
                break
            element_parts.append(token)
            idx += 1

        element = " ".join(p for p in element_parts if p)
        criteria = []
        for score in [10, 8, 6, 4]:
            if not chunk[idx].startswith("・"):
                raise ValueError(f"項目 {label} の評価基準 {score} が見つかりません")
            crit_text = chunk[idx][1:].strip()
            idx += 1
            while idx < len(chunk) and (
                chunk[idx] in {"", "点", str(score), "10", "8", "6", "4"}
                or re.fullmatch(r"\d+", chunk[idx] or "")
            ):
                idx += 1
            criteria.append({"score": score, "text": crit_text})

        items.append(
            {
                "id": f"item_{n + 1:02d}",
                "label": label,
                "name": normalize_name(raw_name, label),
                "element": element,
                "criteria": criteria,
            }
        )

    return items


def build_template(items: list[dict]) -> dict:
    return {
        "id": "assessment_r8_summer",
        "version": "2.0.0",
        "title": "令和8年度 夏季考課表",
        "type": "assessment",
        "instructions": "各項目の評価基準から、一番あてはまる段階を選択してください。",
        "header_fields": [
            {"id": "assignment", "label": "配属"},
            {"id": "job_type", "label": "職種"},
            {"id": "name", "label": "氏名", "readonly": True},
        ],
        "items": items,
        "sections": [
            {
                "id": "total",
                "type": "computed_total",
                "label": "合計",
                "columns": ["evaluator1", "evaluator2"],
            }
        ],
        "text_fields": [
            {
                "id": "philosophy",
                "label": "理念",
                "instruction": "サフィールの理念及び今年度のスローガンを記入してください（一語一句間違えず、正確に記入してください）",
                "multiline": True,
                "readonly": True,
                "copy_from": "self_evaluation",
            },
            {
                "id": "slogan",
                "label": "スローガン",
                "multiline": True,
                "readonly": True,
                "copy_from": "self_evaluation",
            },
            {
                "id": "practice",
                "label": "実践内容",
                "instruction": "あなたは、この理念とスローガンを前向きに捉えどのように実践しているか記入をしてください。",
                "multiline": True,
                "readonly": True,
                "copy_from": "self_evaluation",
            },
            {
                "id": "goal_comment",
                "label": "達成度・振り返り",
                "instruction": "今年度目標の達成度について、また、今年度特に頑張った事や反省点についてコメントして下さい。",
                "multiline": True,
                "readonly": True,
                "copy_from": "self_evaluation",
            },
            {
                "id": "evaluator1_note",
                "label": "第一評価者による特記事項",
                "instruction": "本人の理念・スローガン・実践内容について、評価者としての所見を記入してください。",
                "role": "evaluator1",
                "multiline": True,
            },
            {
                "id": "evaluator2_note",
                "label": "第二評価者による特記事項",
                "instruction": "本人の理念・スローガン・実践内容について、評価者としての所見を記入してください。",
                "role": "evaluator2",
                "multiline": True,
            },
        ],
        "scoring": {
            "columns": [
                {
                    "id": "evaluator1",
                    "label": "第１評価者",
                    "role": "evaluator1",
                    "allowed_scores": [10, 8, 6, 4],
                },
                {
                    "id": "evaluator2",
                    "label": "第２評価者",
                    "role": "evaluator2",
                    "allowed_scores": [10, 8, 6, 4],
                },
            ]
        },
    }


def sync_active_period(db, content: dict) -> int:
    period = db.query(EvaluationPeriod).filter(EvaluationPeriod.status == PeriodStatus.ACTIVE).first()
    if not period or not period.assessment_template_id:
        return 0
    row = db.get(FormTemplate, period.assessment_template_id)
    if not row:
        return 0
    row.content = content
    row.version = content["version"]
    row.name = content["title"]
    db.commit()
    return 1


def main() -> None:
    doc_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_DOC
    if not doc_path.exists():
        print(f"ファイルが見つかりません: {doc_path}", file=sys.stderr)
        sys.exit(1)

    items = parse_items(extract_text(doc_path))
    template = build_template(items)
    errors = validate_template(template)
    if errors:
        print("検証エラー:", errors, file=sys.stderr)
        sys.exit(1)

    OUTPUT.write_text(json.dumps(template, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUTPUT.name} ({len(items)} items)")

    migrate_schema()
    db = SessionLocal()
    if sync_active_period(db, template):
        print("active period assessment template updated in DB")


if __name__ == "__main__":
    main()
