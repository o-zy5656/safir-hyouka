from datetime import datetime, timedelta
from io import BytesIO
from pathlib import Path
from typing import Annotated, List, Optional
from urllib.parse import quote
from uuid import UUID

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.config import settings
from app.database import Base, engine, get_db
from app.models import (
    AuditLog,
    Employee,
    EmploymentStatus,
    Evaluation,
    EvaluationPeriod,
    FormTemplate,
    PeriodStatus,
    SubmissionStatus,
    TemplateType,
    User,
    UserRole,
)
from app.schemas import (
    AdminEvaluationItem,
    AdminUserItem,
    AssignmentSummary,
    BonusReflectResultResponse,
    BonusWorkbookResponse,
    BonusWorkbookRow,
    BonusAmountsSaveRequest,
    BonusAmountsSaveResponse,
    BonusWorkbookSaveRequest,
    BonusWorkbookSummary,
    ChangePasswordRequest,
    CreateEmployeeRequest,
    DemoLoginRequest,
    DemoPersonaItem,
    DemoPersonasResponse,
    EmployeeActionResponse,
    EmployeeAttributes,
    EmployeeListItem,
    EmployeeOptionsResponse,
    EvaluatorWorkspaceResponse,
    FacilitiesListResponse,
    FacilityItem,
    ImportResultResponse,
    LoginRequest,
    PeriodCreateRequest,
    PeriodResponse,
    ResetPasswordResponse,
    RetireEmployeeRequest,
    RetiredArchiveItem,
    ReturnRequest,
    SaveFormRequest,
    SubmissionPanel,
    TokenResponse,
    UpdateUserRoleRequest,
    UserResponse,
    WorkspaceResponse,
)
from app.services.bonus_amounts import (
    compute_bonus_summary,
    default_fiscal_year,
    list_bonus_fiscal_years,
    load_bonus_amounts_store,
    merge_amounts_into_rows,
    save_amounts_for_workbook,
)
from app.services.bonus_workbook import (
    export_bonus_workbook_bytes,
    load_bonus_workbook_rows,
    reflect_evaluations_to_bonus_workbook,
    save_bonus_workbook_rows,
    sync_roster_to_bonus_workbook,
    user_can_access_bonus_workbook,
)
from app.services.demo_auth import (
    find_demo_user,
    list_demo_personas,
    resolve_demo_login_employee_id,
)
from app.services.employee_import import import_employees_from_excel
from app.services.employee_lifecycle import (
    active_employees_query,
    create_or_reactivate_employee,
    retire_employee,
)
from app.services.employee_options import employee_options_dict
from app.services.excel_export import build_period_export
from app.services.form_validation import validate_form_data
from app.services.form_profiles import (
    evaluation_skips_eval1,
    is_facility_director,
    resolve_assessment_template,
    resolve_self_template,
    user_needs_facility_director_self_eval,
)
from app.services.hq_evaluator import hq_review_employees
from app.services.facilities import (
    facility_to_dict,
    get_enabled_facility,
    is_facility_directors_bonus_key,
    list_facilities_for_user,
    resolve_bonus_facility_key,
    resolve_facility_for_assignment,
    user_has_global_facility_access,
)
from app.services.roster_import import import_roster_from_excel
from app.services.retirement_archive import list_retirement_archives, resolve_archive_path
from app.services.template_validator import load_template_file

app = FastAPI(title="サフィール人事考課 API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

TEMPLATES_DIR = settings.templates_dir


def create_tables():
    Base.metadata.create_all(bind=engine)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def create_access_token(user_id: str) -> str:
    expire = datetime.utcnow() + timedelta(minutes=settings.access_token_expire_minutes)
    return jwt.encode({"sub": user_id, "exp": expire}, settings.secret_key, algorithm="HS256")


def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: Annotated[Session, Depends(get_db)],
) -> User:
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=["HS256"])
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="認証に失敗しました")
    except JWTError as exc:
        raise HTTPException(status_code=401, detail="認証に失敗しました") from exc

    user = db.get(User, UUID(user_id))
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="ユーザーが無効です")
    return user


def require_admin(user: Annotated[User, Depends(get_current_user)]) -> User:
    if user.role != UserRole.ADMIN and not user.is_admin:
        raise HTTPException(status_code=403, detail="管理者のみアクセスできます")
    return user


def require_password_manager(user: Annotated[User, Depends(get_current_user)]) -> User:
    if user.role != UserRole.ADMIN and not user.is_admin and not user.is_hq_evaluator:
        raise HTTPException(status_code=403, detail="パスワードリセット権限がありません")
    return user


def user_can_reset_passwords(user: User) -> bool:
    return bool(user.role == UserRole.ADMIN or user.is_admin or user.is_hq_evaluator)


def require_bonus_workbook_access(
    user: Annotated[User, Depends(get_current_user)],
    db: Session = Depends(get_db),
) -> User:
    employee = db.query(Employee).filter(Employee.user_id == user.id).first()
    if not user_can_access_bonus_workbook(user, employee):
        raise HTTPException(status_code=403, detail="賞与表は施設長と本部のみアクセスできます")
    return user


def _bonus_actor(db: Session, user: User) -> tuple[User, Optional[Employee]]:
    employee = db.query(Employee).filter(Employee.user_id == user.id).first()
    return user, employee


def _require_facility_access(
    facility_key: str,
    user: User,
    employee: Optional[Employee],
) -> str:
    try:
        return resolve_bonus_facility_key(user, employee, facility_key)
    except ValueError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


def _bonus_workbook_template_configured() -> bool:
    return bool(settings.bonus_workbook_template_path.strip())


def _bonus_workbook_api_enabled() -> bool:
    return _bonus_workbook_template_configured() or settings.demo_mode


def _resolve_bonus_fiscal_year(
    db: Session,
    fiscal_year: Optional[int] = None,
) -> tuple[int, int, bool]:
    period = get_active_period(db)
    current = period.fiscal_year if period else default_fiscal_year()
    target = int(fiscal_year) if fiscal_year is not None else current
    read_only = target != current
    return target, current, read_only


def _bonus_fiscal_years_for_facility(facility_key: str, target_year: int) -> list[int]:
    years = list_bonus_fiscal_years(facility_key)
    if target_year not in years:
        years = sorted(set(years + [target_year]), reverse=True)
    return years


def employee_attrs(employee: Employee) -> EmployeeAttributes:
    return EmployeeAttributes(
        employee_id=employee.employee_id,
        name=employee.name,
        assignment=employee.assignment,
        job_type=employee.job_type,
        job_title=employee.job_title,
        years_of_service=employee.years_of_service,
    )


def migrate_schema():
    from sqlalchemy import inspect, text

    insp = inspect(engine)
    dialect = engine.dialect.name
    uuid_type = "UUID" if dialect == "postgresql" else "CHAR(36)"

    if "employees" not in insp.get_table_names():
        return
    cols = {c["name"] for c in insp.get_columns("employees")}
    if "job_title" not in cols:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE employees ADD COLUMN job_title VARCHAR(100)"))
    if "employment_status" not in cols:
        with engine.begin() as conn:
            conn.execute(
                text("ALTER TABLE employees ADD COLUMN employment_status VARCHAR(20) DEFAULT 'active'")
            )
            conn.execute(text("UPDATE employees SET employment_status = 'active' WHERE employment_status IS NULL"))
    if "retired_at" not in cols:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE employees ADD COLUMN retired_at TIMESTAMP"))
    if "users" in insp.get_table_names():
        user_cols = {c["name"] for c in insp.get_columns("users")}
        if "is_admin" not in user_cols:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE users ADD COLUMN is_admin BOOLEAN DEFAULT FALSE"))
        if "is_hq_evaluator" not in user_cols:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE users ADD COLUMN is_hq_evaluator BOOLEAN DEFAULT FALSE"))
    if "evaluation_periods" in insp.get_table_names():
        period_cols = {c["name"]: c for c in insp.get_columns("evaluation_periods")}
        for col_name in (
            "facility_director_self_eval_template_id",
            "facility_director_assessment_template_id",
        ):
            if col_name not in period_cols:
                with engine.begin() as conn:
                    conn.execute(
                        text(
                            f"ALTER TABLE evaluation_periods ADD COLUMN {col_name} {uuid_type}"
                        )
                    )
            elif dialect == "postgresql":
                col_type = str(period_cols[col_name]["type"]).lower()
                if "char" in col_type:
                    with engine.begin() as conn:
                        conn.execute(
                            text(
                                f"ALTER TABLE evaluation_periods "
                                f"ALTER COLUMN {col_name} TYPE UUID "
                                f"USING NULLIF({col_name}::text, '')::uuid"
                            )
                        )
    if "evaluations" in insp.get_table_names():
        indexes = {idx["name"] for idx in insp.get_indexes("evaluations")}
        if "uq_evaluation_period_employee" not in indexes:
            with engine.begin() as conn:
                conn.execute(
                    text(
                        "CREATE UNIQUE INDEX IF NOT EXISTS uq_evaluation_period_employee "
                        "ON evaluations (period_id, employee_id)"
                    )
                )


