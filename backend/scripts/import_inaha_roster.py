"""サフィールいなはの名簿 Excel を取込。

使い方:
  cd backend
  source .venv/bin/activate
  python -m scripts.import_inaha_roster
  python -m scripts.import_inaha_roster --force
"""

import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

from app.config import settings
from app.database import Base, SessionLocal, engine
from app.main import (
    hash_password,
    load_assessment_template,
    load_facility_director_assessment_template,
    load_facility_director_self_template,
    load_self_template,
    migrate_schema,
)
from app.models import (
    AuditLog,
    Employee,
    Evaluation,
    EvaluationPeriod,
    FormTemplate,
    PeriodSeason,
    PeriodStatus,
    TemplateType,
    User,
    UserRole,
)
from app.services.roster_import import import_roster_from_excel

DEFAULT_ROSTER = Path(
    os.environ.get(
        "ROSTER_XLSX_PATH",
        "/Users/kawamuraakihiko/Library/CloudStorage/Dropbox/safir_tool/人事考課/名簿.xlsx",
    )
)


def clear_all(db):
    db.query(AuditLog).delete()
    db.query(Evaluation).delete()
    db.query(Employee).delete()
    db.query(EvaluationPeriod).delete()
    db.query(FormTemplate).delete()
    db.query(User).delete()
    db.commit()


def ensure_active_period(db):
    period = (
        db.query(EvaluationPeriod)
        .filter(EvaluationPeriod.status == PeriodStatus.ACTIVE)
        .first()
    )
    if period:
        return period

    self_tpl = FormTemplate(
        type=TemplateType.SELF_EVALUATION,
        version="1.0.0",
        name="令和8年度 夏季自己評価表",
        content=load_self_template(),
    )
    assess_tpl = FormTemplate(
        type=TemplateType.ASSESSMENT,
        version="1.0.0",
        name="令和8年度 夏季考課表",
        content=load_assessment_template(),
    )
    director_self_tpl = FormTemplate(
        type=TemplateType.SELF_EVALUATION,
        version="1.0.0",
        name="令和8年度 夏季自己評価表（施設長用）",
        content=load_facility_director_self_template(),
    )
    director_assess_tpl = FormTemplate(
        type=TemplateType.ASSESSMENT,
        version="1.0.0",
        name="令和8年度 夏季考課表（施設長用）",
        content=load_facility_director_assessment_template(),
    )
    db.add_all([self_tpl, assess_tpl, director_self_tpl, director_assess_tpl])
    db.flush()

    period = EvaluationPeriod(
        name="令和8年度 夏季考課",
        season=PeriodSeason.SUMMER,
        fiscal_year=8,
        self_eval_deadline=datetime.utcnow() + timedelta(days=14),
        eval1_deadline=datetime.utcnow() + timedelta(days=28),
        eval2_deadline=datetime.utcnow() + timedelta(days=42),
        self_eval_template_id=self_tpl.id,
        assessment_template_id=assess_tpl.id,
        facility_director_self_eval_template_id=director_self_tpl.id,
        facility_director_assessment_template_id=director_assess_tpl.id,
        status=PeriodStatus.ACTIVE,
    )
    db.add(period)
    db.commit()
    return period


def main():
    force = "--force" in sys.argv
    paths = [a for a in sys.argv[1:] if not a.startswith("--")]
    roster_path = Path(paths[0]) if paths else DEFAULT_ROSTER

    if not roster_path.exists():
        print(f"名簿が見つかりません: {roster_path}", file=sys.stderr)
        sys.exit(1)

    Base.metadata.create_all(bind=engine)
    migrate_schema()
    db = SessionLocal()

    if force and db.query(User).first():
        print("既存データを削除します...")
        clear_all(db)

    period = ensure_active_period(db)
    content = roster_path.read_bytes()
    result = import_roster_from_excel(
        db=db,
        content=content,
        admin_user=None,
        password_hash_fn=hash_password,
        default_password=settings.default_employee_password,
        active_period=period,
        facility_filter=settings.default_facility_filter,
        admin_job_titles=settings.admin_job_title_set,
        admin_employee_ids=settings.admin_employee_id_set,
        leader_titles=settings.eval1_leader_title_set,
    )

    print(f"取込完了: {settings.default_facility_filter}")
    print(f"  新規 {result.created} / 更新 {result.updated} / ユーザー作成 {result.users_created}")
    print(f"  ロール更新 {result.roles_updated} / 考課データ {result.evaluations_created}")
    if result.errors:
        print(f"  警告 {len(result.errors)}件（先頭5件）:")
        for msg in result.errors[:5]:
            print(f"    - {msg}")

    print()
    print("=== ログイン情報（初期パスワード共通）===")
    print(f"  パスワード: {settings.default_employee_password}")
    print()
    admins = (
        db.query(User)
        .filter((User.is_admin == True) | (User.role == UserRole.ADMIN))  # noqa: E712
        .all()
    )
    print("【管理者画面】職員ID（施設長など）:")
    for u in admins:
        emp = db.query(Employee).filter(Employee.user_id == u.id).first()
        title = emp.job_title if emp else ""
        role_note = u.role.value
        print(f"  {u.employee_id}  {emp.name if emp else ''}（{title} / {role_note}）")

    ev2 = db.query(User).filter(User.role == UserRole.EVALUATOR2, User.is_hq_evaluator == False).all()  # noqa: E712
    print("\n【評価者2（施設長）】:")
    for u in ev2:
        emp = db.query(Employee).filter(Employee.user_id == u.id).first()
        print(f"  {u.employee_id}  {emp.name if emp else ''}（{emp.job_title if emp else ''}）")

    hq = db.query(User).filter(User.is_hq_evaluator == True).all()  # noqa: E712
    print("\n【本部（施設長の二次評価者）】:")
    for u in hq:
        emp = db.query(Employee).filter(Employee.user_id == u.id).first()
        print(f"  {u.employee_id}  {emp.name if emp else ''}")

    ev1 = db.query(User).filter(User.role == UserRole.EVALUATOR1).all()
    print("\n【評価者1（リーダークラス等）】:")
    for u in ev1:
        emp = db.query(Employee).filter(Employee.user_id == u.id).first()
        print(f"  {u.employee_id}  {emp.name if emp else ''}")

    emp_sample = db.query(User).filter(User.role == UserRole.EMPLOYEE).limit(3).all()
    print("\n【本人】例:")
    for u in emp_sample:
        emp = db.query(Employee).filter(Employee.user_id == u.id).first()
        print(f"  {u.employee_id}  {emp.name if emp else ''}")


if __name__ == "__main__":
    main()
