"""The two report sheets, drawn as the paper writes them.

`calculation` works out the figures and `reports` lays the closing `Total` row under
them; this module only decides how a sheet is presented: which band heads each group
of columns, how a closed day shows, and how the sheet holds its date column and
heading still while the figures scroll under them. The same layout feeds the exporter,
so a file and the screen can never disagree.

The sheet is one `DataTable2`, which keeps the heading and the first column pinned by
itself, so there are no scroll positions to keep in step by hand.
"""

from datetime import date
from typing import NamedTuple

import flet as ft
from flet_datatable2 import DataColumn2, DataRow2, DataTable2

import calculation
import data
import reports
import theme as t
from state import State

SABJI = reports.SABJI.key
REGISTER = reports.REGISTER.key

# Every line has a fixed height, so the pinned date column stays level with the figures
# beside it and the heading stays level with them as they move.
HEAD_HEIGHT = 52
ROW_HEIGHT = 28
TOTAL_HEIGHT = 38
DATE_WIDTH = 68

# The ledger groups reuse each commodity's tile colour as a very light wash.
_LEDGER_TINTS = {
    "rice_g": t.BLUE[0],
    "masoor_dal_g": t.PINK[0],
    "mustard_oil_ml": t.AMBER[0],
    "iodised_salt_g": t.MINT[0],
}


class Column(NamedTuple):
    """One sheet column: the band it sits under, its own heading, its tint.

    `muted` writes the figures in a lighter ink; `closing` marks a balance, whose
    total is the stock left at month end rather than a sum.
    """

    group: str
    label: str
    tint: str = t.TABLE_HEADER
    muted: bool = False
    closing: bool = False


def _ledger_columns() -> dict[str, Column]:
    """Each commodity's balance and consumption, grouped under its own name."""
    columns: dict[str, Column] = {}
    for item, (balance, consumption) in calculation.LEDGER_COLUMNS.items():
        tint = _LEDGER_TINTS[item]
        columns[balance] = Column(data.ITEM_LABELS[item], "Balance", tint, closing=True)
        columns[consumption] = Column(data.ITEM_LABELS[item], "Consumption", tint)
    return columns


# How each sheet's columns are headed on screen. A heading the app does not know
# keeps its own name and gets no band, so a new column can never break the sheet.
SABJI_COLUMNS: dict[str, Column] = {
    "Total Beneficiaries": Column("", "Total beneficiaries"),
    "Pregnant+Lactating Mon/Wed/Fri": Column(
        "Pregnant + lactating", "Mon/Wed/Fri", t.MOTHER_BAND
    ),
    "Pregnant+Lactating Tue/Thu/Sat": Column(
        "Pregnant + lactating", "Tue/Thu/Sat", t.MOTHER_BAND
    ),
    "Children Mon/Wed/Fri": Column("Children", "Mon/Wed/Fri", t.CHILDREN_BAND),
    "Children Tue/Thu/Sat": Column("Children", "Tue/Thu/Sat", t.CHILDREN_BAND),
    "Other Children Mon/Wed/Fri": Column("Other children", "Mon/Wed/Fri", muted=True),
    "Other Children Tue/Thu/Sat": Column("Other children", "Tue/Thu/Sat", muted=True),
    "Total Egg Cost": Column("", "Total egg cost"),
    "Veg Mother": Column("Vegetables", "Mother"),
    "Veg Child": Column("Vegetables", "Child"),
    "Potato Mother": Column("Potato", "Mother"),
    "Potato Child": Column("Potato", "Child"),
    "Total Veg+Potato": Column("", "Total veg + potato"),
    "Morning Snack Tue/Thu/Sat": Column("Morning snack", "Tue/Thu/Sat"),
    "Morning Snack Mon/Wed/Fri": Column("Morning snack", "Mon/Wed/Fri"),
    "Daily Total Cost": Column("", "Daily total cost"),
}

REGISTER_COLUMNS: dict[str, Column] = {
    "MS (Morning Snack) Beneficiaries": Column("Attendance", "Morning snack"),
    "HCM Children 6m-6y": Column("Attendance", "Children 6m–6y"),
    "HCM Pregnant+Lactating": Column("Attendance", "Pregnant + lactating"),
    "THR (SAM+SUW)": Column("Attendance", "THR (SAM + SUW)"),
    **_ledger_columns(),
    "Commodity 5 Balance": Column("Commodity 5", "Balance", muted=True),
    "Commodity 5 Consumption": Column("Commodity 5", "Consumption", muted=True),
    "Morning Snacks & THR Value Rs (Item 1)": Column(
        "Money", "Morning snacks & THR (item 1)"
    ),
    "Morning Snacks & THR Value Rs (Item 2 - Egg)": Column(
        "Money", "Morning snacks & THR (item 2 – egg)"
    ),
    "Vegetable Value Rs": Column("Money", "Vegetable value"),
    "Potato Value Rs": Column("Money", "Potato value"),
}

