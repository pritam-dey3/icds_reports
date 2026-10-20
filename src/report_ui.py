"""The two report sheets, drawn as the paper writes them.

`calculation` works out the figures and `reports` lays the closing `Total` row under
them; this module only decides how a sheet is presented: which band heads each group
of columns, how a closed day shows, and how the sheet holds one corner still while it
scrolls both ways. The same layout feeds the exporter, so a file and the screen can
never disagree.
"""

from datetime import date
from functools import partial
from typing import NamedTuple

import flet as ft

import calculation
import data
import reports
import theme as t
from state import State

SABJI = reports.SABJI.key
REGISTER = reports.REGISTER.key

SABJI_CAPTION = reports.SABJI_CAPTION

# Every line has a fixed height, so the frozen date column stays level with the figures
# beside it and the header strip stays level with them as they move.
BAND_HEIGHT = 38
SUB_HEIGHT = 30
ROW_HEIGHT = 34
TOTAL_HEIGHT = 46
DATE_WIDTH = 84

# The pin between the date column and the rest of the sheet.
_FROZEN_EDGE = ft.Border(right=ft.BorderSide(1, t.BORDER_STRONG))

# The ledger groups reuse each commodity's tile colour as a very light wash.
_LEDGER_TINTS = {
    "rice_g": t.BLUE[0],
    "masoor_dal_g": t.PINK[0],
    "mustard_oil_ml": t.AMBER[0],
    "iodised_salt_g": t.MINT[0],
}


class Column(NamedTuple):
    """One sheet column: the band it sits under, its own heading, its tint."""

    group: str
    label: str
    tint: str = t.TABLE_HEADER
    muted: bool = False