def get_active_period(db: Session) -> Optional[EvaluationPeriod]:
    return db.query(EvaluationPeriod).filter(EvaluationPeriod.status == PeriodStatus.ACTIVE).first()


def load_self_template():
    from pathlib import Path

    return load_template_file(Path(TEMPLATES_DIR) / "self_evaluation_r8_summer.json")


def load_assessment_template():
    from pathlib import Path

    return load_template_file(Path(TEMPLATES_DIR) / "assessment_r8_summer.json")


def load_facility_director_self_template():
    from pathlib import Path

    return load_template_file(Path(TEMPLATES_DIR) / "self_evaluation_r8_summer_facility_director.json")


def load_facility_director_assessment_template():
    from pathlib import Path

    return load_template_file(Path(TEMPLATES_DIR) / "assessment_r8_summer_facility_director.json")


def get_user_employee(db: Session, user: User) -> Optional[Employee]:
    return db.query(Employee).filter(Employee.user_id == user.id).first()


def require_self_eval_access(user: User, employee: Optional[Employee]) -> Employee:
    if not employee:
        raise HTTPException(status_code=404, detail="社員情報が見つかりません")
    if employee.employment_status == EmploymentStatus.RETIRED:
        raise HTTPException(status_code=403, detail="退職済みのためアクセスできません")
    if user.is_hq_evaluator:
        raise HTTPException(status_code=403, detail="本人のみアクセスできます")
    if user.role in {UserRole.EMPLOYEE, UserRole.EVALUATOR1}:
        return employee
    if user_needs_facility_director_self_eval(user, employee):
        return employee
    raise HTTPException(status_code=403, detail="本人のみアクセスできます")


def evaluator_subordinates_query(db: Session, evaluator: Employee, user: User):
    field = Employee.evaluator2_id if user.role == UserRole.EVALUATOR2 else Employee.evaluator1_id
    query = db.query(Employee).filter(
        field == evaluator.id,
        Employee.employment_status == EmploymentStatus.ACTIVE,
    )
    if user.role == UserRole.EVALUATOR2:
        if user.is_hq_evaluator:
            query = query.filter(Employee.job_title == "施設長")
        else:
            query = query.filter(Employee.job_title != "施設長")
    if not user.is_hq_evaluator:
        facility = resolve_facility_for_assignment(evaluator.assignment)
        if facility:
            query = query.filter(Employee.assignment.contains(facility.assignment_match))
    return query


def evaluator_role_name(user: User) -> str:
    return "evaluator1" if user.role == UserRole.EVALUATOR1 else "evaluator2"


def merge_assessment_display_data(template: dict, form_data: dict, self_eval_data: dict) -> dict:
    merged = dict(form_data or {})
    text_fields = dict(merged.get("text_fields") or {})
    self_text = (self_eval_data or {}).get("text_fields") or {}
    for field in template.get("text_fields", []):
        if field.get("readonly"):
            text_fields[field["id"]] = self_text.get(field["id"], text_fields.get(field["id"], ""))
    merged["text_fields"] = text_fields
    merged.setdefault("scores", {})
    return merged


def evaluator_can_edit(evaluation: Evaluation, is_eval1: bool, employee: Optional[Employee] = None) -> bool:
    if evaluation.self_eval_status != SubmissionStatus.SUBMITTED:
        return False
    skips_eval1 = evaluation_skips_eval1(employee)
    if is_eval1:
        if skips_eval1:
            return False
        return evaluation.eval1_status in {SubmissionStatus.DRAFT, SubmissionStatus.RETURNED}
    if skips_eval1:
        return evaluation.eval2_status in {
            SubmissionStatus.PENDING,
            SubmissionStatus.DRAFT,
            SubmissionStatus.RETURNED,
        }
    if evaluation.eval1_status != SubmissionStatus.SUBMITTED:
        return False
    return evaluation.eval2_status in {SubmissionStatus.DRAFT, SubmissionStatus.RETURNED}


def build_evaluator_reference(
    evaluation: Evaluation,
    is_eval1: bool,
    employee: Optional[Employee] = None,
    *,
    include_eval2: bool = False,
) -> dict:
    reference = {
        "self_evaluation": {
            "scores": evaluation.self_eval_data.get("scores", {}),
            "text_fields": evaluation.self_eval_data.get("text_fields", {}),
        }
    }
    if (
        not is_eval1
        and not evaluation_skips_eval1(employee)
        and evaluation.eval1_status in {
            SubmissionStatus.SUBMITTED,
            SubmissionStatus.RETURNED,
        }
    ):
        reference["evaluator1"] = {
            "scores": evaluation.eval1_data.get("scores", {}),
            "text_fields": evaluation.eval1_data.get("text_fields", {}),
        }
    if include_eval2 and evaluation.eval2_status in {
        SubmissionStatus.SUBMITTED,
        SubmissionStatus.RETURNED,
    }:
        reference["evaluator2"] = {
            "scores": evaluation.eval2_data.get("scores", {}),
            "text_fields": evaluation.eval2_data.get("text_fields", {}),
        }
    return reference


def _assignment_summary(
    sub: Employee,
    ev: Optional[Evaluation],
    *,
    user: User,
    hq_review_only: bool = False,
) -> AssignmentSummary:
    skips_eval1 = evaluation_skips_eval1(sub)
    if ev:
        if hq_review_only:
            my_status = ev.eval2_status
        elif user.role == UserRole.EVALUATOR1:
            my_status = ev.eval1_status
        else:
            my_status = ev.eval2_status
    else:
        my_status = SubmissionStatus.PENDING

    return AssignmentSummary(
        evaluation_id=ev.id if ev else UUID(int=0),
        employee=employee_attrs(sub),
        self_eval_status=ev.self_eval_status if ev else SubmissionStatus.PENDING,
        eval1_status=ev.eval1_status if ev else SubmissionStatus.PENDING,
        eval2_status=ev.eval2_status if ev else SubmissionStatus.PENDING,
        my_status=my_status,
        uses_facility_director_form=is_facility_director(sub),
        skips_eval1=skips_eval1,
        hq_review_only=hq_review_only,
    )


@app.on_event("startup")
def on_startup():
    settings.validate_runtime()
    create_tables()
    migrate_schema()
    if settings.auto_seed_demo:
        from scripts.seed_demo import seed

        seed()


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/auth/demo-status")
def demo_status():
    return {
        "demo_mode": settings.demo_mode,
        "guest_login_available": settings.demo_mode,
    }


