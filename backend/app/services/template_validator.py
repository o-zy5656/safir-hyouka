import json
from pathlib import Path
from typing import Any

from fastapi import HTTPException


REQUIRED_TEMPLATE_KEYS = {"id", "version", "title", "type", "items"}
REQUIRED_ITEM_KEYS = {"id", "label", "name", "element", "criteria"}
REQUIRED_CRITERIA_KEYS = {"score", "text"}


def validate_template(content: dict[str, Any]) -> list[str]:
    errors: list[str] = []

    for key in REQUIRED_TEMPLATE_KEYS:
        if key not in content:
            errors.append(f"必須項目 '{key}' がありません")

    if content.get("type") not in {"self_evaluation", "assessment"}:
        errors.append("type は self_evaluation または assessment である必要があります")

    items = content.get("items", [])
    if not isinstance(items, list) or len(items) == 0:
        errors.append("items は1件以上必要です")
        return errors

    for index, item in enumerate(items, start=1):
        for key in REQUIRED_ITEM_KEYS:
            if key not in item:
                errors.append(f"項目{index}: '{key}' がありません")
        criteria = item.get("criteria", [])
        if not isinstance(criteria, list) or len(criteria) == 0:
            errors.append(f"項目{index}: criteria が空です")
            continue
        for c_index, criterion in enumerate(criteria, start=1):
            for key in REQUIRED_CRITERIA_KEYS:
                if key not in criterion:
                    errors.append(f"項目{index} 基準{c_index}: '{key}' がありません")

    return errors


def load_template_file(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"テンプレートが見つかりません: {path.name}")
    with path.open(encoding="utf-8") as f:
        content = json.load(f)
    errors = validate_template(content)
    if errors:
        raise HTTPException(status_code=400, detail={"message": "テンプレート検証エラー", "errors": errors})
    return content
