"""The two reports, ready for the screen.

`calculation` works out the figures; this module puts the closing `Total` row under
them and turns every cell into the text the sheet shows: money to two decimals, and
an empty cell wherever nothing is written.
"""

import math
from typing import Any

import pandas as pd

import calculation
from state import State

SABJI_CAPTION = "A blank cell is a closed day, or an item that is not served that day."


def sabji_bill(state: State) -> pd.DataFrame:
    """The sabji bill: one row per day, then the closing total."""
    report = calculation.sabji_bill(state.attendance_frame(), state.costs)
    return _with_total(report, calculation.SABJI_MONEY_COLUMNS)


def stock_register(state: State) -> pd.DataFrame:
    """The stock register: attendance, the ledger, the money, then the closing total."""
    report = calculation.stock_register(
        state.attendance_frame(),
        state.costs,
        state.inventory,
        state.opening,
        state.deliveries(),
    )
    return _with_total(report, calculation.REGISTER_MONEY_COLUMNS)


def _with_total(report: pd.DataFrame, money: tuple[str, ...]) -> pd.DataFrame:
    """Lay the closing `Total` row under the month's days."""
    total = calculation.totals(report)
    row: dict[str, Any] = {"Date": "Total"}
    row.update(total.to_dict())
    return pd.concat([report, pd.DataFrame([row])], ignore_index=True)


def as_text(table: pd.DataFrame, money: tuple[str, ...]) -> list[list[str]]:
    """Every cell as text: money to two decimals, a blank where nothing is written."""
    return [
        [_cell(row[column], column in money) for column in table.columns]
        for _, row in table.iterrows()
    ]


def _cell(value: Any, money: bool) -> str:
    """One cell's text."""
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return ""
    if isinstance(value, str):
        return value
    number = float(value)
    if money:
        return f"{number:.2f}"
    return str(int(number)) if number.is_integer() else f"{number:g}"
