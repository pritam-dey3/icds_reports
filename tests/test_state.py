"""What each month holds: attendance, holidays, deliveries, and carrying over."""

from datetime import date

import data
from state import State


def month(**kwargs) -> State:
    """A fresh sheet for October 2026."""
    return State.new(**{"month": "2026-10", **kwargs})


# A month has its own inputs


def test_a_new_sheet_starts_on_the_shipped_defaults():
    state = month()

    assert state.month == "2026-10"
    assert state.costs.index.tolist() == list(data.COST_ITEMS)
    assert state.opening.at["rice_g", "opening"] == 25640


def test_a_new_month_starts_with_its_sundays_closed():
    state = month()

    assert state.holidays() == data.sundays("2026-10")
    assert state.is_holiday(date(2026, 10, 4))
    assert not state.is_holiday(date(2026, 10, 5))


def test_the_attendance_frame_is_complete_and_blank_on_a_closed_day():
    state = month()
    frame = state.attendance_frame()

    assert len(frame) == 31
    assert frame.index.name == "date"
    assert frame.loc["2026-10-04"].isna().all()  # a Sunday
    assert frame.loc["2026-10-05", "mothers"] == data.DEFAULT_MOTHERS


def test_every_holiday_is_a_day_of_the_open_month():
    state = month()

    for day in state.holidays():
        assert day.month == 10 and day.year == 2026


# Holidays mask a day, they do not erase it


def test_closing_a_day_blanks_it_without_losing_its_counts():
    state = month()
    day = date(2026, 10, 5)
    state.set_attendance(day, 9, 40)

    state.add_holiday(day)

    assert state.attendance_frame().loc["2026-10-05"].isna().all()
    assert state.counts(day) == (9, 40)


def test_reopening_a_day_brings_its_counts_back():
    """The original app reset a reopened day; a masked day keeps what it had."""
    state = month()
    day = date(2026, 10, 5)
    state.set_attendance(day, 9, 40)
    state.add_holiday(day)

    state.remove_holiday(day)

    assert state.attendance_frame().loc["2026-10-05", "mothers"] == 9
    assert state.attendance_frame().loc["2026-10-05", "children"] == 40


def test_a_closed_day_takes_no_counts():
    state = month()
    day = date(2026, 10, 4)  # a Sunday, already closed

    state.set_attendance(day, 9, 40)

    assert state.counts(day) == (data.DEFAULT_MOTHERS, data.DEFAULT_CHILDREN)


def test_a_holiday_outside_the_open_month_is_ignored():
    state = month()

    state.add_holiday(date(2026, 9, 3))

    assert date(2026, 9, 3) not in state.holidays()


def test_the_same_holiday_is_only_recorded_once():
    state = month()
    day = date(2026, 10, 6)

    state.add_holiday(day)
    state.add_holiday(day)

    assert state.holidays().count(day) == 1


def test_holidays_stay_in_date_order():
    state = month()

    state.add_holiday(date(2026, 10, 20))
    state.add_holiday(date(2026, 10, 6))

    stamps = [day for day in state.holidays()]
    assert stamps == sorted(stamps)


# Attendance edits are stored per day of the month


def test_a_count_is_recorded_for_its_own_day_only():
    state = month()
    state.set_attendance(date(2026, 10, 7), 3, 21)

    frame = state.attendance_frame()

    assert frame.loc["2026-10-07", "mothers"] == 3
    assert frame.loc["2026-10-07", "children"] == 21
    assert frame.loc["2026-10-08", "mothers"] == data.DEFAULT_MOTHERS


def test_a_negative_count_is_held_at_zero():
    state = month()
    state.set_attendance(date(2026, 10, 7), -5, -2)

    assert state.counts(date(2026, 10, 7)) == (0, 0)


# Months carry over by day of month


