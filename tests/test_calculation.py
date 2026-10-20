"""The two reports, against a month whose figures were worked out by hand.

October 2026 is chosen because its 1st is a Thursday (a Tue/Thu/Sat day) and its 2nd
a Friday (a Mon/Wed/Fri day), so one closed month of just those two days exercises
both day types. Every day has 2 mothers and 10 children.

The expected numbers below were worked out from `calculation.md` by hand, not taken
from the code, so they fail if the code changes its mind about a rule.
"""

import math
from datetime import date

import pandas as pd
import pytest

import calculation
import reports
from state import State

MONTH = "2026-10"
TTS_DAY = date(2026, 10, 1)  # Thursday
MWF_DAY = date(2026, 10, 2)  # Friday
MOTHERS = 2
CHILDREN = 10


@pytest.fixture
def two_day_month() -> State:
    """The one month every test here reads: only the 1st and 2nd are open."""
    state = State.new(MONTH)
    for day in __import__("data").days_in(MONTH):
        if day not in (TTS_DAY, MWF_DAY):
            state.add_holiday(day)
    state.set_attendance(TTS_DAY, MOTHERS, CHILDREN)
    state.set_attendance(MWF_DAY, MOTHERS, CHILDREN)
    return state


@pytest.fixture
def bill(two_day_month) -> pd.DataFrame:
    return reports.sabji_bill(two_day_month)


@pytest.fixture
def register(two_day_month) -> pd.DataFrame:
    return reports.stock_register(two_day_month)


def cell(report: pd.DataFrame, row: int, column: str):
    return report.loc[row, column]


def blank(value) -> bool:
    return value is None or (isinstance(value, float) and math.isnan(value))


# The head counts


def test_a_closed_day_is_blank_in_both_reports(bill, register):
    days = bill["Date"].tolist()
    assert days[0] == 1 and days[1] == 2
    for report in (bill, register):
        assert blank(cell(report, 2, report.columns[1]))


def test_the_counts_are_split_by_day_type(bill):
    # The 1st is a Tue/Thu/Sat day, so only the Tue/Thu/Sat columns carry its heads.
    assert cell(bill, 0, "Pregnant+Lactating Tue/Thu/Sat") == MOTHERS
    assert cell(bill, 0, "Children Tue/Thu/Sat") == CHILDREN
    assert blank(cell(bill, 0, "Pregnant+Lactating Mon/Wed/Fri"))
    assert blank(cell(bill, 0, "Children Mon/Wed/Fri"))
    # The 2nd is a Mon/Wed/Fri day, so the two sets swap over.
    assert cell(bill, 1, "Pregnant+Lactating Mon/Wed/Fri") == MOTHERS
    assert cell(bill, 1, "Children Mon/Wed/Fri") == CHILDREN
    assert blank(cell(bill, 1, "Pregnant+Lactating Tue/Thu/Sat"))
    assert blank(cell(bill, 1, "Children Tue/Thu/Sat"))


def test_the_total_beneficiaries_are_both_heads_together(bill):
    assert cell(bill, 0, "Total Beneficiaries") == MOTHERS + CHILDREN
    assert cell(bill, 1, "Total Beneficiaries") == MOTHERS + CHILDREN


def test_the_other_children_columns_stay_blank(bill):
    """Nothing feeds these two columns, so no figure is invented for them."""
    assert blank(cell(bill, 0, "Other Children Mon/Wed/Fri"))
    assert blank(cell(bill, 0, "Other Children Tue/Thu/Sat"))


# The sabji bill's money, day by day


