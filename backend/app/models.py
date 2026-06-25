import enum
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.types import Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class UserRole(str, enum.Enum):
    EMPLOYEE = "employee"
    EVALUATOR1 = "evaluator1"
    EVALUATOR2 = "evaluator2"
    ADMIN = "admin"


class PeriodSeason(str, enum.Enum):
    SUMMER = "summer"
    WINTER = "winter"


class PeriodStatus(str, enum.Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    CLOSED = "closed"


class TemplateType(str, enum.Enum):
    SELF_EVALUATION = "self_evaluation"
    ASSESSMENT = "assessment"


class SubmissionStatus(str, enum.Enum):
    PENDING = "pending"
    DRAFT = "draft"
    SUBMITTED = "submitted"
    RETURNED = "returned"


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    employee_id: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[UserRole] = mapped_column(Enum(UserRole))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=False)

    employee: Mapped["Employee | None"] = relationship(back_populates="user", uselist=False)


class Employee(Base):
    __tablename__ = "employees"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    employee_id: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(100))
    assignment: Mapped[str] = mapped_column(String(100))
    job_type: Mapped[str] = mapped_column(String(100))
    years_of_service: Mapped[int] = mapped_column(Integer, default=0)
    evaluator1_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid(as_uuid=True), ForeignKey("employees.id"))
    evaluator2_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid(as_uuid=True), ForeignKey("employees.id"))
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id"))

    user: Mapped[Optional[User]] = relationship(back_populates="employee")
    evaluator1: Mapped["Employee | None"] = relationship(foreign_keys=[evaluator1_id], remote_side=[id])
    evaluator2: Mapped["Employee | None"] = relationship(foreign_keys=[evaluator2_id], remote_side=[id])


class FormTemplate(Base):
    __tablename__ = "form_templates"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    type: Mapped[TemplateType] = mapped_column(Enum(TemplateType))
    version: Mapped[str] = mapped_column(String(20))
    name: Mapped[str] = mapped_column(String(200))
    content: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class EvaluationPeriod(Base):
    __tablename__ = "evaluation_periods"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(200))
    season: Mapped[PeriodSeason] = mapped_column(Enum(PeriodSeason))
    fiscal_year: Mapped[int] = mapped_column(Integer)
    self_eval_deadline: Mapped[Optional[datetime]] = mapped_column(DateTime)
    eval1_deadline: Mapped[Optional[datetime]] = mapped_column(DateTime)
    eval2_deadline: Mapped[Optional[datetime]] = mapped_column(DateTime)
    self_eval_template_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid(as_uuid=True), ForeignKey("form_templates.id"))
    assessment_template_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid(as_uuid=True), ForeignKey("form_templates.id"))
    status: Mapped[PeriodStatus] = mapped_column(Enum(PeriodStatus), default=PeriodStatus.DRAFT)


class Evaluation(Base):
    __tablename__ = "evaluations"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    period_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("evaluation_periods.id"))
    employee_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("employees.id"))
    self_eval_status: Mapped[SubmissionStatus] = mapped_column(Enum(SubmissionStatus), default=SubmissionStatus.DRAFT)
    eval1_status: Mapped[SubmissionStatus] = mapped_column(Enum(SubmissionStatus), default=SubmissionStatus.PENDING)
    eval2_status: Mapped[SubmissionStatus] = mapped_column(Enum(SubmissionStatus), default=SubmissionStatus.PENDING)
    self_eval_data: Mapped[dict] = mapped_column(JSON, default=dict)
    eval1_data: Mapped[dict] = mapped_column(JSON, default=dict)
    eval2_data: Mapped[dict] = mapped_column(JSON, default=dict)
    self_eval_submitted_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    eval1_submitted_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    eval2_submitted_at: Mapped[Optional[datetime]] = mapped_column(DateTime)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id"))
    action: Mapped[str] = mapped_column(String(50))
    target_type: Mapped[str] = mapped_column(String(50))
    target_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid(as_uuid=True))
    detail: Mapped[Optional[dict]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    note: Mapped[Optional[str]] = mapped_column(Text)