def test_a_new_month_takes_its_counts_from_the_newest_month_by_day_of_month():
    state = month()
    state.set_attendance(date(2026, 10, 5), 11, 55)

    state.select_month("2026-11")

    frame = state.attendance_frame()
    assert frame.loc["2026-11-05", "mothers"] == 11
    assert frame.loc["2026-11-05", "children"] == 55


def test_a_day_the_old_month_does_not_have_falls_back_to_the_starting_counts():
    """February has no 31st, so a month with a 31st cannot be carried from it."""
    state = State.new("2027-02")
    state.set_attendance(date(2027, 2, 5), 11, 55)

    state.select_month("2027-03")  # March has a 31st, February does not

    assert state.counts(date(2027, 3, 5)) == (11, 55)
    assert state.counts(date(2027, 3, 31)) == (
        data.DEFAULT_MOTHERS,
        data.DEFAULT_CHILDREN,
    )


def test_each_month_keeps_its_own_holidays():
    state = month()
    state.add_holiday(date(2026, 10, 6))

    state.select_month("2026-11")

    assert date(2026, 10, 6) not in state.holidays(month="2026-11")
    assert date(2026, 10, 6) in state.holidays(month="2026-10")


def test_going_back_to_a_month_shows_it_as_it_was_left():
    state = month()
    state.set_attendance(date(2026, 10, 9), 7, 70)
    state.select_month("2026-11")

    state.select_month("2026-10")

    assert state.counts(date(2026, 10, 9)) == (7, 70)


# Deliveries


def test_a_month_with_no_deliveries_hands_the_register_no_table():
    assert month().deliveries() is None


def test_a_delivery_is_recorded_with_its_item_day_and_amount():
    state = month()
    state.add_delivery("rice_g", date(2026, 10, 17), 30000)

    rows = state.additions()
    assert rows == [{"item": "rice_g", "date": "2026-10-17", "amount": 30000.0}]


def test_a_delivery_is_clamped_into_the_open_month():
    state = month()

    state.add_delivery("rice_g", date(2026, 8, 1), 5)
    state.add_delivery("rice_g", date(2027, 3, 1), 7)

    assert [row["date"] for row in state.additions()] == ["2026-10-01", "2026-10-31"]


def test_a_negative_delivery_is_held_at_zero():
    state = month()
    state.add_delivery("rice_g", date(2026, 10, 3), -50)

    assert state.additions()[0]["amount"] == 0


def test_a_delivery_can_be_edited_and_removed_by_its_place_in_the_list():
    state = month()
    state.add_delivery("rice_g", date(2026, 10, 3), 100)
    state.add_delivery("masoor_dal_g", date(2026, 10, 4), 200)

    state.set_delivery(0, item="mustard_oil_ml", day=date(2026, 10, 9), amount=300)
    assert state.additions()[0] == {
        "item": "mustard_oil_ml",
        "date": "2026-10-09",
        "amount": 300.0,
    }

    state.remove_delivery(0)
    assert [row["item"] for row in state.additions()] == ["masoor_dal_g"]


def test_deliveries_are_handed_over_in_the_columns_the_register_reads():
    state = month()
    state.add_delivery("rice_g", date(2026, 10, 17), 30000)

    table = state.deliveries()

    assert table is not None
    assert list(table.columns) == ["date", "item", "amount"]
    assert table.loc[0, "item"] == "rice_g"
    assert table.loc[0, "amount"] == 30000.0


# Reset


def test_a_reset_puts_every_edit_back_to_the_shipped_defaults():
    state = month()
    state.set_attendance(date(2026, 10, 5), 99, 99)
    state.add_holiday(date(2026, 10, 6))
    state.add_delivery("rice_g", date(2026, 10, 7), 5)
    state.costs.loc["egg", ("mother", "MWF")] = 1
    state.opening.loc["rice_g", "opening"] = 1

    state.reset()

    assert state.costs.at["egg", ("mother", "MWF")] == 850
    assert state.opening.at["rice_g", "opening"] == 25640
    assert state.holidays() == data.sundays("2026-10")
    assert state.additions() == []
    assert state.counts(date(2026, 10, 5)) == (
        data.DEFAULT_MOTHERS,
        data.DEFAULT_CHILDREN,
    )


