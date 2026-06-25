from datetime import datetime, timedelta
from io import BytesIO
from typing import Annotated, List, Optional
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
    ChangePasswordRequest,
    EmployeeAttributes,
    EvaluatorWorkspaceResponse,
    ImportResultResponse,
    LoginRequest,
    PeriodCreateRequest,
    PeriodResponse,
    ReturnRequest,
    SaveFormRequest,
    SubmissionPanel,
    TokenResponse,
    UpdateUserRoleRequest,
    UserResponse,
    WorkspaceResponse,
)
from app.services.employee_import import import_employees_from_excel
from app.services.excel_export import build_period_export
from app.services.form_validation import validate_form_data
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
    if user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="管理者のみアクセスできます")
    return user


def employee_attrs(employee: Employee) -> EmployeeAttributes:
    return EmployeeAttributes(
        employee_id=employee.employee_id,
        name=employee.name,
        assignment=employee.assignment,
        job_type=employee.job_type,
        years_of_service=employee.years_of_service,
    )


def get_active_period(db: Session) -> Optional[EvaluationPeriod]:
    return db.query(EvaluationPeriod).filter(EvaluationPeriod.status == PeriodStatus.ACTIVE).first()


def load_self_template():
    from pathlib import Path

    return load_template_file(Path(TEMPLATES_DIR) / "self_evaluation_r8_summer.json")


def load_assessment_template():
    from pathlib import Path

    return load_template_file(Path(TEMPLATES_DIR) / "assessment_r8_summer.json")


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


def evaluator_can_edit(evaluation: Evaluation, is_eval1: bool) -> bool:
    if evaluation.self_eval_status != SubmissionStatus.SUBMITTED:
        return False
    if is_eval1:
        return evaluation.eval1_status in {SubmissionStatus.DRAFT, SubmissionStatus.RETURNED}
    if evaluation.eval1_status != SubmissionStatus.SUBMITTED:
        return False
    return evaluation.eval2_status in {SubmissionStatus.DRAFT, SubmissionStatus.RETURNED}


def build_evaluator_reference(evaluation: Evaluation, is_eval1: bool) -> dict:
    reference = {
        "self_evaluation": {
            "scores": evaluation.self_eval_data.get("scores", {}),
            "text_fields": evaluation.self_eval_data.get("text_fields", {}),
        }
    }
    if not is_eval1 and evaluation.eval1_status == SubmissionStatus.SUBMITTED:
        reference["evaluator1"] = {
            "scores": evaluation.eval1_data.get("scores", {}),
            "text_fields": evaluation.eval1_data.get("text_fields", {}),
        }
    return reference


@app.on_event("startup")
def on_startup():
    create_tables()
    if settings.auto_seed_demo:
        from scripts.seed_demo import seed

        seed()


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.post("/api/auth/login", response_model=TokenResponse)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.employee_id == form_data.username).first()
    if not user or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="社員IDまたはパスワードが正しくありません")
    return TokenResponse(access_token=create_access_token(str(user.id)))