@app.get("/api/auth/demo-personas", response_model=DemoPersonasResponse)
def demo_personas(db: Session = Depends(get_db)):
    if not settings.demo_mode:
        raise HTTPException(status_code=403, detail="デモ役割一覧は無効です")
    personas = list_demo_personas(db)
    if not personas:
        raise HTTPException(
            status_code=503,
            detail="デモ用アカウントが未設定です。管理者に seed_demo の実行を依頼してください",
        )
    return DemoPersonasResponse(
        personas=[DemoPersonaItem(**item) for item in personas],
        default_employee_id=settings.demo_guest_employee_id.strip(),
    )


@app.post("/api/auth/demo-login", response_model=TokenResponse)
def demo_login(
    body: Optional[DemoLoginRequest] = None,
    db: Session = Depends(get_db),
):
    if not settings.demo_mode:
        raise HTTPException(status_code=403, detail="デモログインは無効です")
    try:
        employee_id = resolve_demo_login_employee_id(body.employee_id if body else None)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    user = find_demo_user(db, employee_id)
    if not user or not user.is_active:
        raise HTTPException(
            status_code=503,
            detail="デモ用アカウントが未設定です。管理者に seed_demo の実行を依頼してください",
        )
    return TokenResponse(access_token=create_access_token(str(user.id)))


@app.post("/api/auth/login", response_model=TokenResponse)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.employee_id == form_data.username).first()
    if not user or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="社員IDまたはパスワードが正しくありません")
    if not user.is_active:
        raise HTTPException(status_code=401, detail="このアカウントは無効です")
    employee = db.query(Employee).filter(Employee.user_id == user.id).first()
    if employee and employee.employment_status == EmploymentStatus.RETIRED:
        raise HTTPException(status_code=401, detail="退職済みのためログインできません")
    return TokenResponse(access_token=create_access_token(str(user.id)))


@app.get("/api/auth/me", response_model=UserResponse)
def me(user: Annotated[User, Depends(get_current_user)], db: Session = Depends(get_db)):
    employee = db.query(Employee).filter(Employee.user_id == user.id).first()
    facility = resolve_facility_for_assignment(employee.assignment) if employee else None
    return UserResponse(
        id=user.id,
        employee_id=user.employee_id,
        role=user.role,
        name=employee.name if employee else None,
        must_change_password=user.must_change_password,
        is_admin=user.is_admin or user.role == UserRole.ADMIN,
        is_hq_evaluator=user.is_hq_evaluator,
        has_facility_director_self_eval=user_needs_facility_director_self_eval(user, employee),
        has_own_self_eval=user.role in {UserRole.EMPLOYEE, UserRole.EVALUATOR1}
        or user_needs_facility_director_self_eval(user, employee),
        can_access_bonus_workbook=user_can_access_bonus_workbook(user, employee),
        can_reset_user_passwords=user_can_reset_passwords(user),
        facility_key=facility.key if facility else None,
        facility_label=facility.label if facility else None,
    )


@app.get("/api/facilities", response_model=FacilitiesListResponse)
def list_facilities(
    user: Annotated[User, Depends(get_current_user)],
    db: Session = Depends(get_db),
):
    employee = db.query(Employee).filter(Employee.user_id == user.id).first()
    facilities = [
        FacilityItem(**facility_to_dict(item))
        for item in list_facilities_for_user(user, employee)
    ]
    return FacilitiesListResponse(facilities=facilities)


@app.post("/api/auth/change-password")
def change_password(
    body: ChangePasswordRequest,
    user: Annotated[User, Depends(get_current_user)],
    db: Session = Depends(get_db),
):
    if len(body.new_password) < 8:
        raise HTTPException(status_code=400, detail="新しいパスワードは8文字以上にしてください")
    if not verify_password(body.current_password, user.password_hash):
        raise HTTPException(status_code=400, detail="現在のパスワードが正しくありません")
    if body.current_password == body.new_password:
        raise HTTPException(status_code=400, detail="新しいパスワードは現在と異なるものにしてください")

    user.password_hash = hash_password(body.new_password)
    user.must_change_password = False
    db.commit()
    return {"ok": True, "message": "パスワードを変更しました"}


@app.get("/api/templates/self-evaluation")
def get_self_template():
    return load_self_template()


@app.get("/api/templates/assessment")
def get_assessment_template():
    return load_assessment_template()


@app.get("/api/me/workspace", response_model=WorkspaceResponse)
def employee_workspace(user: Annotated[User, Depends(get_current_user)], db: Session = Depends(get_db)):
    employee = get_user_employee(db, user)
    employee = require_self_eval_access(user, employee)

    period = get_active_period(db)
    evaluation = None
    if period:
        evaluation = (
            db.query(Evaluation)
            .filter(Evaluation.period_id == period.id, Evaluation.employee_id == employee.id)
            .first()
        )

    status_value = evaluation.self_eval_status if evaluation else SubmissionStatus.DRAFT
    template = resolve_self_template(db, period, employee, TEMPLATES_DIR)
    return WorkspaceResponse(
        period_name=period.name if period else None,
        attributes=employee_attrs(employee),
        template=template,
        form_data=evaluation.self_eval_data if evaluation else {},
        submission=SubmissionPanel(
            status=status_value,
            deadline=period.self_eval_deadline if period else None,
            submitted_at=evaluation.self_eval_submitted_at if evaluation else None,
            can_edit=status_value in {SubmissionStatus.DRAFT, SubmissionStatus.RETURNED},
            can_submit=status_value in {SubmissionStatus.DRAFT, SubmissionStatus.RETURNED},
        ),
    )


@app.put("/api/me/self-evaluation")
def save_self_evaluation(
    body: SaveFormRequest,
    user: Annotated[User, Depends(get_current_user)],
    db: Session = Depends(get_db),
):
    workspace = employee_workspace(user, db)
    if not workspace.submission.can_edit:
        raise HTTPException(status_code=400, detail="提出済みのため編集できません")

    employee = get_user_employee(db, user)
    employee = require_self_eval_access(user, employee)
    period = get_active_period(db)
    if not period:
        raise HTTPException(status_code=400, detail="考課期間が開始されていません")

    evaluation = (
        db.query(Evaluation)
        .filter(Evaluation.period_id == period.id, Evaluation.employee_id == employee.id)
        .first()
    )
    if not evaluation:
        evaluation = Evaluation(period_id=period.id, employee_id=employee.id)
        db.add(evaluation)

    evaluation.self_eval_data = body.data
    evaluation.self_eval_status = SubmissionStatus.DRAFT
    db.commit()
    return {"ok": True}


@app.post("/api/me/self-evaluation/submit")
def submit_self_evaluation(user: Annotated[User, Depends(get_current_user)], db: Session = Depends(get_db)):
    workspace = employee_workspace(user, db)
    if not workspace.submission.can_submit:
        raise HTTPException(status_code=400, detail="提出できません")

    employee = get_user_employee(db, user)
    employee = require_self_eval_access(user, employee)
    period = get_active_period(db)
    if not period:
        raise HTTPException(status_code=400, detail="考課期間が開始されていません")

    evaluation = (
        db.query(Evaluation)
        .filter(Evaluation.period_id == period.id, Evaluation.employee_id == employee.id)
        .first()
    )
    if not evaluation:
        raise HTTPException(status_code=400, detail="保存してから提出してください")

    template = resolve_self_template(db, period, employee, TEMPLATES_DIR)
    errors = validate_form_data(template, evaluation.self_eval_data)
    if errors:
        raise HTTPException(
            status_code=400,
            detail={"message": "未入力の項目があるため提出できません", "errors": errors},
        )

    evaluation.self_eval_status = SubmissionStatus.SUBMITTED
    evaluation.self_eval_submitted_at = datetime.utcnow()
    if evaluation_skips_eval1(employee):
        evaluation.eval1_status = SubmissionStatus.SUBMITTED
        evaluation.eval2_status = SubmissionStatus.DRAFT
    else:
        evaluation.eval1_status = SubmissionStatus.DRAFT
    db.commit()
    return {"ok": True}


