"""事業所（施設）マスタ — 名簿・賞与表・評価者スコープの共通定義。"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

from app.config import settings
from app.models import Employee, User, UserRole
from app.services.form_profiles import FACILITY_DIRECTOR_TITLE, is_facility_director
from app.services.hq_evaluator import HQ_ASSIGNMENT_LABEL

_BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
DEFAULT_BONUS_FACILITY_KEY = "inaha"
FACILITY_DIRECTORS_BONUS_KEY = "facility_directors"
FACILITY_DIRECTORS_BONUS_LABEL = "施設長"


def is_facility_directors_bonus_key(facility_key: str) -> bool:
    return (facility_key or "").strip() == FACILITY_DIRECTORS_BONUS_KEY


def facility_directors_bonus_available() -> bool:
    return any(facility.bonus_enabled for facility in list_all_facilities())


def get_facility_directors_virtual_config() -> FacilityConfig:
    return FacilityConfig(
        key=FACILITY_DIRECTORS_BONUS_KEY,
        label=FACILITY_DIRECTORS_BONUS_LABEL,
        assignment_match="",
        enabled=True,
        bonus_data_sheet="__directors__",
        bonus_layout="inaha",
    )

# 賞与資料シートの列レイアウト（施設追加時は layout 名を facilities.json に指定）
BONUS_COLUMN_LAYOUTS: dict[str, dict[str, int]] = {
    "inaha": {
        "first_data_row": 4,
        "name_col": 2,
        "job_col": 3,
        "self_col": 4,
        "eval1_col": 5,
        "eval2_col": 6,
        "final_col": 7,
        "low_self_col": 8,
        "low_other_col": 9,
        "salary_raise_col": 10,
        "rank_order_col": 11,
        "rank_grade_col": 12,
        "note_col": 13,
    },
    "sohara": {
        "first_data_row": 4,
        "name_col": 2,
        "job_col": 4,
        "self_col": 5,
        "eval1_col": 6,
        "eval2_col": 7,
        "final_col": 8,
        "low_self_col": 9,
        "low_other_col": 10,
        "salary_raise_col": 11,
        "rank_order_col": 12,
        "rank_grade_col": 13,
        "note_col": 14,
    },
    "default": {
        "first_data_row": 4,
        "name_col": 2,
        "job_col": 3,
        "self_col": 4,
        "eval1_col": 5,
        "eval2_col": 6,
        "final_col": 7,
        "low_self_col": 8,
        "low_other_col": 9,
        "salary_raise_col": 10,
        "rank_order_col": 11,
        "rank_grade_col": 12,
        "note_col": 13,
    },
}


def user_has_global_facility_access(user: User) -> bool:
    """全施設のデータにアクセスできるユーザー（本部・システム管理者のみ）。"""
    return bool(user.is_hq_evaluator or user.role == UserRole.ADMIN)


@dataclass(frozen=True)
class FacilityConfig:
    key: str
    label: str
    assignment_match: str
    enabled: bool
    bonus_data_sheet: Optional[str] = None
    bonus_layout: str = "default"

    @property
    def bonus_enabled(self) -> bool:
        return self.enabled

    @property
    def bonus_sheet_keyword(self) -> str:
        text = self.assignment_match or self.label
        return text.replace("サフィール", "").strip()


def resolve_bonus_data_sheet(
    facility: FacilityConfig,
    sheet_names: list[str],
) -> Optional[str]:
    """Excel 内の資料シート名を解決（設定値 → 施設名キーワード一致）。"""
    configured = (facility.bonus_data_sheet or "").strip()
    if configured and configured in sheet_names:
        return configured

    keyword = facility.bonus_sheet_keyword
    if not keyword:
        return None

    matches = [name for name in sheet_names if keyword in name]
    if not matches:
        return None
    if len(matches) == 1:
        return matches[0]

    data_sheets = [name for name in matches if "資料" in name]
    if len(data_sheets) == 1:
        return data_sheets[0]
    return matches[0]


def _facilities_config_path() -> Path:
    configured = settings.facilities_config_path.strip()
    if configured:
        path = Path(configured)
        if not path.is_absolute():
            path = _BACKEND_DIR / path
        return path
    return _BACKEND_DIR / "data" / "facilities.json"


def _parse_facility(raw: dict[str, Any]) -> FacilityConfig:
    bonus = raw.get("bonus")
    bonus_sheet = None
    bonus_layout = "default"
    if isinstance(bonus, dict):
        raw_sheet = bonus.get("data_sheet")
        if raw_sheet not in (None, ""):
            bonus_sheet = str(raw_sheet)
        bonus_layout = str(bonus.get("layout") or "default").strip() or "default"
    return FacilityConfig(
        key=str(raw["key"]).strip(),
        label=str(raw["label"]).strip(),
        assignment_match=str(raw["assignment_match"]).strip(),
        enabled=bool(raw.get("enabled", True)),
        bonus_data_sheet=bonus_sheet,
        bonus_layout=bonus_layout,
    )


@lru_cache(maxsize=1)
def load_facility_configs() -> tuple[FacilityConfig, ...]:
    path = _facilities_config_path()
    if not path.exists():
        raise FileNotFoundError(f"施設マスタが見つかりません: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    facilities = data.get("facilities") or []
    if not facilities:
        raise ValueError("facilities.json に施設が定義されていません")
    return tuple(_parse_facility(item) for item in facilities)


def reload_facility_configs() -> None:
    load_facility_configs.cache_clear()


def list_all_facilities(*, include_disabled: bool = False) -> list[FacilityConfig]:
    configs = load_facility_configs()
    if include_disabled:
        return list(configs)
    return [facility for facility in configs if facility.enabled]


def get_facility(facility_key: str) -> FacilityConfig:
    if is_facility_directors_bonus_key(facility_key):
        return get_facility_directors_virtual_config()
    for facility in load_facility_configs():
        if facility.key == facility_key:
            return facility
    raise ValueError(f"未登録の施設キーです: {facility_key}")


def get_enabled_facility(facility_key: str) -> FacilityConfig:
    facility = get_facility(facility_key)
    if not facility.enabled:
        raise ValueError(f"無効な施設キーです: {facility_key}")
    return facility


def resolve_facility_for_assignment(assignment: str) -> Optional[FacilityConfig]:
    text = (assignment or "").strip()
    if not text or text == HQ_ASSIGNMENT_LABEL:
        return None
    matched: Optional[FacilityConfig] = None
    for facility in list_all_facilities():
        if facility.assignment_match and facility.assignment_match in text:
            if matched is None or len(facility.assignment_match) > len(matched.assignment_match):
                matched = facility
    return matched


def resolve_facility_key(employee: Optional[Employee]) -> Optional[str]:
    if not employee:
        return None
    facility = resolve_facility_for_assignment(employee.assignment)
    return facility.key if facility else None


def employee_belongs_to_facility(employee: Employee, facility_key: str) -> bool:
    facility = get_facility(facility_key)
    return bool(facility.assignment_match and facility.assignment_match in (employee.assignment or ""))


def employees_share_facility(left: Employee, right: Employee) -> bool:
    left_facility = resolve_facility_for_assignment(left.assignment)
    right_facility = resolve_facility_for_assignment(right.assignment)
    if not left_facility or not right_facility:
        return False
    return left_facility.key == right_facility.key


def is_hq_employee(employee: Employee) -> bool:
    return (employee.assignment or "").strip() == HQ_ASSIGNMENT_LABEL or employee.job_title == "本部"


def validate_evaluator_facility(
    employee: Employee,
    evaluator: Employee,
    *,
    role_label: str,
) -> Optional[str]:
    """評価者が被評価者と同一施設か検証（本部は除外）。"""
    if is_hq_employee(evaluator):
        return None
    if not employees_share_facility(employee, evaluator):
        emp_facility = resolve_facility_for_assignment(employee.assignment)
        ev_facility = resolve_facility_for_assignment(evaluator.assignment)
        emp_name = emp_facility.label if emp_facility else employee.assignment
        ev_name = ev_facility.label if ev_facility else evaluator.assignment
        return (
            f"{employee.employee_id} {employee.name}: {role_label} ({evaluator.employee_id}) は "
            f"別施設です（本人={emp_name} / 評価者={ev_name}）"
        )
    return None


def build_bonus_preset(facility_key: str, *, sheet_names: Optional[list[str]] = None) -> dict[str, Any]:
    if is_facility_directors_bonus_key(facility_key):
        raise ValueError("施設長ビューは個別施設の賞与シートを参照します")
    facility = get_enabled_facility(facility_key)
    layout_name = facility.bonus_layout if facility.bonus_layout in BONUS_COLUMN_LAYOUTS else "default"
    columns = dict(BONUS_COLUMN_LAYOUTS[layout_name])
    data_sheet: Optional[str] = None
    if sheet_names is not None:
        data_sheet = resolve_bonus_data_sheet(facility, sheet_names)
    elif facility.bonus_data_sheet:
        data_sheet = facility.bonus_data_sheet
    return {
        "label": facility.label,
        "data_sheet": data_sheet,
        "assignment_contains": facility.assignment_match,
        **columns,
    }


def list_facilities_for_user(user: User, employee: Optional[Employee]) -> list[FacilityConfig]:
    enabled = list_all_facilities()
    if user_has_global_facility_access(user):
        facilities = list(enabled)
        if facility_directors_bonus_available():
            facilities.append(get_facility_directors_virtual_config())
        return facilities
    if employee:
        own_key = resolve_facility_key(employee)
        if own_key:
            try:
                return [get_enabled_facility(own_key)]
            except ValueError:
                pass
    return []


def resolve_bonus_facility_key(
    user: User,
    employee: Optional[Employee],
    requested_key: str,
) -> str:
    """本部・システム管理者は任意施設、施設長は所属施設のみ。"""
    requested_key = (requested_key or "").strip()
    if user_has_global_facility_access(user):
        if not requested_key:
            requested_key = DEFAULT_BONUS_FACILITY_KEY
        if is_facility_directors_bonus_key(requested_key):
            if not facility_directors_bonus_available():
                raise ValueError("施設長ビューを利用できる賞与資料がありません")
            return requested_key
        get_enabled_facility(requested_key)
        return requested_key

    if not employee:
        raise ValueError("職員情報が見つかりません")

    if not is_facility_director(employee):
        raise ValueError("この施設のデータにはアクセスできません")

    own_key = resolve_facility_key(employee)
    if not own_key:
        raise ValueError("所属施設が特定できません")

    if requested_key and requested_key != own_key:
        raise ValueError("この施設のデータにはアクセスできません")

    get_enabled_facility(own_key)
    return own_key


def user_can_access_facility(user: User, employee: Optional[Employee], facility_key: str) -> bool:
    try:
        get_enabled_facility(facility_key)
    except ValueError:
        return False
    if user_has_global_facility_access(user):
        if is_facility_directors_bonus_key(facility_key):
            return facility_directors_bonus_available()
        return True
    if not employee or not is_facility_director(employee):
        return False
    return resolve_facility_key(employee) == facility_key


def facility_to_dict(facility: FacilityConfig) -> dict[str, Any]:
    bonus_enabled = facility.bonus_enabled
    if is_facility_directors_bonus_key(facility.key):
        bonus_enabled = facility_directors_bonus_available()
    return {
        "key": facility.key,
        "label": facility.label,
        "assignment_match": facility.assignment_match,
        "enabled": facility.enabled,
        "bonus_enabled": bonus_enabled,
    }