def _ledger_columns() -> dict[str, Column]:
    """Each commodity's balance and consumption, grouped under its own name."""
    columns: dict[str, Column] = {}
    for item, (balance, consumption) in calculation.LEDGER_COLUMNS.items():
        tint = _LEDGER_TINTS[item]
        columns[balance] = Column(data.ITEM_LABELS[item], "Balance", tint)
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

    The sheet is taller and wider than a phone, so it owns its own viewport: the
    bands and headings sit in a strip above the scroll region, and the date column
    sits to its left, leaving one corner pinned in both directions. Only the figures
    scroll sideways, so the strip is kept level with them as they move.
    """
    columns, rows, days = _parts(state, name)
    widths = [
        _width(column, [row[index] for row in rows])
        for index, column in enumerate(columns)
    ]

    band, subheads = _headings(columns, widths)
    header = ft.Row(
        expand=True,
        scroll=ft.ScrollMode.HIDDEN,
        controls=[ft.Column(spacing=0, controls=[band, subheads])],
    )
    figures = ft.Row(
        expand=True,
        scroll=ft.Scrollbar(thickness=6, radius=t.RADIUS_PILL),
        controls=[_figures(columns, rows, widths, days)],
    )
    _keep_level(header, figures)

    return ft.Column(
        expand=True,
        spacing=0,
        controls=[
            ft.Row(
                spacing=0,
                controls=[
                    _box(
                        t.label("Date", t.REPORT_HEADER),
                        DATE_WIDTH,
                        BAND_HEIGHT + SUB_HEIGHT,
                        t.TABLE_HEADER,
                        ft.Alignment.CENTER_LEFT,
                    ),
                    header,
                ],
            ),
            ft.Column(
                expand=True,
                scroll=ft.Scrollbar(thickness=6, radius=t.RADIUS_PILL),
                controls=[ft.Row(spacing=0, controls=[_dates_column(days), figures])],
            ),
        ],
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
            ft.Icon(ft.Icons.SWAP_HORIZ, size=16, color=t.PRIMARY_600),
            t.label("Swipe table to view all columns", t.HINT),
            ft.Icon(ft.Icons.SWAP_HORIZ, size=16, color=t.PRIMARY_600),
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
    return max(62, min(230, longest * 8 + 20))


# Drawing the sheet


def _dates_column(days: list[tuple[date, bool]]) -> ft.Control:
    """The frozen column: a day per line, pinned while the figures slide past."""
    return ft.Container(
        width=DATE_WIDTH,
        border=_FROZEN_EDGE,
        content=ft.Column(
            spacing=0,
            controls=[
                *[
                    _box(
                        t.label(
                            _date_label(day),
                            t.REPORT_CELL,
                            t.CLOSED_INK if closed else None,
                            nowrap=True,
                        ),
                        DATE_WIDTH,
                        ROW_HEIGHT,
                        t.CLOSED_ROW if closed else t.SURFACE,
                        ft.Alignment.CENTER_LEFT,
                    )
                    for day, closed in days
                ],
                _box(
                    t.label("Total", t.TOTAL_LABEL),
                    DATE_WIDTH,
                    TOTAL_HEIGHT,
                    t.SURFACE_MUTED,
                    ft.Alignment.CENTER_LEFT,
                ),
            ],
        ),
    )


def _figures(
    columns: list[Column],
    rows: list[list[str]],
    widths: list[int],
    days: list[tuple[date, bool]],
) -> ft.Control:
    """A line per day, then the closing row."""
    return ft.Column(
        spacing=0,
        controls=[
            *[
                ft.Row(
                    spacing=0,
                    controls=[
                        _box(
                            t.label(
                                value,
                                t.REPORT_CELL,
                                t.TEXT_TERTIARY if column.muted else None,
                                nowrap=True,
                            ),
                            widths[index],
                            ROW_HEIGHT,
                            t.CLOSED_ROW if closed else t.SURFACE,
                            ft.Alignment.CENTER_RIGHT,
                        )
                        for index, (column, value) in enumerate(
                            zip(columns, line, strict=True)
                        )
                    ],
                )
                for line, (_, closed) in zip(rows[:-1], days, strict=True)
            ],
            _total_row(columns, rows[-1], widths),
        ],
    )


def _keep_level(header: ft.Row, figures: ft.Row) -> None:
    """Hold the header strip over the columns the figures have scrolled to.

    The two live in separate scroll views — one cannot sit still while the other
    slides — so either one moving drags the other with it. A shared flag stops the
    echo of a followed move from following straight back again.
    """
    moving = {"now": False}

    async def follow(source: ft.Row, target: ft.Row, event: ft.OnScrollEvent) -> None:
        if moving["now"]:
            return
        moving["now"] = True
        try:
            await target.scroll_to(offset=event.pixels)
        finally:
            moving["now"] = False

    header.on_scroll = partial(follow, header, figures)
    figures.on_scroll = partial(follow, figures, header)


def _headings(
    columns: list[Column], widths: list[int]
) -> tuple[ft.Control, ft.Control]:
    """The group band and the sub-heading line, with groups spanning their columns."""
    band: list[ft.Control] = []
    subheads: list[ft.Control] = []
    index = 0
    while index < len(columns):
        column = columns[index]
        run = 1
        while index + run < len(columns) and columns[index + run].group == column.group:
            run += 1
        if column.group:
            band.append(
                _box(
                    t.label(
                        column.group, t.GROUP_HEADER, _group_ink(column), nowrap=True
                    ),
                    sum(widths[index : index + run]),
                    BAND_HEIGHT,
                    column.tint,
                    ft.Alignment.CENTER,
                )
            )
            for offset in range(run):
                below = columns[index + offset]
                subheads.append(
                    _box(
                        t.label(below.label, t.REPORT_HEADER, nowrap=True),
                        widths[index + offset],
                        SUB_HEIGHT,
                        below.tint,
                        ft.Alignment.CENTER,
                    )
                )
        else:
            band.append(
                _box(
                    t.label(column.label, t.REPORT_HEADER, nowrap=True),
                    widths[index],
                    BAND_HEIGHT,
                    column.tint,
                    ft.Alignment.CENTER,
                )
            )
            subheads.append(
                _box(None, widths[index], SUB_HEIGHT, column.tint, ft.Alignment.CENTER)
            )
        index += run
    return ft.Row(spacing=0, controls=band), ft.Row(spacing=0, controls=subheads)


def _total_row(
    columns: list[Column], values: list[str], widths: list[int]
) -> ft.Control:
    """The closing line: bold, tinted, and a balance annotated as the closing one."""
    return ft.Row(
        spacing=0,
        controls=[
            _box(
                _total_cell(column, value),
                widths[index],
                TOTAL_HEIGHT,
                column.tint,
                ft.Alignment.CENTER,
            )
            for index, (column, value) in enumerate(zip(columns, values, strict=True))
        ],
    )


def _total_cell(column: Column, value: str) -> ft.Control:
    """A total cell; a balance says it closes the month rather than sums it."""
    if column.label.startswith("Balance") and value:
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


def _box(
    content: ft.Control | None,
    width: int,
    height: int,
    bgcolor: str,
    align: ft.Alignment,
) -> ft.Container:
    """A cell of a fixed size, so two stacked columns stay in step."""
    return ft.Container(
        width=width,
        height=height,
        bgcolor=bgcolor,
        alignment=align,
        padding=ft.Padding.symmetric(horizontal=8),
        content=content,
    )
