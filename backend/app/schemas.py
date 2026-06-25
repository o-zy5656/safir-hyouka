from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field

from app.models import PeriodSeason, PeriodStatus, SubmissionStatus, UserRole


class LoginRequest(BaseModel):
    employee_id: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: UUID
    employee_id: str
    role: UserRole
    name: Optional[str] = None
    must_change_password: bool = False

    class Config:
        from_attributes = True


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


class AdminUserItem(BaseModel):
    user_id: UUID
    employee_id: str
    name: Optional[str] = None
    role: UserRole
    is_active: bool


class UpdateUserRoleRequest(BaseModel):
    role: UserRole


class EmployeeAttributes(BaseModel):
    employee_id: str
    name: str
    assignment: str
    job_type: str
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
    errors: List[str]