@app.post("/api/me/self-evaluation/unsubmit")
def unsubmit_self_evaluation(user: Annotated[User, Depends(get_current_user)], db: Session = Depends(get_db)):
    if not settings.dev_allow_unsubmit:
        raise HTTPException(status_code=403, detail="この操作は開発環境でのみ利用できます")

    employee = get_user_employee(db, user)
    employee = require_self_eval_access(user, employee)
    period = get_active_period(db)
    if not period:
        raise HTTPException(status_code=400, detail="考課期間が開始されていません")

    evaluation = (
        db.query(Evaluation)
        .filter(Evaluation.period_id == period.id, Evaluation.employee_id == employee.id)
        .first()
    )
    if not evaluation or evaluation.self_eval_status != SubmissionStatus.SUBMITTED:
        raise HTTPException(status_code=400, detail="提出済みの自己評価のみ取り消せます")

    evaluation.self_eval_status = SubmissionStatus.RETURNED
    evaluation.self_eval_submitted_at = None
    evaluation.eval1_status = SubmissionStatus.PENDING
    evaluation.eval2_status = SubmissionStatus.PENDING
    db.commit()
    return {"ok": True, "message": "提出を取り消しました。再度編集できます。"}


@app.get("/api/evaluator/workspace", response_model=EvaluatorWorkspaceResponse)
def evaluator_workspace(user: Annotated[User, Depends(get_current_user)], db: Session = Depends(get_db)):
    if user.role not in {UserRole.EVALUATOR1, UserRole.EVALUATOR2}:
        raise HTTPException(status_code=403, detail="評価者のみアクセスできます")

    evaluator = db.query(Employee).filter(Employee.user_id == user.id).first()
    if not evaluator:
        raise HTTPException(status_code=404, detail="評価者情報が見つかりません")

    period = get_active_period(db)
    assignments: list[AssignmentSummary] = []
    seen_ids: set[UUID] = set()

    if user.is_hq_evaluator:
        directors = evaluator_subordinates_query(db, evaluator, user).all()
        for sub in directors:
            seen_ids.add(sub.id)
            ev = None
            if period:
                ev = (
                    db.query(Evaluation)
                    .filter(Evaluation.period_id == period.id, Evaluation.employee_id == sub.id)
                    .first()
                )
            assignments.append(_assignment_summary(sub, ev, user=user))

        for sub in hq_review_employees(db, period):
            if sub.id in seen_ids:
                continue
            seen_ids.add(sub.id)
            ev = (
                db.query(Evaluation)
                .filter(Evaluation.period_id == period.id, Evaluation.employee_id == sub.id)
                .first()
            )
            assignments.append(_assignment_summary(sub, ev, user=user, hq_review_only=True))
    else:
        subordinates = evaluator_subordinates_query(db, evaluator, user).all()
        for sub in subordinates:
            ev = None
            if period:
                ev = (
                    db.query(Evaluation)
                    .filter(Evaluation.period_id == period.id, Evaluation.employee_id == sub.id)
                    .first()
                )
            assignments.append(_assignment_summary(sub, ev, user=user))

    return EvaluatorWorkspaceResponse(period_name=period.name if period else None, assignments=assignments)


def _get_evaluator_assignment(
    evaluation_id: UUID,
    user: User,
    db: Session,
) -> tuple[Evaluation, Employee, EvaluationPeriod, bool, bool]:
    if user.role not in {UserRole.EVALUATOR1, UserRole.EVALUATOR2}:
        raise HTTPException(status_code=403, detail="評価者のみアクセスできます")

    evaluation = db.get(Evaluation, evaluation_id)
    if not evaluation:
        raise HTTPException(status_code=404, detail="考課データが見つかりません")

    employee = db.get(Employee, evaluation.employee_id)
    period = db.get(EvaluationPeriod, evaluation.period_id)
    if not employee or not period:
        raise HTTPException(status_code=404, detail="考課データが見つかりません")

    evaluator = db.query(Employee).filter(Employee.user_id == user.id).first()
    if not evaluator:
        raise HTTPException(status_code=404, detail="評価者情報が見つかりません")

    is_eval1 = user.role == UserRole.EVALUATOR1
    hq_review_only = False
    if is_eval1:
        if employee.evaluator1_id != evaluator.id:
            raise HTTPException(status_code=403, detail="担当外の考課です")
    elif user.is_hq_evaluator:
        if is_facility_director(employee):
            if employee.evaluator2_id != evaluator.id:
                raise HTTPException(status_code=403, detail="担当外の考課です")
            is_eval1 = False
        else:
            ev2 = db.get(Employee, employee.evaluator2_id) if employee.evaluator2_id else None
            if (
                evaluation.eval2_status == SubmissionStatus.SUBMITTED
                and ev2 is not None
                and is_facility_director(ev2)
            ):
                is_eval1 = False
                hq_review_only = True
            else:
                raise HTTPException(status_code=403, detail="担当外の考課です")
    else:
        if is_facility_director(employee) or employee.evaluator2_id != evaluator.id:
            raise HTTPException(status_code=403, detail="担当外の考課です")

    return evaluation, employee, period, is_eval1, hq_review_only


@app.get("/api/evaluator/assignments/{evaluation_id}", response_model=EvaluatorWorkspaceResponse)
def evaluator_assignment_detail(
    evaluation_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    db: Session = Depends(get_db),
):
    base = evaluator_workspace(user, db)
    evaluation, employee, period, is_eval1, hq_review_only = _get_evaluator_assignment(evaluation_id, user, db)

    template = resolve_assessment_template(db, period, employee, TEMPLATES_DIR)
    my_data = evaluation.eval1_data if is_eval1 else evaluation.eval2_data
    my_status = evaluation.eval1_status if is_eval1 else evaluation.eval2_status
    deadline = period.eval1_deadline if is_eval1 else period.eval2_deadline
    submitted_at = evaluation.eval1_submitted_at if is_eval1 else evaluation.eval2_submitted_at

    self_submitted = evaluation.self_eval_status == SubmissionStatus.SUBMITTED
    can_edit = (
        not hq_review_only
        and self_submitted
        and evaluator_can_edit(evaluation, is_eval1, employee)
    )

    base.selected = WorkspaceResponse(
        period_name=period.name,
        attributes=employee_attrs(employee),
        template=template,
        form_data=merge_assessment_display_data(template, my_data, evaluation.self_eval_data)
        if self_submitted
        else {"scores": {}, "text_fields": {}},
        submission=SubmissionPanel(
            status=my_status if self_submitted else SubmissionStatus.PENDING,
            deadline=deadline,
            submitted_at=submitted_at,
            can_edit=can_edit,
            can_submit=can_edit and my_status in {SubmissionStatus.DRAFT, SubmissionStatus.RETURNED},
        ),
    )
    base.reference = (
        build_evaluator_reference(
            evaluation,
            is_eval1,
            employee,
            include_eval2=hq_review_only,
        )
        if self_submitted
        else {}
    )
    return base


@app.put("/api/evaluator/assignments/{evaluation_id}")
def save_evaluator_assignment(
    evaluation_id: UUID,
    body: SaveFormRequest,
    user: Annotated[User, Depends(get_current_user)],
    db: Session = Depends(get_db),
):
    evaluation, employee, period, is_eval1, hq_review_only = _get_evaluator_assignment(evaluation_id, user, db)

    if hq_review_only:
        raise HTTPException(status_code=400, detail="確認専用のため編集できません")

    if not evaluator_can_edit(evaluation, is_eval1, employee):
        raise HTTPException(status_code=400, detail="現在は編集できません")

    if is_eval1:
        evaluation.eval1_data = body.data
        if evaluation.eval1_status in {SubmissionStatus.PENDING, SubmissionStatus.RETURNED}:
            evaluation.eval1_status = SubmissionStatus.DRAFT
    else:
        evaluation.eval2_data = body.data
        if evaluation.eval2_status in {SubmissionStatus.PENDING, SubmissionStatus.RETURNED}:
            evaluation.eval2_status = SubmissionStatus.DRAFT

    db.commit()
    return {"ok": True}


