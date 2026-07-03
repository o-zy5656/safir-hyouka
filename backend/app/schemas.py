from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field

from app.models import EmploymentStatus, PeriodSeason, PeriodStatus, SubmissionStatus, UserRole


class LoginRequest(BaseModel):
    employee_id: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class DemoLoginRequest(BaseModel):
    employee_id: Optional[str] = None


class DemoPersonaItem(BaseModel):
    employee_id: str
    label: str
    name: Optional[str] = None


class DemoPersonasResponse(BaseModel):
    personas: List[DemoPersonaItem]
    default_employee_id: str


class UserResponse(BaseModel):
    id: UUID
    employee_id: str
    role: UserRole
    name: Optional[str] = None
    must_change_password: bool = False
    is_admin: bool = False
    is_hq_evaluator: bool = False
    has_facility_director_self_eval: bool = False
    has_own_self_eval: bool = False
    can_access_bonus_workbook: bool = False
    can_reset_user_passwords: bool = False
    facility_key: Optional[str] = None
    facility_label: Optional[str] = None

    class Config:
        from_attributes = True


class FacilityItem(BaseModel):
    key: str
    label: str
    assignment_match: str
    enabled: bool = True
    bonus_enabled: bool = False


class FacilitiesListResponse(BaseModel):
    facilities: List[FacilityItem]


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


class AdminUserItem(BaseModel):
    user_id: UUID
    employee_id: str
    name: Optional[str] = None
    role: UserRole
    is_active: bool


class ResetPasswordResponse(BaseModel):
    ok: bool = True
    message: str
    employee_id: str
    temporary_password: str


class UpdateUserRoleRequest(BaseModel):
    role: UserRole


class EmployeeAttributes(BaseModel):
    employee_id: str
    name: str
    assignment: str
    job_type: str
    job_title: Optional[str] = None
    years_of_service: int


class SubmissionPanel(BaseModel):
    status: SubmissionStatus
    deadline: Optional[datetime]
    submitted_at: Optional[datetime]
    can_edit: bool
    can_submit: bool


class WorkspaceResponse(BaseModel):
    period_name: Optional[str]
    attributes: EmployeeAttributes
    template: Dict[str, Any]
    form_data: Dict[str, Any] = Field(default_factory=dict)
    submission: SubmissionPanel


class AssignmentSummary(BaseModel):
    evaluation_id: UUID
    employee: EmployeeAttributes
    self_eval_status: SubmissionStatus
    eval1_status: SubmissionStatus
    eval2_status: SubmissionStatus
    my_status: SubmissionStatus
    uses_facility_director_form: bool = False
    skips_eval1: bool = False
    hq_review_only: bool = False


class EvaluatorWorkspaceResponse(BaseModel):
    period_name: Optional[str]
    assignments: List[AssignmentSummary]
    selected: Optional[WorkspaceResponse] = None
    reference: Dict[str, Any] = Field(default_factory=dict)


class SaveFormRequest(BaseModel):
    data: Dict[str, Any]


class PeriodCreateRequest(BaseModel):
    name: str
    season: PeriodSeason
    fiscal_year: int
    self_eval_deadline: Optional[datetime] = None
    eval1_deadline: Optional[datetime] = None
    eval2_deadline: Optional[datetime] = None


class ReturnRequest(BaseModel):
    target: str
    reason: Optional[str] = None


class AdminEvaluationItem(BaseModel):
    evaluation_id: UUID
    employee: EmployeeAttributes
    self_eval_status: SubmissionStatus
    eval1_status: SubmissionStatus
    eval2_status: SubmissionStatus


class PeriodResponse(BaseModel):
    id: UUID
    name: str
    season: PeriodSeason
    fiscal_year: int
    status: PeriodStatus
    self_eval_deadline: Optional[datetime] = None
    eval1_deadline: Optional[datetime] = None
    eval2_deadline: Optional[datetime] = None

    class Config:
        from_attributes = True


class ImportResultResponse(BaseModel):
    created: int
    updated: int
    users_created: int
    evaluations_created: int
    roles_updated: int = 0
    skipped: int = 0
    errors: List[str]