# Round trip


def test_every_edited_input_survives_a_save_and_reload():
    """All seven inputs are edited, then saved and read back.

    Every value asserted here is one the shipped defaults do not already hold, so the
    test fails if a table is left out of the saved file instead of passing on a
    default that happens to match.
    """
    state = month()
    state.costs.loc["egg", ("mother", "MWF")] = 901
    state.inventory.loc["rice_g", ("children", "TTS")] = 76
    state.opening.loc["rice_g", "opening"] = 11_111
    state.set_attendance(date(2026, 10, 5), 13, 51)
    state.add_holiday(date(2026, 10, 6))
    state.remove_holiday(date(2026, 10, 4))
    state.add_delivery("mustard_oil_ml", date(2026, 10, 9), 500)

    rebuilt = State.from_dict(state.to_dict())

    assert rebuilt.month == "2026-10"  # 1 the month
    assert rebuilt.costs.at["egg", ("mother", "MWF")] == 901  # 2 costings
    assert rebuilt.inventory.at["rice_g", ("children", "TTS")] == 76  # 3 inventory
    assert rebuilt.opening.at["rice_g", "opening"] == 11_111  # 4 opening stock
    assert rebuilt.counts(date(2026, 10, 5)) == (13, 51)  # 5 attendance
    assert rebuilt.is_holiday(date(2026, 10, 6))  # 6 a holiday added
    assert not rebuilt.is_holiday(date(2026, 10, 4))  # 6 a Sunday reopened
    assert rebuilt.additions() == [  # 7 a delivery, with item, day and amount
        {"item": "mustard_oil_ml", "date": "2026-10-09", "amount": 500.0}
    ]


def test_a_rebuilt_sheet_is_equal_to_the_one_that_was_saved():
    """The whole worksheet, table by table, after every input has been edited."""
    state = month()
    state.costs.loc["potato", ("children", "TTS")] = 171
    state.inventory.loc["iodised_salt_g", ("mother", "TTS")] = 3
    state.opening.loc["mustard_oil_ml", "opening"] = 4000
    state.set_attendance(date(2026, 10, 5), 11, 55)
    state.add_holiday(date(2026, 10, 6))
    state.add_delivery("rice_g", date(2026, 10, 7), 30)

    rebuilt = State.from_dict(state.to_dict())

    assert rebuilt.costs.equals(state.costs)
    assert rebuilt.inventory.equals(state.inventory)
    assert rebuilt.opening.equals(state.opening)
    assert rebuilt.additions() == state.additions()
    assert rebuilt.holidays() == state.holidays()
    assert rebuilt.attendance_frame().equals(state.attendance_frame())


def test_each_month_s_inputs_survive_a_save_and_reload():
    """A month that is not open is saved too, and comes back intact."""
    state = month()
    state.select_month("2026-11")
    state.set_attendance(date(2026, 11, 3), 6, 33)
    state.add_delivery("rice_g", date(2026, 11, 2), 50)
    state.add_holiday(date(2026, 11, 10))

    rebuilt = State.from_dict(state.to_dict())

    assert rebuilt.month == "2026-11"
    assert rebuilt.counts(date(2026, 11, 3)) == (6, 33)
    assert rebuilt.additions() == [
        {"item": "rice_g", "date": "2026-11-02", "amount": 50.0}
    ]
    assert rebuilt.is_holiday(date(2026, 11, 10))
    # The month it was built from is still there, and still at its own values.
    assert rebuilt.counts(date(2026, 10, 5)) == (
        data.DEFAULT_MOTHERS,
        data.DEFAULT_CHILDREN,
    )
    assert rebuilt.holidays(month="2026-10") == data.sundays("2026-10")