@app.post("/api/evaluator/assignments/{evaluation_id}/submit")
def submit_evaluator_assignment(
    evaluation_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    db: Session = Depends(get_db),
):
    evaluation, employee, period, is_eval1, hq_review_only = _get_evaluator_assignment(evaluation_id, user, db)

    if hq_review_only:
        raise HTTPException(status_code=400, detail="確認専用のため編集できません")

    if not evaluator_can_edit(evaluation, is_eval1, employee):
        raise HTTPException(status_code=400, detail="現在は提出できません")

    my_status = evaluation.eval1_status if is_eval1 else evaluation.eval2_status
    if my_status not in {SubmissionStatus.DRAFT, SubmissionStatus.RETURNED}:
        raise HTTPException(status_code=400, detail="提出できません")

    template = resolve_assessment_template(db, period, employee, TEMPLATES_DIR)
    role = evaluator_role_name(user)
    form_data = evaluation.eval1_data if is_eval1 else evaluation.eval2_data
    errors = validate_form_data(template, form_data, role=role)
    if errors:
        raise HTTPException(
            status_code=400,
            detail={"message": "未入力の項目があるため提出できません", "errors": errors},
        )

    now = datetime.utcnow()
    if is_eval1:
        evaluation.eval1_status = SubmissionStatus.SUBMITTED
        evaluation.eval1_submitted_at = now
        if evaluation.eval2_status == SubmissionStatus.PENDING:
            evaluation.eval2_status = SubmissionStatus.DRAFT
    else:
        evaluation.eval2_status = SubmissionStatus.SUBMITTED
        evaluation.eval2_submitted_at = now

    db.commit()
    return {"ok": True}


RETURN_TARGETS = {
    "self_eval": "self_eval_status",
    "eval1": "eval1_status",
    "eval2": "eval2_status",
}


@app.get("/api/admin/evaluations", response_model=List[AdminEvaluationItem])
def admin_list_evaluations(
    admin: Annotated[User, Depends(require_admin)],
    db: Session = Depends(get_db),
):
    period = get_active_period(db)
    if not period:
        return []

    evaluations = db.query(Evaluation).filter(Evaluation.period_id == period.id).all()
    items: List[AdminEvaluationItem] = []
    for ev in evaluations:
        employee = db.get(Employee, ev.employee_id)
        if not employee or employee.employment_status != EmploymentStatus.ACTIVE:
            continue
        items.append(
            AdminEvaluationItem(
                evaluation_id=ev.id,
                employee=employee_attrs(employee),
                self_eval_status=ev.self_eval_status,
                eval1_status=ev.eval1_status,
                eval2_status=ev.eval2_status,
            )
        )
    return items


@app.post("/api/admin/evaluations/{evaluation_id}/return")
def admin_return_evaluation(
    evaluation_id: UUID,
    body: ReturnRequest,
    admin: Annotated[User, Depends(require_admin)],
    db: Session = Depends(get_db),
):
    if body.target not in RETURN_TARGETS:
        raise HTTPException(status_code=400, detail="target は self_eval / eval1 / eval2 です")

    evaluation = db.get(Evaluation, evaluation_id)
    if not evaluation:
        raise HTTPException(status_code=404, detail="考課データが見つかりません")

    status_field = RETURN_TARGETS[body.target]
    current = getattr(evaluation, status_field)
    if current != SubmissionStatus.SUBMITTED:
        raise HTTPException(status_code=400, detail="提出済みのものだけ差し戻しできます")

    setattr(evaluation, status_field, SubmissionStatus.RETURNED)
    if body.target == "self_eval":
        evaluation.self_eval_submitted_at = None
        evaluation.eval1_status = SubmissionStatus.PENDING
        evaluation.eval2_status = SubmissionStatus.PENDING
    elif body.target == "eval1":
        evaluation.eval1_submitted_at = None
        evaluation.eval2_status = SubmissionStatus.PENDING
    elif body.target == "eval2":
        evaluation.eval2_submitted_at = None

    db.add(
        AuditLog(
            user_id=admin.id,
            action="return",
            target_type=body.target,
            target_id=evaluation.id,
            detail={"reason": body.reason},
        )
    )
    db.commit()
    return {"ok": True, "message": "差し戻ししました"}


def ensure_period_evaluations(db: Session, period: EvaluationPeriod) -> int:
    existing_ids = {
        employee_id
        for (employee_id,) in db.query(Evaluation.employee_id).filter(Evaluation.period_id == period.id).all()
    }
    created = 0
    for employee in active_employees_query(db).all():
        if employee.id in existing_ids:
            continue
        db.add(Evaluation(period_id=period.id, employee_id=employee.id))
        created += 1
    return created


def employee_list_item(employee: Employee) -> EmployeeListItem:
    return EmployeeListItem(
        id=employee.id,
        employee_id=employee.employee_id,
        name=employee.name,
        assignment=employee.assignment,
        job_type=employee.job_type,
        job_title=employee.job_title,
        years_of_service=employee.years_of_service,
        employment_status=employee.employment_status,
        evaluator1_employee_id=employee.evaluator1.employee_id if employee.evaluator1 else None,
        evaluator1_name=employee.evaluator1.name if employee.evaluator1 else None,
        evaluator2_employee_id=employee.evaluator2.employee_id if employee.evaluator2 else None,
        evaluator2_name=employee.evaluator2.name if employee.evaluator2 else None,
    )


@app.get("/api/admin/periods", response_model=List[PeriodResponse])
def admin_list_periods(
    admin: Annotated[User, Depends(require_admin)],
    db: Session = Depends(get_db),
):
    periods = db.query(EvaluationPeriod).order_by(EvaluationPeriod.fiscal_year.desc()).all()
    return periods


@app.post("/api/admin/periods", response_model=PeriodResponse)
def admin_create_period(
    body: PeriodCreateRequest,
    admin: Annotated[User, Depends(require_admin)],
    db: Session = Depends(get_db),
):
    self_tpl = FormTemplate(
        type=TemplateType.SELF_EVALUATION,
        version=load_self_template().get("version", "1.0.0"),
        name=load_self_template().get("title", "自己評価表"),
        content=load_self_template(),
    )
    assess_tpl = FormTemplate(
        type=TemplateType.ASSESSMENT,
        version=load_assessment_template().get("version", "1.0.0"),
        name=load_assessment_template().get("title", "考課表"),
        content=load_assessment_template(),
    )
    director_self_tpl = FormTemplate(
        type=TemplateType.SELF_EVALUATION,
        version=load_facility_director_self_template().get("version", "1.0.0"),
        name=load_facility_director_self_template().get("title", "施設長自己評価表"),
        content=load_facility_director_self_template(),
    )
    director_assess_tpl = FormTemplate(
        type=TemplateType.ASSESSMENT,
        version=load_facility_director_assessment_template().get("version", "1.0.0"),
        name=load_facility_director_assessment_template().get("title", "施設長考課表"),
        content=load_facility_director_assessment_template(),
    )
    db.add_all([self_tpl, assess_tpl, director_self_tpl, director_assess_tpl])
    db.flush()

    period = EvaluationPeriod(
        name=body.name,
        season=body.season,
        fiscal_year=body.fiscal_year,
        self_eval_deadline=body.self_eval_deadline,
        eval1_deadline=body.eval1_deadline,
        eval2_deadline=body.eval2_deadline,
        self_eval_template_id=self_tpl.id,
        assessment_template_id=assess_tpl.id,
        facility_director_self_eval_template_id=director_self_tpl.id,
        facility_director_assessment_template_id=director_assess_tpl.id,
        status=PeriodStatus.DRAFT,
    )
    db.add(period)
    db.add(
        AuditLog(
            user_id=admin.id,
            action="create_period",
            target_type="period",
            target_id=period.id,
            detail={"name": body.name},
        )
    )
    db.commit()
    db.refresh(period)
    return period


