"""開発・公開デモ用のサンプルデータ投入スクリプト。

使い方:
  cd backend
  source .venv/bin/activate
  python -m scripts.seed_demo
  python -m scripts.seed_demo --force   # 既存データを削除して再投入
"""

import sys
from datetime import datetime, timedelta
from typing import Optional

from app.config import settings
from app.database import Base, SessionLocal, engine
from app.main import hash_password, load_assessment_template, load_self_template
from app.models import (
    AuditLog,
    Employee,
    Evaluation,
    EvaluationPeriod,
    FormTemplate,
    PeriodSeason,
    PeriodStatus,
    SubmissionStatus,
    TemplateType,
    User,
    UserRole,
)
from app.services.bonus_amounts import save_bonus_amounts_store, save_workbook_row_fields
from app.services.hq_evaluator import ensure_hq_evaluator

DEMO_FISCAL_YEAR = 8
FACILITY_INAHA = "デモ施設いなは"
FACILITY_SOHARA = "デモ施設そはら"

DEMO_SELF_SCORES = {
    "item_01": 10,
    "item_02": 8,
    "item_03": 10,
    "item_04": 8,
    "item_05": 6,
    "item_06": 8,
    "item_07": 10,
    "item_08": 8,
    "item_09": 6,
    "item_10": 8,
}

DEMO_SELF_TEXT = {
    "philosophy": "利用者の尊厳を守り、笑顔あふれる生活を支える。",
    "slogan": "「つながり」を大切に、チームで支え合う。",
    "practice": "日々の声かけと記録の徹底を心がけ、利用者との信頼関係を築いている。",
}

INAHA_STAFF = [
    ("E101", "山田 太郎"),
    ("E102", "佐藤 花子"),
    ("E103", "鈴木 一郎"),
    ("E104", "田中 次郎"),
    ("E105", "高橋 美咲"),
    ("E106", "伊藤 健太"),
    ("E107", "渡辺 由美"),
    ("E108", "中村 翔"),
]

SOHARA_STAFF = [
    ("E201", "小林 直樹"),
    ("E202", "加藤 恵子"),
    ("E203", "吉田 大輔"),
    ("E204", "山本 真理"),
    ("E205", "松本 優"),
    ("E206", "井上 亮"),
]


def make_self_eval_data(scores: Optional[dict] = None) -> dict:
    return {
        "scores": scores or dict(DEMO_SELF_SCORES),
        "text_fields": dict(DEMO_SELF_TEXT),
    }


def make_eval1_data(partial: bool = False) -> dict:
    scores = dict(DEMO_SELF_SCORES)
    if partial:
        scores = {k: v for i, (k, v) in enumerate(scores.items()) if i < 5}
    return {
        "scores": scores,
        "text_fields": {
            "philosophy": DEMO_SELF_TEXT["philosophy"],
            "slogan": DEMO_SELF_TEXT["slogan"],
            "practice": DEMO_SELF_TEXT["practice"],
            "evaluator1_note": "日々の業務態度は良好。記録の正確性をさらに高めたい。",
        },
    }


def make_eval2_data() -> dict:
    return {
        "scores": dict(DEMO_SELF_SCORES),
        "text_fields": {
            **dict(DEMO_SELF_TEXT),
            "evaluator2_note": "総合的に良好。引き続きチームへの貢献を期待する。",
        },
    }


