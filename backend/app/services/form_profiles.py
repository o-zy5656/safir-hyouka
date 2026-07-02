"""評価フォーム種別（一般職員 / 施設長）の判定とテンプレート解決。"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session

from app.models import Employee, EvaluationPeriod, FormTemplate

FACILITY_DIRECTOR_TITLE = "施設長"

SELF_TEMPLATE_STANDARD = "self_evaluation_r8_summer.json"
SELF_TEMPLATE_DIRECTOR = "self_evaluation_r8_summer_facility_director.json"
ASSESSMENT_TEMPLATE_STANDARD = "assessment_r8_summer.json"
ASSESSMENT_TEMPLATE_DIRECTOR = "assessment_r8_summer_facility_director.json"


def is_facility_director(employee: Optional[Employee]) -> bool:
    return bool(employee and employee.job_title == FACILITY_DIRECTOR_TITLE)


def evaluation_skips_eval1(employee: Optional[Employee]) -> bool:
    """施設長は1次評価者がおらず、自己評価提出後に本部が直接考課する。"""
    return is_facility_director(employee)


def _load_file(templates_dir: str, filename: str) -> dict:
    from app.services.template_validator import load_template_file

    return load_template_file(Path(templates_dir) / filename)


def _from_period(
    db: Optional[Session],
    period: Optional[EvaluationPeriod],
    standard_attr: str,
    director_attr: str,
    standard_file: str,
    director_file: str,
    templates_dir: str,
    for_director: bool,
) -> dict:
    if period and db:
        tpl_id = getattr(period, director_attr if for_director else standard_attr, None)
        if tpl_id:
            tpl = db.get(FormTemplate, tpl_id)
            if tpl:
                return tpl.content
    filename = director_file if for_director else standard_file
    return _load_file(templates_dir, filename)


def resolve_self_template(
    db: Optional[Session],
    period: Optional[EvaluationPeriod],
    employee: Optional[Employee],
    templates_dir: str,
) -> dict:
    for_director = is_facility_director(employee)
    return _from_period(
        db,
        period,
        "self_eval_template_id",
        "facility_director_self_eval_template_id",
        SELF_TEMPLATE_STANDARD,
        SELF_TEMPLATE_DIRECTOR,
        templates_dir,
        for_director,
    )


def resolve_assessment_template(
    db: Optional[Session],
    period: Optional[EvaluationPeriod],
    employee: Optional[Employee],
    templates_dir: str,
) -> dict:
    for_director = is_facility_director(employee)
    return _from_period(
        db,
        period,
        "assessment_template_id",
        "facility_director_assessment_template_id",
        ASSESSMENT_TEMPLATE_STANDARD,
        ASSESSMENT_TEMPLATE_DIRECTOR,
        templates_dir,
        for_director,
    )


def user_needs_facility_director_self_eval(user, employee: Optional[Employee]) -> bool:
    from app.models import UserRole

    if not is_facility_director(employee):
        return False
    return user.role in {UserRole.EVALUATOR2, UserRole.EMPLOYEE}