@app.post("/api/admin/periods/{period_id}/activate", response_model=PeriodResponse)
def admin_activate_period(
    period_id: UUID,
    admin: Annotated[User, Depends(require_admin)],
    db: Session = Depends(get_db),
):
    period = db.get(EvaluationPeriod, period_id)
    if not period:
        raise HTTPException(status_code=404, detail="考課期間が見つかりません")
    if period.status == PeriodStatus.ACTIVE:
        return period

    for active in db.query(EvaluationPeriod).filter(EvaluationPeriod.status == PeriodStatus.ACTIVE).all():
        active.status = PeriodStatus.CLOSED

    period.status = PeriodStatus.ACTIVE
    created = ensure_period_evaluations(db, period)
    db.add(
        AuditLog(
            user_id=admin.id,
            action="activate_period",
            target_type="period",
            target_id=period.id,
            detail={"evaluations_created": created},
        )
    )
    db.commit()
    db.refresh(period)
    return period


@app.post("/api/admin/employees/import", response_model=ImportResultResponse)
async def admin_import_employees(
    admin: Annotated[User, Depends(require_admin)],
    db: Session = Depends(get_db),
    file: UploadFile = File(...),
):
    if not file.filename or not file.filename.lower().endswith((".xlsx", ".xlsm")):
        raise HTTPException(status_code=400, detail="Excelファイル (.xlsx) をアップロードしてください")

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="ファイルが空です")

    active_period = get_active_period(db)
    result = import_employees_from_excel(
        db=db,
        content=content,
        admin_user=admin,
        password_hash_fn=hash_password,
        default_password=settings.default_employee_password,
        active_period=active_period,
    )
    return ImportResultResponse(
        created=result.created,
        updated=result.updated,
        users_created=result.users_created,
        evaluations_created=result.evaluations_created,
        roles_updated=result.roles_updated,
        errors=result.errors,
    )


@app.post("/api/admin/employees/import-roster", response_model=ImportResultResponse)
async def admin_import_roster(
    admin: Annotated[User, Depends(require_admin)],
    db: Session = Depends(get_db),
    file: UploadFile = File(...),
    facility: str = "",
    facility_key: str = "",
):
    """名簿 Excel（社員ID・所属施設・一次/二次評価者 形式）を取込。"""
    if not file.filename or not file.filename.lower().endswith((".xlsx", ".xlsm")):
        raise HTTPException(status_code=400, detail="Excelファイル (.xlsx) をアップロードしてください")

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="ファイルが空です")

    active_period = get_active_period(db)
    facility_label = facility.strip() or None
    facility_key_value = facility_key.strip() or None
    if not facility_key_value and not facility_label:
        facility_label = settings.default_facility_filter

    result = import_roster_from_excel(
        db=db,
        content=content,
        admin_user=admin,
        password_hash_fn=hash_password,
        default_password=settings.default_employee_password,
        active_period=active_period,
        facility_filter=facility_label,
        facility_key=facility_key_value,
        active_only=True,
        admin_job_titles=settings.admin_job_title_set,
        admin_employee_ids=settings.admin_employee_id_set,
        leader_titles=settings.eval1_leader_title_set,
    )
    return ImportResultResponse(
        created=result.created,
        updated=result.updated,
        users_created=result.users_created,
        evaluations_created=result.evaluations_created,
        roles_updated=result.roles_updated,
        skipped=result.skipped,
        errors=result.errors,
    )


@app.get("/api/admin/employee-options", response_model=EmployeeOptionsResponse)
def admin_employee_options(
    admin: Annotated[User, Depends(require_admin)],
):
    return EmployeeOptionsResponse(**employee_options_dict())


@app.get("/api/admin/employees", response_model=List[EmployeeListItem])
def admin_list_employees(
    admin: Annotated[User, Depends(require_admin)],
    db: Session = Depends(get_db),
    status: str = "active",
):
    query = db.query(Employee).order_by(Employee.employee_id)
    if status == "active":
        query = query.filter(Employee.employment_status == EmploymentStatus.ACTIVE)
    elif status == "retired":
        query = query.filter(Employee.employment_status == EmploymentStatus.RETIRED)
    return [employee_list_item(emp) for emp in query.all()]


@app.post("/api/admin/employees", response_model=EmployeeActionResponse)
def admin_create_employee(
    body: CreateEmployeeRequest,
    admin: Annotated[User, Depends(require_admin)],
    db: Session = Depends(get_db),
):
    try:
        result = create_or_reactivate_employee(
            db=db,
            employee_id=body.employee_id,
            name=body.name,
            assignment=body.assignment,
            job_type=body.job_type,
            job_title=body.job_title,
            years_of_service=body.years_of_service,
            evaluator1_employee_id=body.evaluator1_employee_id,
            evaluator2_employee_id=body.evaluator2_employee_id,
            admin_user=admin,
            password_hash_fn=hash_password,
            default_password=settings.default_employee_password,
            active_period=get_active_period(db),
        )
        db.commit()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return EmployeeActionResponse(
        message=result.message,
        employee_id=result.employee_id,
        name=result.name,
        warnings=result.warnings,
    )


@app.post("/api/admin/employees/{employee_uuid}/retire", response_model=EmployeeActionResponse)
def admin_retire_employee(
    employee_uuid: UUID,
    body: RetireEmployeeRequest,
    admin: Annotated[User, Depends(require_admin)],
    db: Session = Depends(get_db),
):
    employee = db.get(Employee, employee_uuid)
    if not employee:
        raise HTTPException(status_code=404, detail="職員が見つかりません")
    try:
        result = retire_employee(db, employee, admin, reason=body.reason)
        db.commit()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return EmployeeActionResponse(
        message=result.message,
        employee_id=result.employee_id,
        name=result.name,
        archive_id=result.archive_id,
        warnings=result.warnings,
    )


@app.get("/api/admin/employees/retired-archives", response_model=List[RetiredArchiveItem])
def admin_list_retired_archives(
    admin: Annotated[User, Depends(require_admin)],
):
    return [RetiredArchiveItem(**item) for item in list_retirement_archives(settings.retired_archives_dir)]


@app.get("/api/admin/employees/retired-archives/{archive_id}/download")
def admin_download_retired_archive(
    archive_id: str,
    admin: Annotated[User, Depends(require_admin)],
    file_type: str = "json",
):
    if file_type not in {"json", "xlsx"}:
        raise HTTPException(status_code=400, detail="file_type は json または xlsx です")
    try:
        path = resolve_archive_path(settings.retired_archives_dir, archive_id, file_type)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="アーカイブが見つかりません") from exc

    media = (
        "application/json"
        if file_type == "json"
        else "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    return StreamingResponse(
        BytesIO(path.read_bytes()),
        media_type=media,
        headers={"Content-Disposition": f'attachment; filename="{path.name}"'},
    )


@app.get("/api/admin/users", response_model=List[AdminUserItem])
def admin_list_users(
    actor: Annotated[User, Depends(require_password_manager)],
    db: Session = Depends(get_db),
):
    users = db.query(User).order_by(User.employee_id).all()
    items: List[AdminUserItem] = []
    for user in users:
        employee = db.query(Employee).filter(Employee.user_id == user.id).first()
        items.append(
            AdminUserItem(
                user_id=user.id,
                employee_id=user.employee_id,
                name=employee.name if employee else None,
                role=user.role,
                is_active=user.is_active,
            )
        )
    return items


