"""The two daily reports: the sabji bill and the stock register.

Every figure in both reports is worked out from four inputs: the day's attendance,
the per-head cost table, the per-head inventory table and the opening stock. The
rules are written out in `calculation.md`, and this module follows it column by
column; the column names are the ones the offices use on their sheets.

Three conventions run through the module:

* A blank means "nothing to write" — a closed day, or an item that is not served.
  Whether an item is served comes from its rates, so a rate of 0 leaves the column
  blank instead of writing 0.
* Money is worked out in paisa, the unit of the cost table, and divided by 100 when
  the report is assembled, so the reports carry rupees.
* Quantities are in the unit of the item's name — `rice_g` in grams,
  `mustard_oil_ml` in millilitres. The sheets title those columns Kg and Ltr, as the
  paper sheets do.

Item names are the keys of the defaults sheets: `egg`, `vegetables`, `potato` and
`morning_snack` for costs, `rice_g`, `masoor_dal_g`, `mustard_oil_ml` and
`iodised_salt_g` for stock. One snack item carries both day types' rates, so the
paper's two snack columns are that item split by the day's type.
"""

from typing import NamedTuple

import pandas as pd

# The day types: which set of rates a day uses, and the suffix on the two sets of
# attendance columns.
MWF = "MWF"
TTS = "TTS"
MWF_WEEKDAYS = (0, 2, 4)  # Monday, Wednesday, Friday

# The two heads every rate table has a column pair for.
MOTHER = "mother"
CHILDREN = "children"

# What a column that has nothing to write holds, so that it comes out blank.
BLANK = float("nan")

# Each commodity's two ledger columns, in the order the register lists them.
LEDGER_COLUMNS = {
    "rice_g": ("Rice Balance (Kg)", "Rice Consumption (Kg)"),
    "masoor_dal_g": ("Masoor Dal Balance (Kg)", "Masoor Dal Consumption (Kg)"),
    "mustard_oil_ml": ("Mustard Oil Balance (Ltr)", "Mustard Oil Consumption (Ltr)"),
    "iodised_salt_g": ("Iodised Salt Balance", "Iodised Salt Consumption"),
}

