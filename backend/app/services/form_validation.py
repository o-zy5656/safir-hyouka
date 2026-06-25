from typing import Any, Optional


def validate_form_data(
    template: dict[str, Any],
    form_data: dict[str, Any],
    role: Optional[str] = None,
) -> list[str]:
    errors: list[str] = []
    scores = form_data.get("scores") or {}
    text_fields = form_data.get("text_fields") or {}

    for item in template.get("items", []):
        item_id = item["id"]
        label = item.get("label", "")
        name = item.get("name", "")
        display = f"{label} {name}".strip()
        score = scores.get(item_id)
        if score is None or score == "":
            errors.append(f"「{display}」の採点が未入力です")

    for field in template.get("text_fields", []):
        if field.get("readonly"):
            continue
        field_role = field.get("role")
        if field_role and role and field_role != role:
            continue
        if field_role and not role:
            continue
        value = text_fields.get(field["id"], "")
        if not str(value).strip():
            errors.append(f"「{field['label']}」が未入力です")

    return errors