def test_the_tue_thu_sat_day_costs_what_its_own_rates_say(bill):
    # egg 2x850 + 10x0 = 1700 paisa -> 17.00
    assert cell(bill, 0, "Total Egg Cost") == 17.0
    # veg mother 2x23 = 46 -> 0.46; veg child 10x41 = 410 -> 4.10
    assert cell(bill, 0, "Veg Mother") == 0.46
    assert cell(bill, 0, "Veg Child") == 4.10
    # potato mother 2x140 = 280 -> 2.80; potato child 10x168 = 1680 -> 16.80
    assert cell(bill, 0, "Potato Mother") == 2.80
    assert cell(bill, 0, "Potato Child") == 16.80
    assert cell(bill, 0, "Total Veg+Potato") == 24.16
    # morning snack 10x425 = 4250 -> 42.50; the Mon/Wed/Fri serving is blank today
    assert cell(bill, 0, "Morning Snack Tue/Thu/Sat") == 42.50
    assert blank(cell(bill, 0, "Morning Snack Mon/Wed/Fri"))
    assert cell(bill, 0, "Daily Total Cost") == 83.66


def test_the_mon_wed_fri_day_costs_what_its_own_rates_say(bill):
    # egg 2x850 + 10x850 = 10200 paisa -> 102.00
    assert cell(bill, 1, "Total Egg Cost") == 102.0
    # vegetables are not served to either head on this day type
    assert blank(cell(bill, 1, "Veg Mother"))
    assert blank(cell(bill, 1, "Veg Child"))
    # potato mother 2x84 = 168 -> 1.68; potato child not served
    assert cell(bill, 1, "Potato Mother") == 1.68
    assert blank(cell(bill, 1, "Potato Child"))
    assert cell(bill, 1, "Total Veg+Potato") == 1.68
    assert blank(cell(bill, 1, "Morning Snack Tue/Thu/Sat"))
    assert cell(bill, 1, "Morning Snack Mon/Wed/Fri") == 16.70
    assert cell(bill, 1, "Daily Total Cost") == 120.38


def test_a_rate_of_zero_writes_a_blank_not_a_zero(bill):
    """The difference matters: a blank means "not served", a 0 would mean "free"."""
    assert blank(cell(bill, 1, "Veg Mother"))
    assert blank(cell(bill, 0, "Morning Snack Mon/Wed/Fri"))


def test_the_daily_total_is_the_sum_of_the_day_s_own_columns(bill):
    for row in (0, 1):
        parts = [
            cell(bill, row, name)
            for name in (
                "Total Egg Cost",
                "Total Veg+Potato",
                "Morning Snack Tue/Thu/Sat",
                "Morning Snack Mon/Wed/Fri",
            )
            if not blank(cell(bill, row, name))
        ]
        assert cell(bill, row, "Daily Total Cost") == pytest.approx(sum(parts))


# The stock register


def test_the_register_repeats_the_attendance_in_its_own_columns(register):
    assert cell(register, 0, "MS (Morning Snack) Beneficiaries") == CHILDREN
    assert cell(register, 0, "HCM Children 6m-6y") == CHILDREN
    assert cell(register, 0, "HCM Pregnant+Lactating") == MOTHERS
    assert cell(register, 0, "THR (SAM+SUW)") == MOTHERS + CHILDREN


def test_each_commodity_opens_at_its_opening_stock_and_issues_the_day_s_ration(
    register,
):
    # rice on the Tuesday/Thursday/Saturday day: 2x75 + 10x75 = 900 g
    assert cell(register, 0, "Rice Balance (Kg)") == 25640
    assert cell(register, 0, "Rice Consumption (Kg)") == 900
    # the next day draws 2x110 + 10x50 = 720 g, so it opens at 25640 - 900
    assert cell(register, 1, "Rice Balance (Kg)") == 24740
    assert cell(register, 1, "Rice Consumption (Kg)") == 720


def test_a_commodity_that_is_not_served_that_day_leaves_the_stock_alone(register):
    """Masoor dal is only served on the Tue/Thu/Sat day, so the Friday is blank."""
    assert cell(register, 0, "Masoor Dal Balance (Kg)") == 20400
    assert cell(register, 0, "Masoor Dal Consumption (Kg)") == 2 * 30 + 10 * 30
    assert blank(cell(register, 1, "Masoor Dal Balance (Kg)"))
    assert blank(cell(register, 1, "Masoor Dal Consumption (Kg)"))


