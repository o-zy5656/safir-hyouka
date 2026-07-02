"""賞与金額（案）・確定賞与・引当金設定の永続化と集計（年度別）。"""

from __future__ import annotations

from datetime import date
from decimal import Decimal, ROUND_HALF_UP
import json
from pathlib import Path
from typing import Any, Optional

from app.config import settings
from app.services.facilities import (
    get_facility,
    is_facility_directors_bonus_key,
)

_BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
DEFAULT_PROVISION_MONTHS = 12
ALLOWED_PROVISION_MONTHS = (6, 12)
AMOUNT_UNIT = "sen_yen"
YEN_LEGACY_THRESHOLD = 10_000
WORKBOOK_ROW_FIELDS = (
    "self_score",
    "eval1_score",
    "eval2_score",
    "rank_order",
    "rank_grade",
    "note",
)


def normalize_provision_months(months: Optional[int]) -> int:
    if months in ALLOWED_PROVISION_MONTHS:
        return int(months)
    return DEFAULT_PROVISION_MONTHS


def default_fiscal_year() -> int:
    return date.today().year


def _read_row_amount_fields(amounts: dict[str, Any]) -> dict[str, Any]:
    data = {
        "proposed_bonus_amount": amounts.get("proposed_bonus_amount"),
        "bonus_amount": amounts.get("bonus_amount"),
        "prior_summer_amount": amounts.get("prior_summer_amount"),
        "prior_winter_amount": amounts.get("prior_winter_amount"),
    }
    for field in WORKBOOK_ROW_FIELDS:
        if field in amounts:
            data[field] = amounts[field]
    return data


def _migrate_row_amount_fields(amounts: dict[str, Any]) -> dict[str, Any]:
    return {
        "proposed_bonus_amount": _to_sen_yen(amounts.get("proposed_bonus_amount")),
        "bonus_amount": _to_sen_yen(amounts.get("bonus_amount")),
        "prior_summer_amount": _to_sen_yen(amounts.get("prior_summer_amount")),
        "prior_winter_amount": _to_sen_yen(amounts.get("prior_winter_amount")),
    }


def _merge_row_amount_entry(
    item: dict[str, Any],
    prev: dict[str, Any],
    *,
    allow_proposed: bool,
    allow_bonus: bool,
) -> dict[str, Any]:
    return {
        "proposed_bonus_amount": (
            item.get("proposed_bonus_amount")
            if allow_proposed
            else prev.get("proposed_bonus_amount")
        ),
        "bonus_amount": item.get("bonus_amount") if allow_bonus else prev.get("bonus_amount"),
        "prior_summer_amount": (
            item.get("prior_summer_amount")
            if allow_bonus
            else prev.get("prior_summer_amount")
        ),
        "prior_winter_amount": (
            item.get("prior_winter_amount")
            if allow_bonus
            else prev.get("prior_winter_amount")
        ),
    }


def _to_sen_yen(value: Any) -> Optional[int]:
    if value in (None, ""):
        return None
    amount = int(value)
    if amount >= YEN_LEGACY_THRESHOLD:
        return amount // 1000
    return amount


def _amounts_dir() -> Path:
    path = _BACKEND_DIR / "data" / "bonus_amounts"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _amounts_path(facility_key: str) -> Path:
    return _amounts_dir() / f"{facility_key}.json"


def default_provision_for_facility(facility_key: str) -> tuple[int, int]:
    """(月額千円, 月数) のデフォルト。facilities.json の bonus.provision_* を参照。"""
    if is_facility_directors_bonus_key(facility_key):
        return 0, DEFAULT_PROVISION_MONTHS
    try:
        facility = get_facility(facility_key)
    except ValueError:
        return 0, DEFAULT_PROVISION_MONTHS
    bonus = _read_facility_bonus_defaults(facility.key)
    return bonus["provision_monthly"], bonus["provision_months"]


def _read_facility_bonus_defaults(facility_key: str) -> dict[str, int]:
    from app.services.facilities import _facilities_config_path

    path = _facilities_config_path()
    if not path.exists():
        return {"provision_monthly": 0, "provision_months": DEFAULT_PROVISION_MONTHS}
    data = json.loads(path.read_text(encoding="utf-8"))
    for raw in data.get("facilities") or []:
        if str(raw.get("key", "")).strip() != facility_key:
            continue
        bonus = raw.get("bonus")
        if not isinstance(bonus, dict):
            break
        monthly = bonus.get("provision_monthly")
        months = bonus.get("provision_months", DEFAULT_PROVISION_MONTHS)
        return {
            "provision_monthly": _to_sen_yen(monthly) or 0,
            "provision_months": normalize_provision_months(
                int(months) if months not in (None, "") else DEFAULT_PROVISION_MONTHS
            ),
        }
    return {"provision_monthly": 0, "provision_months": DEFAULT_PROVISION_MONTHS}


def _normalize_year_entry(entry: dict[str, Any], facility_key: str) -> dict[str, Any]:
    defaults = default_provision_for_facility(facility_key)
    rows = entry.get("rows") if isinstance(entry.get("rows"), dict) else {}
    return {
        "provision_monthly": int(entry.get("provision_monthly", defaults[0])),
        "provision_months": normalize_provision_months(entry.get("provision_months")),
        "rows": rows,
    }