def _seed_bonus_stores() -> None:
    inaha_amount_rows = [
        {"employee_id": "E101", "proposed_bonus_amount": 520, "bonus_amount": 480, "prior_summer_amount": 400, "prior_winter_amount": 380},
        {"employee_id": "E102", "proposed_bonus_amount": 450, "bonus_amount": 420, "prior_summer_amount": 350, "prior_winter_amount": 340},
        {"employee_id": "E103", "proposed_bonus_amount": 500, "bonus_amount": 460, "prior_summer_amount": 390, "prior_winter_amount": 370},
        {"employee_id": "E104", "proposed_bonus_amount": 380, "bonus_amount": 360, "prior_summer_amount": 300, "prior_winter_amount": 290},
        {"employee_id": "E105", "proposed_bonus_amount": 560, "bonus_amount": 520, "prior_summer_amount": 420, "prior_winter_amount": 400},
        {"employee_id": "E106", "proposed_bonus_amount": 410, "bonus_amount": 390, "prior_summer_amount": 320, "prior_winter_amount": 310},
        {"employee_id": "E107", "proposed_bonus_amount": 430, "bonus_amount": 400, "prior_summer_amount": 330, "prior_winter_amount": 320},
        {"employee_id": "E108", "proposed_bonus_amount": 470, "bonus_amount": 440, "prior_summer_amount": 360, "prior_winter_amount": 350},
    ]
    sohara_amount_rows = [
        {"employee_id": "E201", "proposed_bonus_amount": 480, "bonus_amount": 450, "prior_summer_amount": 370, "prior_winter_amount": 360},
        {"employee_id": "E202", "proposed_bonus_amount": 420, "bonus_amount": 400, "prior_summer_amount": 330, "prior_winter_amount": 320},
        {"employee_id": "E203", "proposed_bonus_amount": 510, "bonus_amount": 470, "prior_summer_amount": 380, "prior_winter_amount": 370},
        {"employee_id": "E204", "proposed_bonus_amount": 390, "bonus_amount": 370, "prior_summer_amount": 310, "prior_winter_amount": 300},
        {"employee_id": "E205", "proposed_bonus_amount": 440, "bonus_amount": 410, "prior_summer_amount": 340, "prior_winter_amount": 330},
        {"employee_id": "E206", "proposed_bonus_amount": 460, "bonus_amount": 430, "prior_summer_amount": 350, "prior_winter_amount": 340},
    ]
    save_bonus_amounts_store(
        "inaha",
        DEMO_FISCAL_YEAR,
        rows=inaha_amount_rows,
        provision_monthly=1100,
        provision_months=6,
    )
    save_bonus_amounts_store(
        "sohara",
        DEMO_FISCAL_YEAR,
        rows=sohara_amount_rows,
        provision_monthly=800,
        provision_months=12,
    )

    workbook_rows = []
    for index, (employee_id, _) in enumerate(INAHA_STAFF, start=1):
        workbook_rows.append(
            {
                "employee_id": employee_id,
                "self_score": 78 + index,
                "eval1_score": 80 + index,
                "eval2_score": 79 + index,
                "rank_order": index,
                "rank_grade": "A" if index <= 2 else "B" if index <= 5 else "C",
                "note": f"デモ用特記 {index}",
            }
        )
    for index, (employee_id, _) in enumerate(SOHARA_STAFF, start=1):
        workbook_rows.append(
            {
                "employee_id": employee_id,
                "self_score": 76 + index,
                "eval1_score": 78 + index,
                "eval2_score": 77 + index,
                "rank_order": index,
                "rank_grade": "B" if index <= 3 else "C",
                "note": f"デモ用メモ {index}",
            }
        )
    save_workbook_row_fields("inaha", DEMO_FISCAL_YEAR, workbook_rows[: len(INAHA_STAFF)])
    save_workbook_row_fields("sohara", DEMO_FISCAL_YEAR, workbook_rows[len(INAHA_STAFF) :])