# The columns of each report that hold money: worked out in paisa, written in rupees.
SABJI_MONEY_COLUMNS = (
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
REGISTER_MONEY_COLUMNS = (
    "Morning Snacks & THR Value Rs (Item 1)",
    "Morning Snacks & THR Value Rs (Item 2 - Egg)",
    "Vegetable Value Rs",
    "Potato Value Rs",
)


class Days(NamedTuple):
    """The month's days side by side, one value per row.

    `dates` is the calendar date, which sets each day's type and the day of the month
    the reports write; `mothers` and `children` are the head counts, blank on a closed
    day; `day_type` is the set of rates that day uses.
    """

    dates: pd.DatetimeIndex
    mothers: pd.Series
    children: pd.Series
    day_type: pd.Series


def sabji_bill(attendance: pd.DataFrame, costs: pd.DataFrame) -> pd.DataFrame:
    """The sabji bill: one row per day of the month, one column per cost.

    `attendance` holds the day's two head counts in `mothers` and `children`, blank
    on a closed day. `costs` is the per-head cost table in paisa, indexed by item
    and holding a `(head, day type)` column for each rate.
    """
    days = _days(attendance)

    # The attendance columns: the head counts, split by day type.
    bill = pd.DataFrame({"Date": days.dates.day})
    bill["Total Beneficiaries"] = days.mothers + days.children
    bill["Pregnant+Lactating Mon/Wed/Fri"] = _heads_on(days, MOTHER, MWF)
    bill["Pregnant+Lactating Tue/Thu/Sat"] = _heads_on(days, MOTHER, TTS)
    bill["Children Mon/Wed/Fri"] = _heads_on(days, CHILDREN, MWF)
    bill["Children Tue/Thu/Sat"] = _heads_on(days, CHILDREN, TTS)
    bill["Other Children Mon/Wed/Fri"] = BLANK
    bill["Other Children Tue/Thu/Sat"] = BLANK

    # The money columns, in paisa until `_to_rupees` divides them.
    bill["Total Egg Cost"] = _item_amount(days, costs, "egg")
    bill["Veg Mother"] = _head_amount(days, costs, "vegetables", MOTHER)
    bill["Veg Child"] = _head_amount(days, costs, "vegetables", CHILDREN)
    bill["Potato Mother"] = _head_amount(days, costs, "potato", MOTHER)
    bill["Potato Child"] = _head_amount(days, costs, "potato", CHILDREN)
    bill["Total Veg+Potato"] = _sum(
        bill["Veg Mother"],
        bill["Veg Child"],
        bill["Potato Mother"],
        bill["Potato Child"],
    )
    # The paper keeps a column per day type; both are the one snack item, split by
    # the day's type. Where a day is blank for its type, the other column stays blank.
    bill["Morning Snack Tue/Thu/Sat"] = _item_amount_on(
        days, costs, "morning_snack", TTS
    )
    bill["Morning Snack Mon/Wed/Fri"] = _item_amount_on(
        days, costs, "morning_snack", MWF
    )
    bill["Daily Total Cost"] = _sum(
        bill["Total Egg Cost"],
        bill["Total Veg+Potato"],
        bill["Morning Snack Tue/Thu/Sat"],
        bill["Morning Snack Mon/Wed/Fri"],
    )
    return _to_rupees(bill, SABJI_MONEY_COLUMNS)


def stock_register(
    attendance: pd.DataFrame,
    costs: pd.DataFrame,
    inventory: pd.DataFrame,
    opening: pd.DataFrame,
    additions: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """The stock register: the day's attendance, the commodity ledger, the money.

    `attendance` and `costs` are as for `sabji_bill`. `inventory` is the per-head
    quantity table, in the unit named by each item, and `opening` holds one column of
    opening stock per commodity — the stock the register's ledger starts from.

    `additions` holds stock that arrives during the month, one row per delivery with a
    `date`, an `item` and an `amount`. A delivery counts from its own day on: it is in
    stock for that day's issue, and for every day after it. A date the report does not
    cover is ignored.

    A delivery is always on or before the last day the item is written — the last day
    it is served. That is what lets `totals` close a balance from the last written day
    alone: stock arriving after it would never be written into a balance column.
    """
    days = _days(attendance)
    opening_stock = opening.iloc[:, 0]  # one column: the stock per commodity
    received = _receipts(additions, days.dates)

    # The attendance columns.
    register = pd.DataFrame({"Date": days.dates.day})
    register["MS (Morning Snack) Beneficiaries"] = days.children
    register["HCM Children 6m-6y"] = days.children
    register["HCM Pregnant+Lactating"] = days.mothers
    register["THR (SAM+SUW)"] = days.mothers + days.children

    # The ledger: each commodity's balance and consumption, in sheet order.
    for item, (balance, consumption) in LEDGER_COLUMNS.items():
        ration = _item_amount(days, inventory, item)
        ledger = _ledger(opening_stock[item], ration, received[item])
        register[balance] = ledger["balance"]
        register[consumption] = ledger["consumption"]
    register["Commodity 5 Balance"] = BLANK
    register["Commodity 5 Consumption"] = BLANK

    # The money columns: the same figures as the sabji bill, in paisa until
    # `_to_rupees` divides them. Item 1 is the Mon/Wed/Fri serving of the snack.
    register["Morning Snacks & THR Value Rs (Item 1)"] = _item_amount_on(
        days, costs, "morning_snack", MWF
    )
    # Item 2 is the egg, plus the Tue/Thu/Sat serving of the snack.
    register["Morning Snacks & THR Value Rs (Item 2 - Egg)"] = _sum(
        _item_amount(days, costs, "egg"),
        _item_amount_on(days, costs, "morning_snack", TTS),
    )
    register["Vegetable Value Rs"] = _item_amount(days, costs, "vegetables")
    register["Potato Value Rs"] = _item_amount(days, costs, "potato")
    return _to_rupees(register, REGISTER_MONEY_COLUMNS)


def totals(report: pd.DataFrame) -> pd.Series:
    """The closing `Total` row of a report: counts and money summed, stock closed.

    A balance column is not a sum. Its total is the stock left at month end: the last
    balance the report writes, less that day's consumption. The `Date` column is left
    out, and a column that is blank all month stays blank.
    """
    total = report.drop(columns="Date").sum(min_count=1)
    for balance, consumption in LEDGER_COLUMNS.values():
        if balance not in report:
            continue  # the bill has no ledger
        # The last day the commodity was written is the last day it was served.
        written = report[balance].dropna()
        if written.empty:
            continue  # never served this month, so there is no balance to close
        last_written = written.index[-1]
        total[balance] = (
            written.loc[last_written] - report[consumption].loc[last_written]
        )
    return total


def day_types(dates: pd.DatetimeIndex) -> pd.Series:
    """The day type of each date: `MWF` on Mon/Wed/Fri, `TTS` on every other day.

    Closed days are not decided here. They are the days the attendance sheet leaves
    blank, which blanks every report column and leaves the stock where it was.
    """
    return pd.Series([
        MWF if weekday in MWF_WEEKDAYS else TTS for weekday in dates.weekday
    ])


def _days(attendance: pd.DataFrame) -> Days:
    """The month's days in calendar order, one row per day: its date, the head counts
    and the day type.

    The date is the frame's index; a `date` column is accepted too, so an attendance
    sheet read straight from a CSV works. Attendance is blank on a closed day, so
    everything derived from it is blank there.
    """
    if "date" in attendance.columns:
        attendance = attendance.set_index("date")
    frame = attendance.sort_index()
    dates = pd.DatetimeIndex(frame.index)
    return Days(
        dates=dates,
        mothers=frame["mothers"].reset_index(drop=True),
        children=frame["children"].reset_index(drop=True),
        day_type=day_types(dates),
    )


def _head_counts(days: Days, head: str) -> pd.Series:
    """The month's own count for one head: the mothers, or the children."""
    return days.mothers if head == MOTHER else days.children


def _heads_on(days: Days, head: str, day_type: str) -> pd.Series:
    """One head's count on the days of one type, blank on the other days."""
    return _head_counts(days, head).where(days.day_type == day_type)


def _rate(table: pd.DataFrame, item: str, head: str, day_type: pd.Series) -> pd.Series:
    """The item's rate for one head, taking the Mon/Wed/Fri or Tue/Thu/Sat column."""
    rate = {MWF: table.at[item, (head, MWF)], TTS: table.at[item, (head, TTS)]}
    return day_type.map(rate)


def _served(for_mothers: pd.Series, for_children: pd.Series) -> pd.Series:
    """Whether the item is served at all that day: a rate above 0 for either head."""
    return (for_mothers > 0) | (for_children > 0)


def _head_amount(days: Days, table: pd.DataFrame, item: str, head: str) -> pd.Series:
    """`heads x rate[item][head]`, blank when the item is not served to that head.

    A rate of 0 means the item is not served to that head on that day type.
    """
    rate = _rate(table, item, head, days.day_type)
    return (_head_counts(days, head) * rate).where(rate > 0)


def _item_amount(days: Days, table: pd.DataFrame, item: str) -> pd.Series:
    """`M x rate[item][mother] + C x rate[item][children]`, blank when not served.

    The amount is in the table's own unit: paisa for the cost table, grams or
    millilitres for the inventory table.
    """
    for_mothers = _rate(table, item, MOTHER, days.day_type)
    for_children = _rate(table, item, CHILDREN, days.day_type)
    amount = for_mothers * days.mothers + for_children * days.children
    return amount.where(_served(for_mothers, for_children))


def _item_amount_on(
    days: Days, table: pd.DataFrame, item: str, day_type: str
) -> pd.Series:
    """The item's amount on the days of one type, blank on the days of the other.

    An item can be served on both day types; the paper writes one column for each.
    """
    return _item_amount(days, table, item).where(days.day_type == day_type)


def _receipts(additions: pd.DataFrame | None, dates: pd.DatetimeIndex) -> pd.DataFrame:
    """The stock that arrives on each day, one column per commodity.

    A delivery is counted on its own date; one dated outside the report's days is
    ignored. Several deliveries of the same item on one day add up.
    """
    days = pd.DatetimeIndex(dates).normalize()
    if additions is None:
        return pd.DataFrame(0.0, index=range(len(days)), columns=list(LEDGER_COLUMNS))

    deliveries = pd.DataFrame({
        "date": pd.DatetimeIndex(additions["date"]).normalize(),
        "item": additions["item"].to_numpy(),
        "amount": additions["amount"].to_numpy(),
    })
    return (
        deliveries.groupby(["date", "item"])["amount"]
        .sum()
        .unstack(fill_value=0)
        .reindex(index=days, columns=list(LEDGER_COLUMNS), fill_value=0.0)
        .reset_index(drop=True)
    )


def _ledger(opening: float, ration: pd.Series, received: pd.Series) -> pd.DataFrame:
    """Walk the month: the stock at the start of each day, and what was issued.

    `ration` is what the day's heads are due, blank on a day the commodity is not
    served. `received` is the stock that arrives at the start of each day, so a
    delivery can be issued on the day it lands. Never issue more than is in stock: the
    issue is cut back to what is left and the balance settles at 0. A blank day writes
    nothing and leaves the stock where it was.
    """
    balance: list[float] = []
    issued: list[float] = []
    stock = opening
    for due_today, added, served in zip(ration, received, ration.notna()):
        stock += added
        if not served:
            balance.append(BLANK)
            issued.append(BLANK)
            continue
        issued_today = min(due_today, stock)
        balance.append(stock)
        issued.append(issued_today)
        stock -= issued_today
    return pd.DataFrame({"balance": balance, "consumption": issued})


def _sum(*parts: pd.Series) -> pd.Series:
    """Add columns up row by row, staying blank only when every part is blank."""
    return pd.concat(parts, axis=1).sum(axis=1, min_count=1)


def _to_rupees(report: pd.DataFrame, money: tuple[str, ...]) -> pd.DataFrame:
    """Turn the money columns from paisa into rupees, as the sheets are written."""
    columns = list(money)
    report[columns] = report[columns] / 100
    return report