@app.get("/api/auth/me", response_model=UserResponse)
def me(user: Annotated[User, Depends(get_current_user)], db: Session = Depends(get_db)):
    employee = db.query(Employee).filter(Employee.user_id == user.id).first()
    return UserResponse(
        id=user.id,
        employee_id=user.employee_id,
        role=user.role,
        name=employee.name if employee else None,
        must_change_password=user.must_change_password,
    )


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
    if user.role != UserRole.EMPLOYEE:
        raise HTTPException(status_code=403, detail="本人のみアクセスできます")

    employee = db.query(Employee).filter(Employee.user_id == user.id).first()
    if not employee:
        raise HTTPException(status_code=404, detail="社員情報が見つかりません")

    period = get_active_period(db)
    evaluation = None
    if period:
        evaluation = (
            db.query(Evaluation)
            .filter(Evaluation.period_id == period.id, Evaluation.employee_id == employee.id)
            .first()
        )

    status_value = evaluation.self_eval_status if evaluation else SubmissionStatus.DRAFT
    return WorkspaceResponse(
        period_name=period.name if period else None,
        attributes=employee_attrs(employee),
        template=load_self_template(),
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

    employee = db.query(Employee).filter(Employee.user_id == user.id).first()
    period = get_active_period(db)
    if not employee or not period:
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

    employee = db.query(Employee).filter(Employee.user_id == user.id).first()
    period = get_active_period(db)
    evaluation = (
        db.query(Evaluation)
        .filter(Evaluation.period_id == period.id, Evaluation.employee_id == employee.id)
        .first()
    )
    if not evaluation:
        raise HTTPException(status_code=400, detail="保存してから提出してください")

    template = load_self_template()
    errors = validate_form_data(template, evaluation.self_eval_data)
    if errors:
        raise HTTPException(
            status_code=400,
            detail={"message": "未入力の項目があるため提出できません", "errors": errors},
        )

    evaluation.self_eval_status = SubmissionStatus.SUBMITTED
    evaluation.self_eval_submitted_at = datetime.utcnow()
    evaluation.eval1_status = SubmissionStatus.DRAFT
    db.commit()
    return {"ok": True}


@app.post("/api/me/self-evaluation/unsubmit")
def unsubmit_self_evaluation(user: Annotated[User, Depends(get_current_user)], db: Session = Depends(get_db)):
    if not settings.dev_allow_unsubmit:
        raise HTTPException(status_code=403, detail="この操作は開発環境でのみ利用できます")

    if user.role != UserRole.EMPLOYEE:
        raise HTTPException(status_code=403, detail="本人のみ利用できます")

    employee = db.query(Employee).filter(Employee.user_id == user.id).first()
    period = get_active_period(db)
    if not employee or not period:
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
    field = "evaluator1_id" if user.role == UserRole.EVALUATOR1 else "evaluator2_id"
    subordinates = db.query(Employee).filter(getattr(Employee, field) == evaluator.id).all()

    assignments: list[AssignmentSummary] = []
    for sub in subordinates:
        ev = None
        if period:
            ev = (
                db.query(Evaluation)
                .filter(Evaluation.period_id == period.id, Evaluation.employee_id == sub.id)
                .first()
            )
        my_status = (ev.eval1_status if user.role == UserRole.EVALUATOR1 else ev.eval2_status) if ev else SubmissionStatus.PENDING
        assignments.append(
            AssignmentSummary(
                evaluation_id=ev.id if ev else UUID(int=0),
                employee=employee_attrs(sub),
                self_eval_status=ev.self_eval_status if ev else SubmissionStatus.PENDING,
                eval1_status=ev.eval1_status if ev else SubmissionStatus.PENDING,
                eval2_status=ev.eval2_status if ev else SubmissionStatus.PENDING,
                my_status=my_status,
            )
        )

    return EvaluatorWorkspaceResponse(period_name=period.name if period else None, assignments=assignments)


def _get_evaluator_assignment(
    evaluation_id: UUID,
    user: User,
    db: Session,
) -> tuple[Evaluation, Employee, EvaluationPeriod, bool]:
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
    field = "evaluator1_id" if is_eval1 else "evaluator2_id"
    if getattr(employee, field) != evaluator.id:
        raise HTTPException(status_code=403, detail="担当外の考課です")

    return evaluation, employee, period, is_eval1


@app.get("/api/evaluator/assignments/{evaluation_id}", response_model=EvaluatorWorkspaceResponse)
def evaluator_assignment_detail(
    evaluation_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    db: Session = Depends(get_db),
):
    base = evaluator_workspace(user, db)
    evaluation, employee, period, is_eval1 = _get_evaluator_assignment(evaluation_id, user, db)

    if evaluation.self_eval_status != SubmissionStatus.SUBMITTED:
        raise HTTPException(status_code=400, detail="本人の自己評価提出後に参照できます")

    template = load_assessment_template()
    my_data = evaluation.eval1_data if is_eval1 else evaluation.eval2_data
    my_status = evaluation.eval1_status if is_eval1 else evaluation.eval2_status
    deadline = period.eval1_deadline if is_eval1 else period.eval2_deadline
    submitted_at = evaluation.eval1_submitted_at if is_eval1 else evaluation.eval2_submitted_at
    can_edit = evaluator_can_edit(evaluation, is_eval1)

    base.selected = WorkspaceResponse(
        period_name=period.name,
        attributes=employee_attrs(employee),
        template=template,
        form_data=merge_assessment_display_data(template, my_data, evaluation.self_eval_data),
        submission=SubmissionPanel(
            status=my_status,
            deadline=deadline,
            submitted_at=submitted_at,
            can_edit=can_edit,
            can_submit=can_edit and my_status in {SubmissionStatus.DRAFT, SubmissionStatus.RETURNED},
        ),
    )
    base.reference = build_evaluator_reference(evaluation, is_eval1)
    return base


@app.put("/api/evaluator/assignments/{evaluation_id}")
def save_evaluator_assignment(
    evaluation_id: UUID,
    body: SaveFormRequest,
    user: Annotated[User, Depends(get_current_user)],
    db: Session = Depends(get_db),
):
    evaluation, employee, period, is_eval1 = _get_evaluator_assignment(evaluation_id, user, db)

    if not evaluator_can_edit(evaluation, is_eval1):
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
    evaluation, employee, period, is_eval1 = _get_evaluator_assignment(evaluation_id, user, db)

    if not evaluator_can_edit(evaluation, is_eval1):
        raise HTTPException(status_code=400, detail="現在は提出できません")

    my_status = evaluation.eval1_status if is_eval1 else evaluation.eval2_status
    if my_status not in {SubmissionStatus.DRAFT, SubmissionStatus.RETURNED}:
        raise HTTPException(status_code=400, detail="提出できません")

    template = load_assessment_template()
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
        if not employee:
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
    for employee in db.query(Employee).all():
        if employee.id in existing_ids:
            continue
        db.add(Evaluation(period_id=period.id, employee_id=employee.id))
        created += 1
    return created


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
    db.add_all([self_tpl, assess_tpl])
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


@app.get("/api/admin/users", response_model=List[AdminUserItem])
def admin_list_users(
    admin: Annotated[User, Depends(require_admin)],
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

    data, filename = build_period_export(db, period, self_template, assessment_template)
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

    return StreamingResponse(
        BytesIO(data),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
