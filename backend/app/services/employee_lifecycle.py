"""職員の入職・退職処理。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.config import settings
from app.models import (
    AuditLog,
    Employee,
    EmploymentStatus,
    Evaluation,
    EvaluationPeriod,
    User,
    UserRole,
)
from app.services.form_profiles import FACILITY_DIRECTOR_TITLE
from app.services.hq_evaluator import get_hq_evaluator_employee
from app.services.retirement_archive import (
    ArchiveFiles,
    build_retirement_archive_payload,
    save_retirement_archive,
)
from app.services.roster_import import _resolve_is_admin, _resolve_role


@dataclass
class EmployeeActionResult:
    employee_id: str
    name: str
    message: str
    archive_id: Optional[str] = None
    warnings: list[str] = field(default_factory=list)


def active_employees_query(db: Session):
    return db.query(Employee).filter(Employee.employment_status == EmploymentStatus.ACTIVE)


def _get_employee_by_business_id(db: Session, employee_id: str) -> Optional[Employee]:
    return db.query(Employee).filter(Employee.employee_id == employee_id).first()


def _apply_roles_for_employee(db: Session, employee: Employee) -> None:
    if not employee.user_id:
        return
    user = db.get(User, employee.user_id)
    if not user:
        return

    active_emps = (
        db.query(Employee)
        .filter(Employee.employment_status == EmploymentStatus.ACTIVE)
        .all()
    )
    eval1_refs = (
        {employee.employee_id}
        if any(e.evaluator1_id == employee.id for e in active_emps)
        else set()
    )
    eval2_refs = (
        {employee.employee_id}
        if any(e.evaluator2_id == employee.id for e in active_emps)
        else set()
    )

    user.role = _resolve_role(
        employee.employee_id,
        employee.job_title or "",
        eval1_refs,
        eval2_refs,
        settings.eval1_leader_title_set,
    )
    user.is_admin = _resolve_is_admin(
        employee.employee_id,
        employee.job_title or "",
        settings.admin_job_title_set,
        settings.admin_employee_id_set,
    )


def _ensure_period_evaluation(db: Session, employee: Employee, period: Optional[EvaluationPeriod]) -> bool:
    if not period:
        return False
    exists = (
        db.query(Evaluation)
        .filter(Evaluation.period_id == period.id, Evaluation.employee_id == employee.id)
        .first()
    )
    if exists:
        return False
    db.add(Evaluation(period_id=period.id, employee_id=employee.id))
    return True


def create_or_reactivate_employee(
    db: Session,
    *,
    employee_id: str,
    name: str,
    assignment: str,
    job_type: str,
    job_title: str,
    years_of_service: int,
    evaluator1_employee_id: Optional[str],
    evaluator2_employee_id: Optional[str],
    admin_user: User,
    password_hash_fn,
    default_password: str,
    active_period: Optional[EvaluationPeriod],
) -> EmployeeActionResult:
    employee_id = employee_id.strip()
    if not employee_id:
        raise ValueError("社員IDを入力してください")

    existing = _get_employee_by_business_id(db, employee_id)
    if existing and existing.employment_status == EmploymentStatus.ACTIVE:
        raise ValueError(f"社員ID {employee_id} は既に在籍中です")

    ev1 = _get_employee_by_business_id(db, evaluator1_employee_id) if evaluator1_employee_id else None
    ev2 = _get_employee_by_business_id(db, evaluator2_employee_id) if evaluator2_employee_id else None
    if evaluator1_employee_id and not ev1:
        raise ValueError(f"一次評価者 ({evaluator1_employee_id}) が見つかりません")
    if evaluator2_employee_id and not ev2:
        raise ValueError(f"二次評価者 ({evaluator2_employee_id}) が見つかりません")

    if job_title == FACILITY_DIRECTOR_TITLE:
        hq = get_hq_evaluator_employee(db)
        if hq:
            ev2 = hq
        ev1 = None

    if existing:
        employee = existing
        employee.name = name
        employee.assignment = assignment
        employee.job_type = job_type
        employee.job_title = job_title or "一般"
        employee.years_of_service = years_of_service
        employee.employment_status = EmploymentStatus.ACTIVE
        employee.retired_at = None
        if employee.user_id:
            user = db.get(User, employee.user_id)
            if user:
                user.is_active = True
        message = f"{name} さんを再入職として登録しました"
    else:
        user = db.query(User).filter(User.employee_id == employee_id).first()
        if not user:
            user = User(
                employee_id=employee_id,
                password_hash=password_hash_fn(default_password),
                role=UserRole.EMPLOYEE,
                must_change_password=True,
            )
            db.add(user)
            db.flush()
        else:
            user.is_active = True

        employee = Employee(
            employee_id=employee_id,
            name=name,
            assignment=assignment,
            job_type=job_type,
            job_title=job_title or "一般",
            years_of_service=years_of_service,
            user_id=user.id,
            employment_status=EmploymentStatus.ACTIVE,
        )
        db.add(employee)
        db.flush()
        message = f"{name} さんを入職登録しました（初期パスワードは管理者に確認してください）"

    employee.evaluator1_id = ev1.id if ev1 else None
    employee.evaluator2_id = ev2.id if ev2 else None

    if employee.user_id:
        user = db.get(User, employee.user_id)
        if user:
            user.is_active = True
    _apply_roles_for_employee(db, employee)
    _ensure_period_evaluation(db, employee, active_period)

    db.add(
        AuditLog(
            user_id=admin_user.id,
            action="create_employee",
            target_type="employee",
            target_id=employee.id,
            detail={"employee_id": employee_id, "name": name},
        )
    )
    db.flush()

    return EmployeeActionResult(employee_id=employee.employee_id, name=employee.name, message=message)


def retire_employee(
    db: Session,
    employee: Employee,
    admin_user: User,
    reason: Optional[str] = None,
) -> EmployeeActionResult:
    if employee.employment_status == EmploymentStatus.RETIRED:
        raise ValueError("既に退職済みです")
    if employee.employee_id == settings.hq_evaluator_employee_id:
        raise ValueError("本部評価者アカウントは退職処理できません")

    warnings: list[str] = []
    as_ev1 = (
        db.query(Employee)
        .filter(
            Employee.evaluator1_id == employee.id,
            Employee.employment_status == EmploymentStatus.ACTIVE,
        )
        .count()
    )
    as_ev2 = (
        db.query(Employee)
        .filter(
            Employee.evaluator2_id == employee.id,
            Employee.employment_status == EmploymentStatus.ACTIVE,
        )
        .count()
    )
    if as_ev1:
        warnings.append(f"一次評価者として担当中の在籍職員が {as_ev1} 名います。評価者の付け替えを検討してください。")
    if as_ev2:
        warnings.append(f"二次評価者として担当中の在籍職員が {as_ev2} 名います。評価者の付け替えを検討してください。")

    retired_at = datetime.utcnow()
    payload = build_retirement_archive_payload(db, employee, reason=reason)

    cleared_ev1 = (
        db.query(Employee)
        .filter(
            Employee.evaluator1_id == employee.id,
            Employee.employment_status == EmploymentStatus.ACTIVE,
        )
        .update({Employee.evaluator1_id: None}, synchronize_session=False)
    )
    cleared_ev2 = (
        db.query(Employee)
        .filter(
            Employee.evaluator2_id == employee.id,
            Employee.employment_status == EmploymentStatus.ACTIVE,
        )
        .update({Employee.evaluator2_id: None}, synchronize_session=False)
    )
    if cleared_ev1:
        warnings.append(f"一次評価者参照を {cleared_ev1} 名分クリアしました。")
    if cleared_ev2:
        warnings.append(f"二次評価者参照を {cleared_ev2} 名分クリアしました。")

    employee.employment_status = EmploymentStatus.RETIRED
    employee.retired_at = retired_at
    employee.evaluator1_id = None
    employee.evaluator2_id = None

    if employee.user_id:
        user = db.get(User, employee.user_id)
        if user:
            user.is_active = False

    db.flush()

    archive: ArchiveFiles = save_retirement_archive(
        settings.retired_archives_dir,
        employee,
        payload,
        retired_at=retired_at,
    )

    db.add(
        AuditLog(
            user_id=admin_user.id,
            action="retire_employee",
            target_type="employee",
            target_id=employee.id,
            detail={
                "employee_id": employee.employee_id,
                "archive_id": archive.archive_id,
                "reason": reason,
            },
        )
    )
    db.flush()

    return EmployeeActionResult(
        employee_id=employee.employee_id,
        name=employee.name,
        message=f"{employee.name} さんを退職処理しました。アーカイブを保存しました。",
        archive_id=archive.archive_id,
        warnings=warnings,
    )