def test_a_commodity_served_every_day_moves_every_day(register):
    # mustard oil 2 ml per head: (2 + 10) x 2 = 24 ml on each open day
    assert cell(register, 0, "Mustard Oil Consumption (Ltr)") == 24
    assert cell(register, 1, "Mustard Oil Balance (Ltr)") == 3272 - 24
    assert cell(register, 1, "Mustard Oil Consumption (Ltr)") == 24


def test_the_unused_fifth_commodity_stays_blank(register):
    assert blank(cell(register, 0, "Commodity 5 Balance"))
    assert blank(cell(register, 0, "Commodity 5 Consumption"))


def test_the_register_money_matches_the_bill(register):
    # Item 1 is the Mon/Wed/Fri serving; the Tue/Thu/Sat day leaves it blank
    assert blank(cell(register, 0, "Morning Snacks & THR Value Rs (Item 1)"))
    assert cell(register, 1, "Morning Snacks & THR Value Rs (Item 1)") == 16.70
    # Item 2 is the egg plus the Tue/Thu/Sat snack: 1700 + 4250 = 5950 -> 59.50
    assert cell(register, 0, "Morning Snacks & THR Value Rs (Item 2 - Egg)") == 59.50
    assert cell(register, 1, "Morning Snacks & THR Value Rs (Item 2 - Egg)") == 102.0
    assert cell(register, 0, "Vegetable Value Rs") == 4.56
    assert cell(register, 1, "Potato Value Rs") == 1.68


def test_the_register_and_the_bill_agree_on_the_same_money(register, bill):
    assert cell(register, 1, "Potato Value Rs") == cell(bill, 1, "Potato Mother")
    assert cell(register, 0, "Vegetable Value Rs") == pytest.approx(
        cell(bill, 0, "Veg Mother") + cell(bill, 0, "Veg Child")
    )


# The closing Total row


def test_the_total_row_sums_the_counts_and_the_money(bill):
    total = bill.iloc[-1]
    assert total["Date"] == "Total"
    assert total["Total Beneficiaries"] == 2 * (MOTHERS + CHILDREN)
    assert total["Total Egg Cost"] == 17.0 + 102.0
    assert total["Total Veg+Potato"] == pytest.approx(24.16 + 1.68)
    assert total["Daily Total Cost"] == pytest.approx(83.66 + 120.38)


def test_a_column_that_is_blank_all_month_stays_blank_in_the_total(bill):
    total = bill.iloc[-1]
    assert blank(total["Other Children Mon/Wed/Fri"])
    assert blank(total["Other Children Tue/Thu/Sat"])


def test_a_balance_total_is_the_stock_left_at_month_end_not_a_sum(register):
    total = register.iloc[-1]
    # rice closes at what the last written day opened with, less that day's issue
    assert total["Rice Balance (Kg)"] == 24740 - 720
    assert total["Rice Consumption (Kg)"] == 900 + 720
    # a commodity with a gap mid-month closes from its own last written day
    assert total["Masoor Dal Balance (Kg)"] == 20400 - 360


# Deliveries


def test_a_delivery_counts_from_its_own_day_on(two_day_month):
    """Stock that arrives on the 2nd is on hand for the 2nd, and not before."""
    before = reports.stock_register(two_day_month)
    two_day_month.add_delivery("rice_g", MWF_DAY, 30000)
    after = reports.stock_register(two_day_month)

    # The day before the delivery is untouched: the stock is not there early.
    assert cell(after, 0, "Rice Balance (Kg)") == cell(before, 0, "Rice Balance (Kg)")
    assert cell(after, 0, "Rice Consumption (Kg)") == cell(
        before, 0, "Rice Consumption (Kg)"
    )
    # On its own day the whole amount is in stock.
    assert cell(after, 1, "Rice Balance (Kg)") == 24740 + 30000
    # That day draws its full ration, exactly as before.
    assert cell(after, 1, "Rice Consumption (Kg)") == 720


