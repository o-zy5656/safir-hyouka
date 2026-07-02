"""本部（二次評価者）アカウントの確保。"""

from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from app.config import settings
from app.models import Employee, EmploymentStatus, Evaluation, EvaluationPeriod, SubmissionStatus, User, UserRole
from app.services.form_profiles import FACILITY_DIRECTOR_TITLE

HQ_ASSIGNMENT_LABEL = "本部"


def ensure_hq_evaluator(
    db: Session,
    password_hash_fn,
    default_password: str,
) -> Employee:
    """名簿にいない本部評価者用の職員・ユーザーを作成または更新する。"""
    employee_id = settings.hq_evaluator_employee_id.strip()
    if not employee_id:
        raise ValueError("HQ_EVALUATOR_EMPLOYEE_ID が未設定です")

    user = db.query(User).filter(User.employee_id == employee_id).first()
    if not user:
        user = User(
            employee_id=employee_id,
            password_hash=password_hash_fn(default_password),
            role=UserRole.EVALUATOR2,
            must_change_password=True,
            is_hq_evaluator=True,
        )
        db.add(user)
        db.flush()
    else:
        user.role = UserRole.EVALUATOR2
        user.is_hq_evaluator = True
        user.is_active = True

    employee = db.query(Employee).filter(Employee.employee_id == employee_id).first()
    if not employee:
        employee = Employee(
            employee_id=employee_id,
            name=settings.hq_evaluator_display_name,
            assignment=HQ_ASSIGNMENT_LABEL,
            job_type="管理職",
            job_title="本部",
            years_of_service=0,
            user_id=user.id,
        )
        db.add(employee)
        db.flush()
    else:
        employee.name = settings.hq_evaluator_display_name
        employee.assignment = HQ_ASSIGNMENT_LABEL
        employee.job_title = "本部"
        if not employee.user_id:
            employee.user_id = user.id

    db.flush()
    return employee


def get_hq_evaluator_employee(db: Session) -> Optional[Employee]:
    employee_id = settings.hq_evaluator_employee_id.strip()
    if not employee_id:
        return None
    return db.query(Employee).filter(Employee.employee_id == employee_id).first()


def hq_review_employees(db: Session, period: Optional[EvaluationPeriod]) -> list[Employee]:
    """施設長が二次評価を提出済みの一般職・リーダー（本部確認用）。"""
    if not period:
        return []

    director_ids = [
        row[0]
        for row in db.query(Employee.id)
        .filter(
            Employee.job_title == FACILITY_DIRECTOR_TITLE,
            Employee.employment_status == EmploymentStatus.ACTIVE,
        )
        .all()
    ]
    if not director_ids:
        return []

    return (
        db.query(Employee)
        .join(Evaluation, Evaluation.employee_id == Employee.id)
        .filter(
            Evaluation.period_id == period.id,
            Employee.employment_status == EmploymentStatus.ACTIVE,
            Employee.job_title != FACILITY_DIRECTOR_TITLE,
            Employee.evaluator2_id.in_(director_ids),
            Evaluation.eval2_status == SubmissionStatus.SUBMITTED,
        )
        .order_by(Employee.employee_id)
        .all()
    )
