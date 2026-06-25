"""開発用のサンプルデータ投入スクリプト。

使い方:
  cd backend
  source .venv/bin/activate
  python -m scripts.seed_demo
"""

from datetime import datetime, timedelta

from app.database import Base, SessionLocal, engine
from app.main import hash_password, load_assessment_template, load_self_template
from app.models import (
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


def seed():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    if db.query(User).first():
        print("既にデータがあります。スキップします。")
        return

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
    db.add_all([self_tpl, assess_tpl])
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
        status=PeriodStatus.ACTIVE,
    )
    db.add(period)

    def make_user(employee_id: str, role: UserRole, password: str) -> User:
        user = User(
            employee_id=employee_id,
            password_hash=hash_password(password),
            role=role,
        )
        db.add(user)
        db.flush()
        return user

    admin = make_user("ADMIN001", UserRole.ADMIN, "admin123")
    ev1_user = make_user("E010", UserRole.EVALUATOR1, "pass123")
    ev2_user = make_user("E020", UserRole.EVALUATOR2, "pass123")
    emp_user = make_user("E001", UserRole.EMPLOYEE, "pass123")

    ev1 = Employee(
        employee_id="E010",
        name="評価者 一郎",
        assignment="本部",
        job_type="管理職",
        years_of_service=10,
        user_id=ev1_user.id,
    )
    ev2 = Employee(
        employee_id="E020",
        name="評価者 二郎",
        assignment="本部",
        job_type="管理職",
        years_of_service=12,
        user_id=ev2_user.id,
    )
    emp = Employee(
        employee_id="E001",
        name="山田 太郎",
        assignment="サフィール苑",
        job_type="介護職",
        years_of_service=5,
        evaluator1_id=None,
        evaluator2_id=None,
        user_id=emp_user.id,
    )
    db.add_all([ev1, ev2, emp])
    db.flush()

    emp.evaluator1_id = ev1.id
    emp.evaluator2_id = ev2.id

    evaluation = Evaluation(period_id=period.id, employee_id=emp.id)
    db.add(evaluation)

    db.commit()
    print("デモデータを投入しました")
    print("  本人: E001 / pass123")
    print("  評価者1: E010 / pass123")
    print("  評価者2: E020 / pass123")
    print("  管理者: ADMIN001 / admin123")


if __name__ == "__main__":
    seed()
