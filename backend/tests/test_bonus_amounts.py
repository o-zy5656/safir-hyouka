"""賞与金額・引当金の集計テスト。"""

from datetime import date

from app.services.bonus_amounts import (
    compute_bonus_summary,
    list_bonus_fiscal_years,
    load_bonus_amounts_store,
    normalize_provision_months,
    save_bonus_amounts_store,
)

TEST_YEAR = 2026


def test_compute_bonus_summary_inaha_defaults():
    rows = [
        {"proposed_bonus_amount": 500, "bonus_amount": 450},
        {"proposed_bonus_amount": 300, "bonus_amount": 280},
    ]
    summary = compute_bonus_summary(
        rows,
        facility_key="inaha",
        provision_monthly=1100,
        provision_months=12,
    )
    assert summary["total_proposed"] == 800
    assert summary["total_bonus"] == 730
    assert summary["total_with_social_insurance"] == 840  # 730 * 1.15 = 839.5 -> 840
    assert summary["provision_total"] == 13_200
    assert summary["difference"] == 12_360


def test_compute_bonus_summary_directors_aggregates_provision(monkeypatch, tmp_path):
    from app.services import bonus_amounts as module

    amounts_dir = tmp_path / "bonus_amounts"
    amounts_dir.mkdir()
    (amounts_dir / "inaha.json").write_text(
        '{"amount_unit":"sen_yen","years":{"2026":{"provision_monthly":1100,"provision_months":12,"rows":{}}}}',
        encoding="utf-8",
    )
    (amounts_dir / "sohara.json").write_text(
        '{"amount_unit":"sen_yen","years":{"2026":{"provision_monthly":800,"provision_months":6,"rows":{}}}}',
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "_amounts_dir", lambda: amounts_dir)

    rows = [
        {
            "employee_id": "d1",
            "bonus_facility_key": "inaha",
            "proposed_bonus_amount": 100,
            "bonus_amount": 100,
        },
        {
            "employee_id": "d2",
            "bonus_facility_key": "sohara",
            "proposed_bonus_amount": 50,
            "bonus_amount": 50,
        },
    ]
    summary = compute_bonus_summary(
        rows,
        facility_key="facility_directors",
        provision_monthly=0,
        provision_months=12,
        fiscal_year=TEST_YEAR,
    )
    assert summary["total_bonus"] == 150
    assert summary["provision_total"] == 13_200 + 4_800


def test_save_bonus_amounts_respects_role_fields(monkeypatch, tmp_path):
    from app.services import bonus_amounts as module

    amounts_dir = tmp_path / "bonus_amounts"
    amounts_dir.mkdir()
    monkeypatch.setattr(module, "_amounts_dir", lambda: amounts_dir)

    save_bonus_amounts_store(
        "inaha",
        TEST_YEAR,
        rows=[
            {
                "employee_id": "i1001",
                "proposed_bonus_amount": 100,
                "bonus_amount": 90,
            }
        ],
    )
    save_bonus_amounts_store(
        "inaha",
        TEST_YEAR,
        rows=[
            {
                "employee_id": "i1001",
                "proposed_bonus_amount": 120,
                "bonus_amount": 50,
            }
        ],
        allow_proposed=True,
        allow_bonus=False,
    )
    store = load_bonus_amounts_store("inaha", TEST_YEAR)
    assert store["rows"]["i1001"]["proposed_bonus_amount"] == 120
    assert store["rows"]["i1001"]["bonus_amount"] == 90

    save_bonus_amounts_store(
        "inaha",
        TEST_YEAR,
        rows=[
            {
                "employee_id": "i1001",
                "proposed_bonus_amount": 999,
                "bonus_amount": 80,
            }
        ],
        allow_proposed=False,
        allow_bonus=True,
    )
    store = load_bonus_amounts_store("inaha", TEST_YEAR)
    assert store["rows"]["i1001"]["proposed_bonus_amount"] == 120
    assert store["rows"]["i1001"]["bonus_amount"] == 80


def test_provision_saved_by_facility_director_role(monkeypatch, tmp_path):
    from app.services import bonus_amounts as module

    amounts_dir = tmp_path / "bonus_amounts"
    amounts_dir.mkdir()
    monkeypatch.setattr(module, "_amounts_dir", lambda: amounts_dir)

    save_bonus_amounts_store(
        "inaha",
        TEST_YEAR,
        rows=[],
        provision_monthly=900,
        provision_months=6,
        allow_proposed=False,
        allow_bonus=False,
        allow_provision=True,
    )
    store = load_bonus_amounts_store("inaha", TEST_YEAR)
    assert store["provision_monthly"] == 900
    assert store["provision_months"] == 6

    save_bonus_amounts_store(
        "inaha",
        TEST_YEAR,
        rows=[],
        provision_monthly=999,
        provision_months=12,
        allow_provision=False,
    )
    store = load_bonus_amounts_store("inaha", TEST_YEAR)
    assert store["provision_monthly"] == 900
    assert store["provision_months"] == 6


def test_fiscal_years_are_isolated(monkeypatch, tmp_path):
    from app.services import bonus_amounts as module

    amounts_dir = tmp_path / "bonus_amounts"
    amounts_dir.mkdir()
    monkeypatch.setattr(module, "_amounts_dir", lambda: amounts_dir)

    save_bonus_amounts_store(
        "inaha",
        2025,
        rows=[{"employee_id": "i1001", "proposed_bonus_amount": 100}],
        provision_monthly=500,
        provision_months=6,
    )
    save_bonus_amounts_store(
        "inaha",
        2026,
        rows=[{"employee_id": "i1001", "proposed_bonus_amount": 200}],
        provision_monthly=1100,
        provision_months=12,
    )

    store_2025 = load_bonus_amounts_store("inaha", 2025)
    store_2026 = load_bonus_amounts_store("inaha", 2026)
    assert store_2025["rows"]["i1001"]["proposed_bonus_amount"] == 100
    assert store_2025["provision_monthly"] == 500
    assert store_2026["rows"]["i1001"]["proposed_bonus_amount"] == 200
    assert store_2026["provision_monthly"] == 1100
    assert list_bonus_fiscal_years("inaha") == [2026, 2025]


def test_migrate_legacy_yen_store(monkeypatch, tmp_path):
    from app.services import bonus_amounts as module

    amounts_dir = tmp_path / "bonus_amounts"
    amounts_dir.mkdir()
    path = amounts_dir / "inaha.json"
    path.write_text(
        '{"provision_monthly": 1100000, "provision_months": 12, "rows": {"i1001": {"proposed_bonus_amount": 500000, "bonus_amount": 450000}}}',
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "_amounts_dir", lambda: amounts_dir)

    store = load_bonus_amounts_store("inaha", date.today().year)
    assert store["amount_unit"] == "sen_yen"
    assert store["provision_monthly"] == 1100
    assert store["rows"]["i1001"]["proposed_bonus_amount"] == 500
    assert store["rows"]["i1001"]["bonus_amount"] == 450


def test_normalize_provision_months():
    assert normalize_provision_months(6) == 6
    assert normalize_provision_months(12) == 12
    assert normalize_provision_months(10) == 12