class BonusReflectResultResponse(BaseModel):
    facility: str
    updated_rows: int
    matched_employees: List[str]
    unmatched_employees: List[str]
    unmatched_excel_names: List[str]
    warnings: List[str]


class BonusWorkbookRow(BaseModel):
    row_number: int
    employee_id: Optional[str] = None
    name: str
    job_title: str = ""
    facility_label: Optional[str] = None
    bonus_facility_key: Optional[str] = None
    self_score: Optional[int] = None
    eval1_score: Optional[int] = None
    eval2_score: Optional[int] = None
    final_score: Optional[int] = None
    low_self_count: Optional[int] = None
    low_other_count: Optional[int] = None
    cut_self_items: Optional[str] = None
    cut_other_items: Optional[str] = None
    promotion_reference: Optional[str] = None
    is_role_holder: bool = False
    salary_raise: Optional[str] = None
    rank_order: Optional[int] = None
    rank_grade: Optional[str] = None
    note: str = ""
    proposed_bonus_amount: Optional[int] = None
    bonus_amount: Optional[int] = None
    prior_summer_amount: Optional[int] = None
    prior_winter_amount: Optional[int] = None


class BonusWorkbookSummary(BaseModel):
    total_proposed: int = 0
    total_bonus: int = 0
    total_with_social_insurance: int = 0
    provision_monthly: int = 0
    provision_months: int = 12
    provision_total: int = 0
    difference: int = 0
    social_insurance_rate: float = 0.15


class BonusWorkbookResponse(BaseModel):
    facility: str
    facility_key: str
    period_name: Optional[str] = None
    template_configured: bool
    bonus_sheet_available: bool = True
    fiscal_year: int
    current_fiscal_year: int
    available_fiscal_years: List[int]
    read_only: bool = False
    provision_monthly: int = 0
    provision_months: int = 12
    summary: BonusWorkbookSummary
    rows: List[BonusWorkbookRow]


class BonusWorkbookSaveRequest(BaseModel):
    rows: List[BonusWorkbookRow]
    provision_monthly: Optional[int] = None
    provision_months: Optional[int] = None


class BonusAmountsRowPayload(BaseModel):
    employee_id: str
    bonus_facility_key: Optional[str] = None
    proposed_bonus_amount: Optional[int] = None
    bonus_amount: Optional[int] = None
    prior_summer_amount: Optional[int] = None
    prior_winter_amount: Optional[int] = None


class BonusAmountsSaveRequest(BaseModel):
    rows: List[BonusAmountsRowPayload]
    provision_monthly: Optional[int] = None
    provision_months: Optional[int] = None


class BonusAmountsSaveResponse(BaseModel):
    ok: bool = True
    provision_monthly: int = 0
    provision_months: int = 12
    summary: BonusWorkbookSummary


class EmployeeListItem(BaseModel):
    id: UUID
    employee_id: str
    name: str
    assignment: str
    job_type: str
    job_title: Optional[str] = None
    years_of_service: int
    employment_status: EmploymentStatus
    evaluator1_employee_id: Optional[str] = None
    evaluator1_name: Optional[str] = None
    evaluator2_employee_id: Optional[str] = None
    evaluator2_name: Optional[str] = None


class CreateEmployeeRequest(BaseModel):
    employee_id: str
    name: str
    assignment: str
    job_type: str
    job_title: str = "一般"
    years_of_service: int = 0
    evaluator1_employee_id: Optional[str] = None
    evaluator2_employee_id: Optional[str] = None


class RetireEmployeeRequest(BaseModel):
    reason: Optional[str] = None


class EmployeeActionResponse(BaseModel):
    ok: bool = True
    message: str
    employee_id: str
    name: str
    archive_id: Optional[str] = None
    warnings: List[str] = Field(default_factory=list)


class RetiredArchiveItem(BaseModel):
    archive_id: str
    employee_id: Optional[str] = None
    employee_name: Optional[str] = None
    retired_at: Optional[str] = None
    json_filename: str
    xlsx_filename: Optional[str] = None


class EmployeeOptionsResponse(BaseModel):
    job_types: List[str]
    job_titles: List[str]
