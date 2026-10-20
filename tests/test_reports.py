"""A finished report as text: the closing total, the money, and the blanks."""

import math

import pytest

import calculation
import data
import reports
from state import State

MONTH = "2026-10"


@pytest.fixture
def month() -> State:
    return State.new(MONTH)


def test_both_reports_end_with_a_total_row(month):
    for report in (reports.sabji_bill(month), reports.stock_register(month)):
        assert report.iloc[-1]["Date"] == "Total"


def test_each_report_has_one_row_per_day_and_then_the_total(month):
    days = len(list(data.days_in(MONTH)))
    assert len(reports.sabji_bill(month)) == days + 1
    assert len(reports.stock_register(month)) == days + 1


def test_the_days_are_numbered_in_order_and_the_total_follows_them(month):
    dates = reports.sabji_bill(month)["Date"].tolist()
    assert dates[:-1] == list(range(1, 32))
    assert dates[-1] == "Total"


# Text


def test_money_is_written_to_two_decimals(month):
    report = reports.sabji_bill(month)
    lines = reports.as_text(report, calculation.SABJI_MONEY_COLUMNS)
    money_at = list(report.columns).index("Daily Total Cost")

    written = [line[money_at] for line in lines if line[money_at]]
    assert written
    assert all(len(value.split(".")[-1]) == 2 for value in written)


def test_a_blank_cell_becomes_an_empty_string(month):
    report = reports.sabji_bill(month)
    lines = reports.as_text(report, calculation.SABJI_MONEY_COLUMNS)
    closed_day = lines[3]  # the 4th is a Sunday
    blank_at = list(report.columns).index("Total Egg Cost")

    assert closed_day[blank_at] == ""
    assert closed_day[0] == "4"


def test_a_count_is_written_as_a_whole_number(month):
    report = reports.sabji_bill(month)
    lines = reports.as_text(report, calculation.SABJI_MONEY_COLUMNS)
    first_open_day = lines[0]
    head_at = list(report.columns).index("Total Beneficiaries")

    assert first_open_day[head_at] == "32"
    assert "." not in first_open_day[head_at]


def test_every_row_has_one_cell_per_column(month):
    for report, money in (
        (reports.sabji_bill(month), calculation.SABJI_MONEY_COLUMNS),
        (reports.stock_register(month), calculation.REGISTER_MONEY_COLUMNS),
    ):
        lines = reports.as_text(report, money)
        assert len(lines) == len(report)
        assert all(len(line) == len(report.columns) for line in lines)


def test_the_caption_says_what_a_blank_cell_means():
    assert "blank cell" in reports.SABJI_CAPTION
    assert "closed day" in reports.SABJI_CAPTION


# A month where every day is closed


def test_a_month_with_no_open_day_still_produces_both_reports(month):
    for day in data.days_in(MONTH):
        month.add_holiday(day)

    bill = reports.sabji_bill(month)
    register = reports.stock_register(month)

    # Every day is blank, and the total row is blank too: nothing was spent.
    assert bill.iloc[:-1].drop(columns="Date").isna().all().all()
    assert math.isnan(bill.iloc[-1]["Daily Total Cost"])
    assert (
        register.iloc[-1]["Rice Balance (Kg)"] != register.iloc[-1]["Rice Balance (Kg)"]
    )


def test_a_month_with_no_open_day_writes_nothing_at_all_as_text(month):
    for day in data.days_in(MONTH):
        month.add_holiday(day)

    lines = reports.as_text(reports.sabji_bill(month), calculation.SABJI_MONEY_COLUMNS)

    assert all(value == "" for line in lines[:-1] for value in line[1:])
    assert lines[-1][0] == "Total"