@app.post("/api/admin/users/{user_id}/reset-password", response_model=ResetPasswordResponse)
def admin_reset_user_password(
    user_id: UUID,
    actor: Annotated[User, Depends(require_password_manager)],
    db: Session = Depends(get_db),
):
    target = db.get(User, user_id)
    if not target:
        raise HTTPException(status_code=404, detail="ユーザーが見つかりません")
    if target.id == actor.id:
        raise HTTPException(status_code=400, detail="自分自身のパスワードはこの操作ではリセットできません")
    if target.role == UserRole.ADMIN:
        raise HTTPException(status_code=400, detail="システム管理者のパスワードはリセットできません")
    if not target.is_active:
        raise HTTPException(status_code=400, detail="無効なアカウントはリセットできません")

    temporary_password = settings.default_employee_password
    target.password_hash = hash_password(temporary_password)
    target.must_change_password = True
    db.add(
        AuditLog(
            user_id=actor.id,
            action="reset_password",
            target_type="user",
            target_id=target.id,
            detail={"employee_id": target.employee_id},
        )
    )
    db.commit()
    return ResetPasswordResponse(
        message=f"{target.employee_id} のパスワードを初期値にリセットしました",
        employee_id=target.employee_id,
        temporary_password=temporary_password,
    )


@app.put("/api/admin/users/{user_id}/role", response_model=AdminUserItem)
def admin_update_user_role(
    user_id: UUID,
    body: UpdateUserRoleRequest,
    admin: Annotated[User, Depends(require_admin)],
    db: Session = Depends(get_db),
):
    target = db.get(User, user_id)
    if not target:
        raise HTTPException(status_code=404, detail="ユーザーが見つかりません")
    if target.role == UserRole.ADMIN and body.role != UserRole.ADMIN:
        admin_count = db.query(User).filter(User.role == UserRole.ADMIN).count()
        if admin_count <= 1:
            raise HTTPException(status_code=400, detail="最後の管理者のロールは変更できません")

    target.role = body.role
    db.add(
        AuditLog(
            user_id=admin.id,
            action="update_role",
            target_type="user",
            target_id=target.id,
            detail={"role": body.role.value},
        )
    )
    db.commit()
    db.refresh(target)

    employee = db.query(Employee).filter(Employee.user_id == target.id).first()
    return AdminUserItem(
        user_id=target.id,
        employee_id=target.employee_id,
        name=employee.name if employee else None,
        role=target.role,
        is_active=target.is_active,
    )


@app.get("/api/bonus-workbook", response_model=BonusWorkbookResponse)
def bonus_workbook_get(
    user: Annotated[User, Depends(require_bonus_workbook_access)],
    db: Session = Depends(get_db),
    facility: str = "inaha",
    fiscal_year: Optional[int] = None,
):
    if not _bonus_workbook_api_enabled():
        raise HTTPException(status_code=400, detail="BONUS_WORKBOOK_TEMPLATE_PATH が未設定です")
    _, employee = _bonus_actor(db, user)
    facility = _require_facility_access(facility, user, employee)
    target_year, current_year, read_only = _resolve_bonus_fiscal_year(db, fiscal_year)
    try:
        rows, facility_label = load_bonus_workbook_rows(db, facility_key=facility)
        rows, provision_monthly, provision_months = merge_amounts_into_rows(
            rows,
            facility,
            target_year,
        )
        summary = compute_bonus_summary(
            rows,
            facility_key=facility,
            provision_monthly=provision_monthly,
            provision_months=provision_months,
            fiscal_year=target_year,
        )
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    period = get_active_period(db)
    return BonusWorkbookResponse(
        facility=facility_label,
        facility_key=facility,
        period_name=period.name if period else None,
        template_configured=_bonus_workbook_template_configured(),
        bonus_sheet_available=len(rows) > 0,
        fiscal_year=target_year,
        current_fiscal_year=current_year,
        available_fiscal_years=_bonus_fiscal_years_for_facility(facility, target_year),
        read_only=read_only,
        provision_monthly=provision_monthly,
        provision_months=provision_months,
        summary=BonusWorkbookSummary(**summary),
        rows=[BonusWorkbookRow(**row) for row in rows],
    )


@app.put("/api/bonus-workbook")
def bonus_workbook_save(
    body: BonusWorkbookSaveRequest,
    user: Annotated[User, Depends(require_bonus_workbook_access)],
    db: Session = Depends(get_db),
    facility: str = "inaha",
    fiscal_year: Optional[int] = None,
):
    if not _bonus_workbook_api_enabled():
        raise HTTPException(status_code=400, detail="BONUS_WORKBOOK_TEMPLATE_PATH が未設定です")
    _, employee = _bonus_actor(db, user)
    facility = _require_facility_access(facility, user, employee)
    target_year, _, read_only = _resolve_bonus_fiscal_year(db, fiscal_year)
    if read_only:
        raise HTTPException(status_code=403, detail="過去年度のデータは閲覧のみです")
    is_hq = user_has_global_facility_access(user)
    try:
        save_bonus_workbook_rows(
            [row.model_dump() for row in body.rows],
            facility_key=facility,
            fiscal_year=target_year,
        )
        save_amounts_for_workbook(
            facility,
            target_year,
            [row.model_dump() for row in body.rows],
            provision_monthly=body.provision_monthly if not is_hq else None,
            provision_months=body.provision_months if not is_hq else None,
            allow_proposed=not is_hq,
            allow_bonus=is_hq,
            allow_provision=not is_hq,
        )
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    db.add(
        AuditLog(
            user_id=user.id,
            action="bonus_workbook_save",
            target_type="bonus_workbook",
            detail={"facility": facility, "fiscal_year": target_year, "rows": len(body.rows)},
        )
    )
    db.commit()
    return {"ok": True}


@app.put("/api/bonus-workbook/amounts", response_model=BonusAmountsSaveResponse)
def bonus_workbook_save_amounts(
    body: BonusAmountsSaveRequest,
    user: Annotated[User, Depends(require_bonus_workbook_access)],
    db: Session = Depends(get_db),
    facility: str = "inaha",
    fiscal_year: Optional[int] = None,
):
    if not _bonus_workbook_api_enabled():
        raise HTTPException(status_code=400, detail="BONUS_WORKBOOK_TEMPLATE_PATH が未設定です")
    _, employee = _bonus_actor(db, user)
    facility = _require_facility_access(facility, user, employee)
    target_year, _, read_only = _resolve_bonus_fiscal_year(db, fiscal_year)
    if read_only:
        raise HTTPException(status_code=403, detail="過去年度のデータは閲覧のみです")
    is_hq = user_has_global_facility_access(user)
    row_payloads = [row.model_dump() for row in body.rows]
    try:
        save_amounts_for_workbook(
            facility,
            target_year,
            row_payloads,
            provision_monthly=body.provision_monthly if not is_hq else None,
            provision_months=body.provision_months if not is_hq else None,
            allow_proposed=not is_hq,
            allow_bonus=is_hq,
            allow_provision=not is_hq,
        )
        if is_facility_directors_bonus_key(facility):
            provision_monthly = 0
            provision_months = 12
        else:
            store = load_bonus_amounts_store(facility, target_year)
            provision_monthly = int(store.get("provision_monthly", 0))
            provision_months = int(store.get("provision_months", 12))
        summary = compute_bonus_summary(
            row_payloads,
            facility_key=facility,
            provision_monthly=provision_monthly,
            provision_months=provision_months,
            fiscal_year=target_year,
        )
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    db.add(
        AuditLog(
            user_id=user.id,
            action="bonus_amounts_save",
            target_type="bonus_workbook",
            detail={"facility": facility, "fiscal_year": target_year, "rows": len(body.rows)},
        )
    )
    db.commit()
    return BonusAmountsSaveResponse(
        provision_monthly=provision_monthly,
        provision_months=provision_months,
        summary=BonusWorkbookSummary(**summary),
    )


