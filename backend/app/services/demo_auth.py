"""公開デモ用の役割切り替え。"""

from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from app.config import settings
from app.models import Employee, User

# employee_id（大文字）→ デモ UI 表示ラベル
DEMO_PERSONA_LABELS: dict[str, str] = {
    "ADMIN001": "管理者",
    "DIR001": "施設長",
    "E010": "リーダー",
    "E101": "一般",
}


def _normalized_demo_persona_labels() -> dict[str, str]:
    labels = dict(DEMO_PERSONA_LABELS)
    hq_id = settings.hq_evaluator_employee_id.strip()
    if hq_id:
        labels[hq_id.upper()] = "本部"
    return labels


def demo_switchable_employee_ids() -> list[str]:
    raw = settings.demo_switchable_employee_ids.strip()
    if raw:
        return [item.strip() for item in raw.split(",") if item.strip()]
    labels = _normalized_demo_persona_labels()
    hq_id = settings.hq_evaluator_employee_id.strip()
    ordered = ["ADMIN001"]
    if hq_id:
        ordered.append(hq_id)
    ordered.extend(["DIR001", "E010", "E101"])
    return [item for item in ordered if item.upper() in labels or item == hq_id]


def demo_persona_label(employee_id: str) -> str:
    labels = _normalized_demo_persona_labels()
    return labels.get(employee_id.strip().upper(), employee_id.strip())


def resolve_demo_login_employee_id(requested: Optional[str]) -> str:
    target = (requested or settings.demo_guest_employee_id).strip()
    if not target:
        raise ValueError("デモ用アカウント ID が未設定です")

    allowed = demo_switchable_employee_ids()
    allowed_map = {item.upper(): item for item in allowed}
    canonical = allowed_map.get(target.upper())
    if not canonical:
        raise ValueError("指定したデモ役割には切り替えできません")
    return canonical


def find_demo_user(db: Session, employee_id: str) -> Optional[User]:
    user = db.query(User).filter(User.employee_id == employee_id).first()
    if user:
        return user
    return db.query(User).filter(User.employee_id.ilike(employee_id)).first()


def list_demo_personas(db: Session) -> list[dict[str, str]]:
    personas: list[dict[str, str]] = []
    for employee_id in demo_switchable_employee_ids():
        user = find_demo_user(db, employee_id)
        if not user or not user.is_active:
            continue
        employee = db.query(Employee).filter(Employee.user_id == user.id).first()
        personas.append(
            {
                "employee_id": user.employee_id,
                "label": demo_persona_label(user.employee_id),
                "name": employee.name if employee else None,
            }
        )
    return personas
