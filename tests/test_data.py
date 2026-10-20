"""The bundled defaults, the months the picker offers, and the attendance sheet."""

from datetime import date

import pandas as pd
import pytest

import calculation
import data


def test_the_cost_sheet_is_read_as_one_column_per_head_and_day_type():
    costs = data.cost_defaults()

    assert list(costs.index) == list(data.COST_ITEMS)
    assert list(costs.columns) == list(data.PER_HEAD_COLUMNS.values())
    assert costs.at["egg", ("mother", "MWF")] == 850
    assert costs.at["egg", ("children", "TTS")] == 0
    # The one snack item carries a rate for each day type.
    assert costs.at["morning_snack", ("children", "MWF")] == 167
    assert costs.at["morning_snack", ("children", "TTS")] == 425


def test_the_derived_total_row_is_dropped():
    """The sheets carry a `total` row that the calculation must not count twice."""
    for sheet in (data.cost_defaults(), data.inventory_defaults()):
        assert "total" not in sheet.index


def test_the_cost_table_sums_to_the_printed_total_row():
    """The dropped row is the sum of the rows above it, in all four columns."""
    costs = data.cost_defaults()
    printed = {
        ("mother", "MWF"): 934,
        ("mother", "TTS"): 1013,
        ("children", "MWF"): 1017,
        ("children", "TTS"): 634,
    }
    for column, expected in printed.items():
        assert int(costs[column].sum()) == expected


def test_the_inventory_sheet_covers_every_commodity_the_register_writes():
    inventory = data.inventory_defaults()

    assert list(inventory.index) == list(calculation.LEDGER_COLUMNS)
    assert inventory.at["rice_g", ("mother", "MWF")] == 110
    assert inventory.at["masoor_dal_g", ("mother", "MWF")] == 0


def test_the_opening_stock_is_one_column_indexed_by_commodity():
    opening = data.opening_defaults()

    assert list(opening.columns) == ["opening"]
    assert list(opening.index) == list(calculation.LEDGER_COLUMNS)
    assert opening.at["rice_g", "opening"] == 25640
    assert opening.at["iodised_salt_g", "opening"] == 3272


def test_every_item_on_screen_has_a_label_and_a_key():
    for item in data.COST_ITEMS + data.STOCK_ITEMS:
        assert item in data.ITEM_LABELS


def test_a_month_lists_every_day_of_that_month():
    assert len(list(data.days_in("2026-10"))) == 31
    assert len(list(data.days_in("2026-02"))) == 28
    assert len(list(data.days_in("2024-02"))) == 29
    assert list(data.days_in("2026-12"))[-1] == date(2026, 12, 31)


def test_the_picker_offers_the_last_twelve_months_newest_first():
    keys = data.months_offered(date(2026, 10, 20))

    assert len(keys) == 12
    assert keys[0] == "2026-10"
    assert keys[-1] == "2025-11"


def test_a_month_is_written_out_by_name():
    assert data.month_label("2026-10") == "October 2026"
    assert data.month_label("2026-01") == "January 2026"


def test_every_sunday_of_the_month_is_found():
    sundays = data.sundays("2026-10")

    assert sundays == [
        date(2026, 10, 4),
        date(2026, 10, 11),
        date(2026, 10, 18),
        date(2026, 10, 25),
    ]


def test_a_fresh_month_is_complete_date_indexed_and_closed_on_sundays():
    sheet = data.attendance_sheet("2026-10")

    assert isinstance(sheet.index, pd.DatetimeIndex)
    assert sheet.index.name == "date"
    assert sheet.index.is_monotonic_increasing
    assert len(sheet) == 31
    # Sundays blank, every other day at the counts a working day starts at.
    assert sheet.loc["2026-10-04", "mothers"] != sheet.loc["2026-10-04", "mothers"]
    assert sheet.loc["2026-10-05", "mothers"] == data.DEFAULT_MOTHERS
    assert sheet.loc["2026-10-05", "children"] == data.DEFAULT_CHILDREN


def test_a_sheet_with_one_heading_per_column_reads_the_same_way(monkeypatch, tmp_path):
    """An office sheet written as `Mother MWF` rather than the two-row form reads."""
    (tmp_path / "per_head_costs_paisa.csv").write_text(
        "item,Mother MWF,Mother TTS,Children MWF,Children TTS\n"
        "egg,850,850,850,0\n"
        "total,850,850,850,0\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(data, "data_dir", lambda: tmp_path)

    costs = data.cost_defaults()

    assert list(costs.index) == ["egg"]
    assert costs.at["egg", ("children", "TTS")] == 0


def test_a_sheet_without_an_item_column_is_rejected(monkeypatch, tmp_path):
    (tmp_path / "per_head_costs_paisa.csv").write_text(
        "whatever\n1\n", encoding="utf-8"
    )
    monkeypatch.setattr(data, "data_dir", lambda: tmp_path)

    with pytest.raises(ValueError):
        data.cost_defaults()