@app.post("/api/bonus-workbook/sync", response_model=BonusReflectResultResponse)
def bonus_workbook_sync(
    user: Annotated[User, Depends(require_bonus_workbook_access)],
    db: Session = Depends(get_db),
    facility: str = "inaha",
):
    if not _bonus_workbook_api_enabled():
        raise HTTPException(status_code=400, detail="BONUS_WORKBOOK_TEMPLATE_PATH が未設定です")
    period = get_active_period(db)
    if not period:
        raise HTTPException(status_code=400, detail="考課期間が開始されていません")
    _, employee = _bonus_actor(db, user)
    facility = _require_facility_access(facility, user, employee)
    try:
        _, result = reflect_evaluations_to_bonus_workbook(
            db, period, facility_key=facility, dry_run=False
        )
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    db.add(
        AuditLog(
            user_id=user.id,
            action="bonus_workbook_sync",
            target_type="period",
            target_id=period.id,
            detail={"facility": facility, "updated_rows": result.updated_rows},
        )
    )
    db.commit()
    return BonusReflectResultResponse(
        facility=result.facility,
        updated_rows=result.updated_rows,
        matched_employees=result.matched_employees,
        unmatched_employees=result.unmatched_employees,
        unmatched_excel_names=result.unmatched_excel_names,
        warnings=result.warnings,
    )


@app.post("/api/bonus-workbook/sync-roster", response_model=BonusReflectResultResponse)
def bonus_workbook_sync_roster(
    user: Annotated[User, Depends(require_bonus_workbook_access)],
    db: Session = Depends(get_db),
    facility: str = "inaha",
):
    if not _bonus_workbook_api_enabled():
        raise HTTPException(status_code=400, detail="BONUS_WORKBOOK_TEMPLATE_PATH が未設定です")
    _, employee = _bonus_actor(db, user)
    facility = _require_facility_access(facility, user, employee)
    period = get_active_period(db)
    fiscal_year = period.fiscal_year if period else default_fiscal_year()
    try:
        result = sync_roster_to_bonus_workbook(
            db,
            facility_key=facility,
            dry_run=False,
            fiscal_year=fiscal_year,
        )
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    db.add(
        AuditLog(
            user_id=user.id,
            action="bonus_workbook_sync_roster",
            target_type="bonus_workbook",
            detail={"facility": facility, "updated_rows": result.updated_rows},
        )
    )
    db.commit()
    return BonusReflectResultResponse(
        facility=result.facility,
        updated_rows=result.updated_rows,
        matched_employees=result.matched_employees,
        unmatched_employees=result.unmatched_employees,
        unmatched_excel_names=result.unmatched_excel_names,
        warnings=result.warnings,
    )


@app.get("/api/bonus-workbook/export")
def bonus_workbook_export(
    user: Annotated[User, Depends(require_bonus_workbook_access)],
    db: Session = Depends(get_db),
    facility: str = "inaha",
):
    if not _bonus_workbook_api_enabled():
        raise HTTPException(status_code=400, detail="BONUS_WORKBOOK_TEMPLATE_PATH が未設定です")
    _, employee = _bonus_actor(db, user)
    facility = _require_facility_access(facility, user, employee)
    try:
        data, filename = export_bonus_workbook_bytes(facility_key=facility)
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    ascii_filename = "bonus_workbook.xlsx"
    encoded_filename = quote(filename)
    return StreamingResponse(
        BytesIO(data),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": (
                f'attachment; filename="{ascii_filename}"; filename*=UTF-8\'\'{encoded_filename}'
            )
        },
    )


@app.get("/api/admin/periods/{period_id}/export-bonus/preview", response_model=BonusReflectResultResponse)
def admin_export_bonus_preview(
    period_id: UUID,
    admin: Annotated[User, Depends(require_admin)],
    db: Session = Depends(get_db),
    facility: str = "inaha",
):
    if not settings.bonus_workbook_template_path.strip():
        raise HTTPException(
            status_code=400,
            detail="BONUS_WORKBOOK_TEMPLATE_PATH が未設定です（.env に賞与 Excel のパスを設定してください）",
        )
    period = db.get(EvaluationPeriod, period_id)
    if not period:
        raise HTTPException(status_code=404, detail="考課期間が見つかりません")
    employee = db.query(Employee).filter(Employee.user_id == admin.id).first()
    facility = _require_facility_access(facility, admin, employee)
    try:
        _, result = reflect_evaluations_to_bonus_workbook(
            db, period, facility_key=facility, dry_run=True
        )
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return BonusReflectResultResponse(
        facility=result.facility,
        updated_rows=result.updated_rows,
        matched_employees=result.matched_employees,
        unmatched_employees=result.unmatched_employees,
        unmatched_excel_names=result.unmatched_excel_names,
        warnings=result.warnings,
    )


@app.get("/api/admin/periods/{period_id}/export-bonus")
def admin_export_bonus(
    period_id: UUID,
    admin: Annotated[User, Depends(require_admin)],
    db: Session = Depends(get_db),
    facility: str = "inaha",
):
    if not settings.bonus_workbook_template_path.strip():
        raise HTTPException(
            status_code=400,
            detail="BONUS_WORKBOOK_TEMPLATE_PATH が未設定です（.env に賞与 Excel のパスを設定してください）",
        )
    period = db.get(EvaluationPeriod, period_id)
    if not period:
        raise HTTPException(status_code=404, detail="考課期間が見つかりません")
    employee = db.query(Employee).filter(Employee.user_id == admin.id).first()
    facility = _require_facility_access(facility, admin, employee)
    try:
        data, result = reflect_evaluations_to_bonus_workbook(
            db, period, facility_key=facility, dry_run=False
        )
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    template_path = Path(settings.bonus_workbook_template_path.strip())
    stem = template_path.stem
    filename = f"{stem}_考課反映.xlsx"
    db.add(
        AuditLog(
            user_id=admin.id,
            action="export_bonus",
            target_type="period",
            target_id=period.id,
            detail={
                "filename": filename,
                "facility": result.facility,
                "updated_rows": result.updated_rows,
                "unmatched": len(result.unmatched_employees),
            },
        )
    )
    db.commit()

    ascii_filename = "bonus_reflect.xlsx"
    encoded_filename = quote(filename)
    return StreamingResponse(
        BytesIO(data),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": (
                f'attachment; filename="{ascii_filename}"; filename*=UTF-8\'\'{encoded_filename}'
            )
        },
    )


@app.get("/api/admin/periods/{period_id}/export")
def admin_export_period(
    period_id: UUID,
    admin: Annotated[User, Depends(require_admin)],
    db: Session = Depends(get_db),
):
    period = db.get(EvaluationPeriod, period_id)
    if not period:
        raise HTTPException(status_code=404, detail="考課期間が見つかりません")

    self_template = load_self_template()
    assessment_template = load_assessment_template()
    if period.self_eval_template_id:
        tpl = db.get(FormTemplate, period.self_eval_template_id)
        if tpl:
            self_template = tpl.content
    if period.assessment_template_id:
        tpl = db.get(FormTemplate, period.assessment_template_id)
        if tpl:
            assessment_template = tpl.content
    director_self_template = load_facility_director_self_template()
    director_assessment_template = load_facility_director_assessment_template()
    if period.facility_director_self_eval_template_id:
        tpl = db.get(FormTemplate, period.facility_director_self_eval_template_id)
        if tpl:
            director_self_template = tpl.content
    if period.facility_director_assessment_template_id:
        tpl = db.get(FormTemplate, period.facility_director_assessment_template_id)
        if tpl:
            director_assessment_template = tpl.content

    data, filename = build_period_export(
        db,
        period,
        self_template,
        assessment_template,
        director_self_template,
        director_assessment_template,
    )
    db.add(
        AuditLog(
            user_id=admin.id,
            action="export",
            target_type="period",
            target_id=period.id,
            detail={"filename": filename},
        )
    )
    db.commit()

    ascii_filename = "hyouka_export.xlsx"
    encoded_filename = quote(filename)
    return StreamingResponse(
        BytesIO(data),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": (
                f'attachment; filename="{ascii_filename}"; filename*=UTF-8\'\'{encoded_filename}'
            )
        },
    )