def _migrate_store(raw: dict[str, Any], facility_key: str, default_year: int) -> dict[str, Any]:
    if isinstance(raw.get("years"), dict):
        years: dict[str, Any] = {}
        for year_key, entry in raw["years"].items():
            if isinstance(entry, dict):
                years[str(int(year_key))] = _normalize_year_entry(entry, facility_key)
        return {"amount_unit": AMOUNT_UNIT, "years": years}

    if raw.get("amount_unit") == AMOUNT_UNIT or raw.get("rows") or raw.get("provision_monthly") is not None:
        entry = {
            "provision_monthly": _to_sen_yen(raw.get("provision_monthly")) or 0,
            "provision_months": normalize_provision_months(raw.get("provision_months")),
            "rows": raw.get("rows") if isinstance(raw.get("rows"), dict) else {},
        }
        if raw.get("amount_unit") != AMOUNT_UNIT:
            migrated_rows: dict[str, Any] = {}
            for employee_id, amounts in (entry["rows"] or {}).items():
                if isinstance(amounts, dict):
                    migrated_rows[str(employee_id)] = _migrate_row_amount_fields(amounts)
            entry["rows"] = migrated_rows
            entry["provision_monthly"] = _to_sen_yen(raw.get("provision_monthly")) or 0
        return {
            "amount_unit": AMOUNT_UNIT,
            "years": {str(default_year): _normalize_year_entry(entry, facility_key)},
        }

    return {"amount_unit": AMOUNT_UNIT, "years": {}}


def _read_full_store(facility_key: str, *, default_year: Optional[int] = None) -> dict[str, Any]:
    year = default_year or default_fiscal_year()
    path = _amounts_path(facility_key)
    if not path.exists():
        defaults = default_provision_for_facility(facility_key)
        return {
            "amount_unit": AMOUNT_UNIT,
            "years": {
                str(year): {
                    "provision_monthly": defaults[0],
                    "provision_months": defaults[1],
                    "rows": {},
                }
            },
        }
    raw = json.loads(path.read_text(encoding="utf-8"))
    store = _migrate_store(raw if isinstance(raw, dict) else {}, facility_key, year)
    if raw != store:
        path.write_text(json.dumps(store, ensure_ascii=False, indent=2), encoding="utf-8")
    return store


