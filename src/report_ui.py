"""The two report sheets, read-only.

`calculation` works out the figures and `reports` lays the closing `Total` row under
them; this module only turns a sheet into controls. The sheet is wider than a phone,
so it scrolls sideways, and nothing here is given a fixed size.
"""

import flet as ft
import pandas as pd

import calculation
import reports
from state import State

SABJI = "sabji"
REGISTER = "register"

SABJI_CAPTION = reports.SABJI_CAPTION

HEADER_SIZE = 11
CELL_SIZE = 12


def sheet(state: State, name: str) -> ft.Control:
    """One sheet, chosen by name: the sabji bill, or the stock register."""
    if name == REGISTER:
        return table(reports.stock_register(state), calculation.REGISTER_MONEY_COLUMNS)
    return table(reports.sabji_bill(state), calculation.SABJI_MONEY_COLUMNS)


def table(report: pd.DataFrame, money: tuple[str, ...]) -> ft.Control:
    """A report as a read-only table: headings, the month's days, then the total."""
    columns = [
        ft.DataColumn(
            label=ft.Text(
                name, size=HEADER_SIZE, weight=ft.FontWeight.W_600, no_wrap=True
            )
        )
        for name in report.columns
    ]

    lines = reports.as_text(report, money)
    last = len(lines) - 1
    rows = [
        ft.DataRow(
            cells=[
                ft.DataCell(
                    ft.Text(
                        value,
                        size=CELL_SIZE,
                        no_wrap=True,
                        weight=ft.FontWeight.W_600 if index == last else None,
                    )
                )
                for value in line
            ]
        )
        for index, line in enumerate(lines)
    ]

    return ft.Row(
        scroll=ft.ScrollMode.AUTO,
        controls=[
            ft.DataTable(
                columns=columns, rows=rows, column_spacing=18, divider_thickness=0.4
            )
        ],
    )
