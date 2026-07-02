"""施設別賞与設定・名簿連携のテスト。"""

from app.services.facilities import (
    get_facility,
    reload_facility_configs,
    resolve_bonus_data_sheet,
)


def test_all_enabled_facilities_have_bonus_layout():
    reload_facility_configs()
    facility = get_facility("unuma")
    assert facility.bonus_enabled is True
    assert facility.bonus_layout == "default"


def test_resolve_bonus_data_sheet_by_keyword():
    reload_facility_configs()
    facility = get_facility("ogaki")
    sheet = resolve_bonus_data_sheet(
        facility,
        ["R7　いなは資料 ", "R7　大垣資料", "その他"],
    )
    assert sheet == "R7　大垣資料"


def test_resolve_bonus_data_sheet_prefers_configured_name():
    reload_facility_configs()
    facility = get_facility("inaha")
    sheet = resolve_bonus_data_sheet(
        facility,
        ["R7　いなは資料 ", "R7　大垣資料"],
    )
    assert sheet == "R7　いなは資料 "