def test_a_delivery_leaves_every_other_column_alone(two_day_month):
    before = reports.stock_register(two_day_month)
    two_day_month.add_delivery("rice_g", MWF_DAY, 30000)
    after = reports.stock_register(two_day_month)

    changed = {name for name in before.columns if not before[name].equals(after[name])}
    # Only the rice ledger moves, and only from the delivery day on.
    assert changed == {"Rice Balance (Kg)"}


def test_a_delivery_that_exceeds_the_ration_is_carried_forward(two_day_month):
    two_day_month.add_delivery("masoor_dal_g", TTS_DAY, 500)
    register = reports.stock_register(two_day_month)

    assert cell(register, 0, "Masoor Dal Balance (Kg)") == 20400 + 500
    assert cell(register, 0, "Masoor Dal Consumption (Kg)") == 360


def test_stock_that_runs_out_issues_only_what_is_left(two_day_month):
    """A ration bigger than the shelf is cut back, and the balance settles at 0."""
    two_day_month.opening.loc["iodised_salt_g", "opening"] = 10
    register = reports.stock_register(two_day_month)

    assert cell(register, 0, "Iodised Salt Balance") == 10
    assert cell(register, 0, "Iodised Salt Consumption") == 10
    # the next day has nothing left, so it issues nothing and shows 0
    assert cell(register, 1, "Iodised Salt Balance") == 0
    assert cell(register, 1, "Iodised Salt Consumption") == 0


# Day types


def test_the_day_types_come_from_the_calendar():
    dates = pd.DatetimeIndex(["2026-10-05", "2026-10-06", "2026-10-07"])  # Mon Tue Wed

    assert calculation.day_types(dates).tolist() == ["MWF", "TTS", "MWF"]


# Every column the paper sheet has is written


SABJI_COLUMNS = (
    "Date",
    "Total Beneficiaries",
    "Pregnant+Lactating Mon/Wed/Fri",
    "Pregnant+Lactating Tue/Thu/Sat",
    "Children Mon/Wed/Fri",
    "Children Tue/Thu/Sat",
    "Other Children Mon/Wed/Fri",
    "Other Children Tue/Thu/Sat",
    "Total Egg Cost",
    "Veg Mother",
    "Veg Child",
    "Potato Mother",
    "Potato Child",
    "Total Veg+Potato",
    "Morning Snack Tue/Thu/Sat",
    "Morning Snack Mon/Wed/Fri",
    "Daily Total Cost",
)

REGISTER_COLUMNS = (
    "Date",
    "MS (Morning Snack) Beneficiaries",
    "HCM Children 6m-6y",
    "HCM Pregnant+Lactating",
    "THR (SAM+SUW)",
    "Rice Balance (Kg)",
    "Rice Consumption (Kg)",
    "Masoor Dal Balance (Kg)",
    "Masoor Dal Consumption (Kg)",
    "Mustard Oil Balance (Ltr)",
    "Mustard Oil Consumption (Ltr)",
    "Iodised Salt Balance",
    "Iodised Salt Consumption",
    "Commodity 5 Balance",
    "Commodity 5 Consumption",
    "Morning Snacks & THR Value Rs (Item 1)",
    "Morning Snacks & THR Value Rs (Item 2 - Egg)",
    "Vegetable Value Rs",
    "Potato Value Rs",
)


def test_the_bill_carries_every_column_in_the_paper_order(bill):
    assert tuple(bill.columns) == SABJI_COLUMNS


def test_the_register_carries_every_column_in_the_paper_order(register):
    assert tuple(register.columns) == REGISTER_COLUMNS