def _write_full_store(facility_key: str, store: dict[str, Any]) -> None:
    _amounts_path(facility_key).write_text(
        json.dumps(store, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _get_year_entry(store: dict[str, Any], fiscal_year: int, facility_key: str) -> dict[str, Any]:
    years = store.setdefault("years", {})
    key = str(int(fiscal_year))
    if key not in years:
        defaults = default_provision_for_facility(facility_key)
        years[key] = {
            "provision_monthly": defaults[0],
            "provision_months": defaults[1],
            "rows": {},
        }
    return years[key]


def list_bonus_fiscal_years(facility_key: str) -> list[int]:
    store = _read_full_store(facility_key)
    years = store.get("years") or {}
    return sorted((int(year) for year in years.keys()), reverse=True)


def load_bonus_amounts_store(facility_key: str, fiscal_year: int) -> dict[str, Any]:
    store = _read_full_store(facility_key, default_year=fiscal_year)
    entry = _normalize_year_entry(_get_year_entry(store, fiscal_year, facility_key), facility_key)
    return {
        "amount_unit": AMOUNT_UNIT,
        "fiscal_year": int(fiscal_year),
        "provision_monthly": int(entry["provision_monthly"]),
        "provision_months": int(entry["provision_months"]),
        "rows": entry["rows"],
    }


def ensure_bonus_store_for_facility(facility_key: str, fiscal_year: int) -> None:
    store = _read_full_store(facility_key, default_year=fiscal_year)
    _get_year_entry(store, fiscal_year, facility_key)
    _write_full_store(facility_key, store)


def save_workbook_row_fields(
    facility_key: str,
    fiscal_year: int,
    rows: list[dict[str, Any]],
) -> None:
    store = _read_full_store(facility_key, default_year=fiscal_year)
    entry = _get_year_entry(store, fiscal_year, facility_key)
    row_map: dict[str, Any] = dict(entry.get("rows") or {})

    for item in rows:
        employee_id = (item.get("employee_id") or "").strip()
        if not employee_id:
            continue
        prev = row_map.get(employee_id) or {}
        next_row = dict(prev)
        for field in WORKBOOK_ROW_FIELDS:
            if field in item:
                next_row[field] = item.get(field)
        row_map[employee_id] = next_row

    entry["rows"] = row_map
    _write_full_store(facility_key, store)


def save_bonus_amounts_store(
    facility_key: str,
    fiscal_year: int,
    *,
    rows: list[dict[str, Any]],
    provision_monthly: Optional[int] = None,
    provision_months: Optional[int] = None,
    allow_proposed: bool = True,
    allow_bonus: bool = True,
    allow_provision: bool = True,
) -> None:
    store = _read_full_store(facility_key, default_year=fiscal_year)
    entry = _get_year_entry(store, fiscal_year, facility_key)
    row_map: dict[str, Any] = dict(entry.get("rows") or {})

    for item in rows:
        employee_id = (item.get("employee_id") or "").strip()
        if not employee_id:
            continue
        prev = row_map.get(employee_id) or {}
        merged = _merge_row_amount_entry(
            item,
            prev,
            allow_proposed=allow_proposed,
            allow_bonus=allow_bonus,
        )
        for field in WORKBOOK_ROW_FIELDS:
            if field in prev:
                merged[field] = prev[field]
        row_map[employee_id] = merged

    if allow_provision and provision_monthly is not None:
        entry["provision_monthly"] = int(provision_monthly)
    if allow_provision and provision_months is not None:
        entry["provision_months"] = normalize_provision_months(provision_months)
    entry["rows"] = row_map
    _write_full_store(facility_key, store)


def merge_amounts_into_rows(
    rows: list[dict[str, Any]],
    facility_key: str,
    fiscal_year: int,
) -> tuple[list[dict[str, Any]], int, int]:
    if is_facility_directors_bonus_key(facility_key):
        merged: list[dict[str, Any]] = []
        for row in rows:
            target_key = row.get("bonus_facility_key") or facility_key
            store = load_bonus_amounts_store(str(target_key), fiscal_year)
            employee_id = (row.get("employee_id") or "").strip()
            amounts = (store.get("rows") or {}).get(employee_id) or {}
            next_row = dict(row)
            next_row.update(_read_row_amount_fields(amounts))
            merged.append(next_row)
        return merged, 0, DEFAULT_PROVISION_MONTHS

    store = load_bonus_amounts_store(facility_key, fiscal_year)
    merged_rows: list[dict[str, Any]] = []
    for row in rows:
        employee_id = (row.get("employee_id") or "").strip()
        amounts = (store.get("rows") or {}).get(employee_id) or {}
        next_row = dict(row)
        next_row.update(_read_row_amount_fields(amounts))
        merged_rows.append(next_row)
    return (
        merged_rows,
        int(store.get("provision_monthly", 0)),
        int(store.get("provision_months", DEFAULT_PROVISION_MONTHS)),
    )


def save_amounts_for_workbook(
    facility_key: str,
    fiscal_year: int,
    rows: list[dict[str, Any]],
    *,
    provision_monthly: Optional[int] = None,
    provision_months: Optional[int] = None,
    allow_proposed: bool = True,
    allow_bonus: bool = True,
    allow_provision: bool = True,
) -> None:
    if is_facility_directors_bonus_key(facility_key):
        by_facility: dict[str, list[dict[str, Any]]] = {}
        for row in rows:
            target_key = (row.get("bonus_facility_key") or "").strip()
            if not target_key:
                continue
            by_facility.setdefault(target_key, []).append(row)
        for target_key, facility_rows in by_facility.items():
            save_bonus_amounts_store(
                target_key,
                fiscal_year,
                rows=facility_rows,
                allow_proposed=allow_proposed,
                allow_bonus=allow_bonus,
                allow_provision=False,
            )
        return

    save_bonus_amounts_store(
        facility_key,
        fiscal_year,
        rows=rows,
        provision_monthly=provision_monthly,
        provision_months=provision_months,
        allow_proposed=allow_proposed,
        allow_bonus=allow_bonus,
        allow_provision=allow_provision,
    )


def _round_sen_yen(value: float | Decimal) -> int:
    return int(Decimal(str(value)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def compute_bonus_summary(
    rows: list[dict[str, Any]],
    *,
    facility_key: str,
    provision_monthly: int,
    provision_months: int,
    fiscal_year: Optional[int] = None,
) -> dict[str, Any]:
    rate = settings.bonus_social_insurance_rate
    total_proposed = sum(int(row.get("proposed_bonus_amount") or 0) for row in rows)
    total_bonus = sum(int(row.get("bonus_amount") or 0) for row in rows)
    multiplier = Decimal("1") + Decimal(str(rate))
    total_with_social = _round_sen_yen(Decimal(total_bonus) * multiplier)
    year = fiscal_year or default_fiscal_year()

    if is_facility_directors_bonus_key(facility_key):
        facility_keys = {
            str(row.get("bonus_facility_key")).strip()
            for row in rows
            if row.get("bonus_facility_key")
        }
        provision_total = 0
        for key in facility_keys:
            store = load_bonus_amounts_store(key, year)
            monthly = int(store.get("provision_monthly", 0))
            months = int(store.get("provision_months", DEFAULT_PROVISION_MONTHS))
            provision_total += monthly * months
    else:
        provision_total = provision_monthly * provision_months

    difference = provision_total - total_with_social
    return {
        "total_proposed": total_proposed,
        "total_bonus": total_bonus,
        "total_with_social_insurance": total_with_social,
        "provision_monthly": provision_monthly,
        "provision_months": provision_months,
        "provision_total": provision_total,
        "difference": difference,
        "social_insurance_rate": rate,
    }