SPECS = {SABJI: SABJI_COLUMNS, REGISTER: REGISTER_COLUMNS}


def sheet(state: State, name: str) -> ft.Control:
    """One sheet, chosen by name: the sabji bill, or the stock register.

    The sheet is taller and wider than a phone, so it owns its viewport. `DataTable2`
    pins the heading row and the date column against the scrolling figures, which
    leaves the corner that names both still in each direction.
    """
    columns, rows, days = _parts(state, name)
    widths = [
        _width(column, [row[index] for row in rows])
        for index, column in enumerate(columns)
    ]

    return ft.Container(
        expand=True,
        bgcolor=t.SURFACE,
        border=t.hairline(),
        border_radius=t.RADIUS_BAND,
        clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
        content=DataTable2(
            expand=True,
            columns=[_date_head(), *_heads(columns, widths)],
            rows=[
                *[
                    _day_row(day, closed, line, columns, widths)
                    for line, (day, closed) in zip(rows[:-1], days, strict=True)
                ],
                _total_row(columns, rows[-1], widths),
            ],
            fixed_top_rows=1,
            fixed_left_columns=1,
            fixed_columns_color=t.SURFACE,
            fixed_corner_color=t.TABLE_HEADER,
            heading_row_height=HEAD_HEIGHT,
            heading_row_color=t.TABLE_HEADER,
            data_row_height=ROW_HEIGHT,
            divider_thickness=1,
            column_spacing=0,
            horizontal_margin=0,
            visible_horizontal_scroll_bar=True,
        ),
    )


def grid(state: State, name: str) -> tuple[list[str], list[list[str]]]:
    """The sheet as plain headings and text rows, the way a file holds it."""
    columns, rows, days = _parts(state, name)
    headings = ["Date", *[_flat_heading(column) for column in columns]]
    dates = [_date_label(day) for day, _ in days]
    return headings, [
        [date, *row] for date, row in zip([*dates, "Total"], rows, strict=True)
    ]


def hint() -> ft.Control:
    """The one line that tells the user the sheet is wider than the phone."""
    return ft.Row(
        alignment=ft.MainAxisAlignment.CENTER,
        spacing=6,
        controls=[
            ft.Icon(ft.Icons.SWAP_HORIZ, size=14, color=t.PRIMARY_600),
            t.label("Swipe table to view all columns", t.HINT),
            ft.Icon(ft.Icons.SWAP_HORIZ, size=14, color=t.PRIMARY_600),
        ],
    )


# Reading the sheet


def _parts(
    state: State, name: str
) -> tuple[list[Column], list[list[str]], list[tuple[date, bool]]]:
    """The columns, the figures as text, and each closed day with its row."""
    chosen = reports.SHEETS[name]
    frame = chosen.build(state)
    spec = SPECS[name]
    columns = [spec.get(heading, Column("", heading)) for heading in frame.columns[1:]]
    rows = [line[1:] for line in reports.as_text(frame, chosen.money_columns)]
    days = [(day, state.is_holiday(day)) for day in data.days_in(state.month)]
    return columns, rows, days


def _date_label(day: date) -> str:
    """A day in the date column: a weekday and a day number."""
    return f"{day:%a} {day:%d}"


def _flat_heading(column: Column) -> str:
    """A column's name when it is written flat, as a file needs it."""
    return f"{column.group} {column.label}".strip() if column.group else column.label


def _width(column: Column, values: list[str]) -> int:
    """Enough room for the longest value and the heading that sits over it."""
    longest = max([len(column.label), *(len(value) for value in values)])
    return max(54, min(200, longest * 7 + 16))


# Drawing the sheet


def _date_head() -> DataColumn2:
    """The heading over the pinned date column."""
    return DataColumn2(
        fixed_width=DATE_WIDTH,
        label=ft.Container(
            width=DATE_WIDTH,
            height=HEAD_HEIGHT,
            bgcolor=t.TABLE_HEADER,
            alignment=ft.Alignment.CENTER_LEFT,
            padding=ft.Padding.symmetric(horizontal=6),
            content=t.label("Date", t.REPORT_HEADER),
        ),
    )


