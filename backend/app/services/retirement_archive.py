"""退職者データのアーカイブ作成・保管。"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Any, Optional
from uuid import UUID

from openpyxl import Workbook
from openpyxl.styles import Font
from sqlalchemy.orm import Session

from app.models import Employee, EmploymentStatus, Evaluation, EvaluationPeriod, User

STATUS_LABELS = {
    "pending": "未着手",
    "draft": "下書き",
    "submitted": "提出済",
    "returned": "差戻",
}


@dataclass
class ArchiveFiles:
    archive_id: str
    json_path: Path
    xlsx_path: Path
    retired_at: datetime


def _safe_part(text: str) -> str:
    cleaned = re.sub(r"[^\w\-]+", "_", text.replace("\u3000", " ").strip())
    return cleaned.strip("_")[:40] or "unknown"


def _employee_snapshot(employee: Employee) -> dict[str, Any]:
    ev1 = employee.evaluator1
    ev2 = employee.evaluator2
    return {
        "id": str(employee.id),
        "employee_id": employee.employee_id,
        "name": employee.name,
        "assignment": employee.assignment,
        "job_type": employee.job_type,
        "job_title": employee.job_title,
        "years_of_service": employee.years_of_service,
        "evaluator1_employee_id": ev1.employee_id if ev1 else None,
        "evaluator1_name": ev1.name if ev1 else None,
        "evaluator2_employee_id": ev2.employee_id if ev2 else None,
        "evaluator2_name": ev2.name if ev2 else None,
    }


def _user_snapshot(user: Optional[User]) -> Optional[dict[str, Any]]:
    if not user:
        return None
    return {
        "employee_id": user.employee_id,
        "role": user.role.value,
        "is_admin": user.is_admin,
        "is_hq_evaluator": user.is_hq_evaluator,
    }


def build_retirement_archive_payload(
    db: Session,
    employee: Employee,
    reason: Optional[str] = None,
) -> dict[str, Any]:
    user = db.query(User).filter(User.id == employee.user_id).first() if employee.user_id else None
    evaluations = db.query(Evaluation).filter(Evaluation.employee_id == employee.id).all()
    period_map = {p.id: p for p in db.query(EvaluationPeriod).all()}

    eval_rows = []
    for ev in evaluations:
        period = period_map.get(ev.period_id)
        eval_rows.append(
            {
                "period_id": str(ev.period_id),
                "period_name": period.name if period else None,
                "period_status": period.status.value if period else None,
                "self_eval_status": ev.self_eval_status.value,
                "eval1_status": ev.eval1_status.value,
                "eval2_status": ev.eval2_status.value,
                "self_eval_submitted_at": ev.self_eval_submitted_at.isoformat()
                if ev.self_eval_submitted_at
                else None,
                "eval1_submitted_at": ev.eval1_submitted_at.isoformat() if ev.eval1_submitted_at else None,
                "eval2_submitted_at": ev.eval2_submitted_at.isoformat() if ev.eval2_submitted_at else None,
                "self_eval_data": ev.self_eval_data,
                "eval1_data": ev.eval1_data,
                "eval2_data": ev.eval2_data,
            }
        )

    as_eval1 = (
        db.query(Employee)
        .filter(
            Employee.evaluator1_id == employee.id,
            Employee.employment_status == EmploymentStatus.ACTIVE,
        )
        .all()
    )
    as_eval2 = (
        db.query(Employee)
        .filter(
            Employee.evaluator2_id == employee.id,
            Employee.employment_status == EmploymentStatus.ACTIVE,
        )
        .all()
    )

    return {
        "archived_at": datetime.utcnow().isoformat(),
        "retirement_reason": reason,
        "employee": _employee_snapshot(employee),
        "user": _user_snapshot(user),
        "evaluations": eval_rows,
        "active_subordinates_as_evaluator1": [
            {"employee_id": e.employee_id, "name": e.name} for e in as_eval1
        ],
        "active_subordinates_as_evaluator2": [
            {"employee_id": e.employee_id, "name": e.name} for e in as_eval2
        ],
    }


def _build_xlsx(payload: dict[str, Any]) -> bytes:
    wb = Workbook()
    info = wb.active
    info.title = "職員情報"
    info.append(["項目", "内容"])
    emp = payload["employee"]
    for key, label in [
        ("employee_id", "社員ID"),
        ("name", "氏名"),
        ("assignment", "配属"),
        ("job_type", "職種"),
        ("job_title", "役職"),
        ("years_of_service", "勤続年数"),
        ("evaluator1_employee_id", "評価者1 ID"),
        ("evaluator1_name", "評価者1 氏名"),
        ("evaluator2_employee_id", "評価者2 ID"),
        ("evaluator2_name", "評価者2 氏名"),
    ]:
        info.append([label, emp.get(key)])
    info.append(["退職処理日時", payload.get("archived_at")])
    info.append(["退職理由", payload.get("retirement_reason") or ""])
    for cell in info[1]:
        cell.font = Font(bold=True)

    ev_sheet = wb.create_sheet("考課履歴")
    ev_sheet.append(
        [
            "考課期間",
            "自己評価",
            "評価者1",
            "評価者2",
            "自己提出日",
            "評1提出日",
            "評2提出日",
        ]
    )
    for cell in ev_sheet[1]:
        cell.font = Font(bold=True)
    for row in payload.get("evaluations", []):
        ev_sheet.append(
            [
                row.get("period_name"),
                STATUS_LABELS.get(row.get("self_eval_status", ""), row.get("self_eval_status")),
                STATUS_LABELS.get(row.get("eval1_status", ""), row.get("eval1_status")),
                STATUS_LABELS.get(row.get("eval2_status", ""), row.get("eval2_status")),
                row.get("self_eval_submitted_at"),
                row.get("eval1_submitted_at"),
                row.get("eval2_submitted_at"),
            ]
        )

    buffer = BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


def save_retirement_archive(
    archives_dir: str,
    employee: Employee,
    payload: dict[str, Any],
    retired_at: Optional[datetime] = None,
) -> ArchiveFiles:
    retired_at = retired_at or datetime.utcnow()
    stamp = retired_at.strftime("%Y%m%d_%H%M%S")
    archive_id = f"{employee.employee_id}_{_safe_part(employee.name)}_{stamp}"

    base = Path(archives_dir)
    base.mkdir(parents=True, exist_ok=True)

    json_path = base / f"{archive_id}.json"
    xlsx_path = base / f"{archive_id}.xlsx"

    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    xlsx_path.write_bytes(_build_xlsx(payload))

    return ArchiveFiles(
        archive_id=archive_id,
        json_path=json_path,
        xlsx_path=xlsx_path,
        retired_at=retired_at,
    )


def list_retirement_archives(archives_dir: str) -> list[dict[str, Any]]:
    base = Path(archives_dir)
    if not base.exists():
        return []

    archives: list[dict[str, Any]] = []
    for json_path in sorted(base.glob("*.json"), reverse=True):
        archive_id = json_path.stem
        xlsx_path = base / f"{archive_id}.xlsx"
        item: dict[str, Any] = {
            "archive_id": archive_id,
            "json_filename": json_path.name,
            "xlsx_filename": xlsx_path.name if xlsx_path.exists() else None,
            "retired_at": None,
            "employee_id": None,
            "employee_name": None,
        }
        try:
            data = json.loads(json_path.read_text(encoding="utf-8"))
            item["retired_at"] = data.get("archived_at")
            emp = data.get("employee") or {}
            item["employee_id"] = emp.get("employee_id")
            item["employee_name"] = emp.get("name")
        except (json.JSONDecodeError, OSError):
            parts = archive_id.split("_")
            if parts:
                item["employee_id"] = parts[0]
        archives.append(item)
    return archives


def resolve_archive_path(archives_dir: str, archive_id: str, file_type: str) -> Path:
    if ".." in archive_id or "/" in archive_id or "\\" in archive_id:
        raise ValueError("不正なアーカイブIDです")
    ext = "json" if file_type == "json" else "xlsx"
    path = Path(archives_dir) / f"{archive_id}.{ext}"
    if not path.exists():
        raise FileNotFoundError(str(path))
    return path