def seed(force: bool = False):
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    if db.query(User).first():
        if not force:
            print("既にデータがあります。スキップします。")
            print("再投入する場合: python -m scripts.seed_demo --force")
            return
        print("既存データを削除して再投入します...")
        db.query(AuditLog).delete()
        db.query(Evaluation).delete()
        db.query(Employee).delete()
        db.query(EvaluationPeriod).delete()
        db.query(FormTemplate).delete()
        db.query(User).delete()
        db.commit()

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
        name="令和8年度 夏季考課（デモ）",
        season=PeriodSeason.SUMMER,
        fiscal_year=DEMO_FISCAL_YEAR,
        self_eval_deadline=datetime.utcnow() + timedelta(days=14),
        eval1_deadline=datetime.utcnow() + timedelta(days=28),
        eval2_deadline=datetime.utcnow() + timedelta(days=42),
        self_eval_template_id=self_tpl.id,
        assessment_template_id=assess_tpl.id,
        status=PeriodStatus.ACTIVE,
    )
    db.add(period)

    def make_user(
        employee_id: str,
        role: UserRole,
        password: str,
        *,
        is_admin: bool = False,
        is_hq_evaluator: bool = False,
    ) -> User:
        user = User(
            employee_id=employee_id,
            password_hash=hash_password(password),
            role=role,
            must_change_password=False,
            is_admin=is_admin,
            is_hq_evaluator=is_hq_evaluator,
        )
        db.add(user)
        db.flush()
        return user

    make_user("ADMIN001", UserRole.ADMIN, "admin123", is_admin=True)
    ev1_user = make_user("E010", UserRole.EVALUATOR1, "pass123")
    ev2_user = make_user("E020", UserRole.EVALUATOR2, "pass123")

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
    db.add_all([ev1, ev2])
    db.flush()

    ensure_hq_evaluator(db, hash_password, settings.default_employee_password)
    hq_user = db.query(User).filter(User.employee_id == settings.hq_evaluator_employee_id).first()
    if hq_user:
        hq_user.must_change_password = False

    def add_employee(
        employee_id: str,
        name: str,
        assignment: str,
        *,
        job_title: str = "介護職員",
        job_type: str = "介護職",
        password: str = "pass123",
        evaluator1_id=None,
        evaluator2_id=None,
    ) -> Employee:
        user = make_user(employee_id, UserRole.EMPLOYEE, password)
        emp = Employee(
            employee_id=employee_id,
            name=name,
            assignment=assignment,
            job_type=job_type,
            job_title=job_title,
            years_of_service=5,
            evaluator1_id=evaluator1_id or ev1.id,
            evaluator2_id=evaluator2_id or ev2.id,
            user_id=user.id,
        )
        db.add(emp)
        db.flush()
        return emp

    now = datetime.utcnow()

    add_employee(
        "DIR001",
        "施設長 一郎",
        FACILITY_INAHA,
        job_title="施設長",
        job_type="管理職",
        password="pass123",
    )
    add_employee(
        "DIR002",
        "施設長 二郎",
        FACILITY_SOHARA,
        job_title="施設長",
        job_type="管理職",
        password="pass123",
    )

    def add_completed_evaluation(employee: Employee) -> None:
        db.add(
            Evaluation(
                period_id=period.id,
                employee_id=employee.id,
                self_eval_status=SubmissionStatus.SUBMITTED,
                self_eval_submitted_at=now - timedelta(days=8),
                self_eval_data=make_self_eval_data(),
                eval1_status=SubmissionStatus.SUBMITTED,
                eval1_submitted_at=now - timedelta(days=5),
                eval1_data=make_eval1_data(),
                eval2_status=SubmissionStatus.SUBMITTED,
                eval2_submitted_at=now - timedelta(days=2),
                eval2_data=make_eval2_data(),
            )
        )

    for index, (employee_id, name) in enumerate(INAHA_STAFF):
        employee = add_employee(employee_id, name, FACILITY_INAHA)
        if index < 6:
            add_completed_evaluation(employee)
        elif index == 6:
            db.add(
                Evaluation(
                    period_id=period.id,
                    employee_id=employee.id,
                    self_eval_status=SubmissionStatus.SUBMITTED,
                    self_eval_submitted_at=now - timedelta(days=3),
                    self_eval_data=make_self_eval_data(),
                    eval1_status=SubmissionStatus.DRAFT,
                    eval1_data=make_eval1_data(partial=True),
                )
            )
        else:
            db.add(
                Evaluation(
                    period_id=period.id,
                    employee_id=employee.id,
                    self_eval_status=SubmissionStatus.PENDING,
                )
            )

    for index, (employee_id, name) in enumerate(SOHARA_STAFF):
        employee = add_employee(employee_id, name, FACILITY_SOHARA)
        if index < 4:
            add_completed_evaluation(employee)
        else:
            db.add(
                Evaluation(
                    period_id=period.id,
                    employee_id=employee.id,
                    self_eval_status=SubmissionStatus.DRAFT,
                    self_eval_data=make_self_eval_data({"item_01": 9, "item_02": 8}),
                )
            )

    db.commit()
    _seed_bonus_stores()

    print("デモデータを投入しました（架空の氏名・2施設・賞与表サンプル付き）")
    print("  管理者（ゲストログイン）: ADMIN001")
    print("  施設長: DIR001（いなは）/ DIR002（そはら）")
    print("  職員: E101〜E108（いなは）/ E201〜E206（そはら）")
    print("  評価者1: E010 / 評価者2: E020 / 本部: hq001")


if __name__ == "__main__":
    seed(force="--force" in sys.argv)