def _heads(columns: list[Column], widths: list[int]) -> list[DataColumn2]:
    """A heading per column, naming its group only on the run's first column.

    A table has no merged cells, so the group is written once at the start of its run
    and the tint carries the band across the rest; the second line names the column.
    """
    return [
        DataColumn2(
            fixed_width=widths[index],
            label=_head_cell(
                widths[index],
                column.tint,
                column.group if _opens(columns, index) else "",
                column.label,
                _group_ink(column),
            ),
        )
        for index, column in enumerate(columns)
    ]


def _opens(columns: list[Column], index: int) -> bool:
    """Whether this column is the first of its group's run."""
    return index == 0 or columns[index - 1].group != columns[index].group


def _head_cell(
    width: int, bgcolor: str, group: str, label: str, ink: str
) -> ft.Container:
    """Two stacked lines on the column's tint: the group over the column's own name."""
    return ft.Container(
        width=width,
        height=HEAD_HEIGHT,
        bgcolor=bgcolor,
        alignment=ft.Alignment.CENTER,
        padding=ft.Padding.symmetric(horizontal=4),
        content=ft.Column(
            spacing=0,
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                t.label(group, t.GROUP_HEADER, ink, nowrap=True),
                t.label(label, t.REPORT_HEADER, nowrap=True),
            ],
        ),
    )


def _day_row(
    day: date, closed: bool, values: list[str], columns: list[Column], widths: list[int]
) -> DataRow2:
    """One day: its date, then a figure per column."""
    tint = t.CLOSED_ROW if closed else t.SURFACE
    return DataRow2(
        specific_row_height=ROW_HEIGHT,
        cells=[
            _date_cell(_date_label(day), tint, ink=t.CLOSED_INK if closed else None),
            *[
                _cell(
                    t.label(
                        value,
                        t.REPORT_CELL,
                        t.TEXT_TERTIARY if column.muted else None,
                        nowrap=True,
                    ),
                    widths[index],
                    tint,
                    ft.Alignment.CENTER_RIGHT,
                )
                for index, (column, value) in enumerate(
                    zip(columns, values, strict=True)
                )
            ],
        ],
    )


def _total_row(columns: list[Column], values: list[str], widths: list[int]) -> DataRow2:
    """The closing line: bold, tinted, and a balance annotated as the closing one."""
    return DataRow2(
        specific_row_height=TOTAL_HEIGHT,
        cells=[
            _date_cell("Total", t.SURFACE_MUTED, style=t.TOTAL_LABEL),
            *[
                _cell(
                    _total_cell(column, value),
                    widths[index],
                    column.tint,
                    ft.Alignment.CENTER,
                )
                for index, (column, value) in enumerate(
                    zip(columns, values, strict=True)
                )
            ],
        ],
    )


def _date_cell(
    label: str,
    bgcolor: str,
    *,
    style: ft.TextStyle = t.REPORT_CELL,
    ink: str | None = None,
) -> ft.DataCell:
    """A cell of the pinned date column."""
    return _cell(
        t.label(label, style, ink, nowrap=True),
        DATE_WIDTH,
        bgcolor,
        ft.Alignment.CENTER_LEFT,
    )


def _total_cell(column: Column, value: str) -> ft.Control:
    """A total cell; a balance says it closes the month rather than sums it."""
    if column.closing and value:
        return ft.Column(
            spacing=0,
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.END,
            controls=[
                t.label(value, t.TOTAL_VALUE, nowrap=True),
                t.label("closing", t.HINT, nowrap=True),
            ],
        )
    return t.label(value, t.TOTAL_VALUE, nowrap=True)


def _group_ink(column: Column) -> str:
    """Groups are named in their own ink; neutral bands keep the page ink."""
    return {t.MOTHER_BAND: t.MOTHER_INK, t.CHILDREN_BAND: t.CHILDREN_INK}.get(
        column.tint, t.TEXT
    )


def _cell(
    content: ft.Control, width: int, bgcolor: str, align: ft.Alignment
) -> ft.DataCell:
    """A figure of a fixed width, so a row's cells stay in step with its headings."""
    return ft.DataCell(
        ft.Container(
            width=width,
            bgcolor=bgcolor,
            alignment=align,
            padding=ft.Padding.symmetric(horizontal=6),
            content=content,
        )
    )
