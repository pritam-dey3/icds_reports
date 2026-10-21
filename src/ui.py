"""The four-step worksheet, drawn with the design's component library.

The app is one column: a header, the month, the step rail, then a card per section.
The cards scroll and the footer does not. Every value is a field in place, and every
edit is saved as it is made — there is no Save button and no confirm step.
"""

from collections.abc import Callable
from datetime import date, datetime
from functools import partial
from numbers import Real
from typing import Any

import flet as ft
import pandas as pd

import components as c
import data
import export
import report_ui
import reports
import theme as t
from calculation import CHILDREN, MOTHER
from state import State

STEPS = ("Costings", "Attendance", "Inventory", "Report")

# The step that shows the sheets. It is the one step without a month row above it and
# the one whose table needs a viewport of its own.
REPORT_STEP = len(STEPS) - 1

# A table's name column against one of its number fields. The name gets the larger
# share, so a commodity can wrap to two lines while its figures stay on one.
LABEL_FLEX = 7
FIELD_FLEX = 3

# How much of the rail's width a day's count takes, against its date.
DATE_FLEX = 4

# Each head's tint: the band over the group, and the wash behind its cells.
HEAD_TINTS = {
    MOTHER: (t.MOTHER_BAND, t.MOTHER_BG),
    CHILDREN: (t.CHILDREN_BAND, t.CHILDREN_BG),
}

# The item tiles: the same commodity looks the same on every screen.
ITEM_TILES: dict[str, tuple[ft.IconData, tuple[str, str]]] = {
    "egg": (ft.Icons.EGG, t.AMBER),
    "vegetables": (ft.Icons.ECO, t.MINT),
    "potato": (ft.Icons.CIRCLE, t.AMBER),
    "morning_snack": (ft.Icons.SOUP_KITCHEN, t.BLUE),
    "rice_g": (ft.Icons.RICE_BOWL, t.BLUE),
    "masoor_dal_g": (ft.Icons.GRAIN, t.PINK),
    "mustard_oil_ml": (ft.Icons.WATER_DROP, t.AMBER),
    "iodised_salt_g": (ft.Icons.AC_UNIT, t.MINT),
}


class Workspace:
    """The screen's own state — the open step, the open sheet — and its way back.

    `touch` records an edit and saves it; `rebuild` does that and draws the screen
    again, for the changes that alter its shape. `failure_shown` remembers that a
    write failure has been announced, so a queue of failed writes warns once.
    """

    def __init__(
        self,
        state: State,
        on_edit: Callable[[], None] | None = None,
        on_rebuild: Callable[[], None] | None = None,
        *,
        files: ft.FilePicker | None = None,
    ):
        self.state = state
        self.step = 0
        self.report_sheet = report_ui.SABJI
        self.files = files
        self.failure_shown = False
        self._on_edit = on_edit or (lambda: None)
        self._on_rebuild = on_rebuild or (lambda: None)

    def touch(self) -> None:
        """An edit in place: hand it to the store, leaving the screen as it is.

        The store writes in the background, so a failure is reported by the writer
        rather than here.
        """
        self._on_edit()

    def rebuild(self) -> None:
        """A change of shape: save it and draw the screen again."""
        self.touch()
        self._on_rebuild()


def build(workspace: Workspace) -> list[ft.BaseControl]:
    """The whole screen: a scrolling column of cards above a fixed footer."""
    return [
        ft.SafeArea(
            expand=True,
            avoid_intrusions_left=False,
            avoid_intrusions_right=False,
            content=ft.Column(
                expand=True,
                spacing=0,
                controls=[_content(workspace), footer(workspace)],
            ),
        )
    ]


def _content(workspace: Workspace) -> ft.Control:
    """The steps above the footer.

    The report is a table, so it is given the screen rather than a place in a page:
    the header strip only stays still while the figures scroll under it, which needs
    a boundary of its own. Every other step scrolls as one long page.
    """
    at_report = workspace.step == REPORT_STEP
    padded = ft.Container(
        width=t.CONTENT_WIDTH,
        padding=ft.Padding.only(
            left=t.SPACE_3, right=t.SPACE_3, top=t.SPACE_2, bottom=t.SPACE_4
        ),
        expand=at_report,
        content=ft.Column(
            expand=at_report,
            spacing=t.SPACE_3,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
            controls=_page(workspace),
        ),
    )
    if at_report:
        return padded
    return ft.Column(
        expand=True,
        scroll=ft.ScrollMode.AUTO,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        controls=[padded],
    )


def _page(workspace: Workspace) -> list[ft.Control]:
    """The content above the footer: the header, the steps and the open step."""
    return [header(workspace), _stepper(workspace), _body(workspace)]


# The shell: header, month, steps, footer


def header(workspace: Workspace) -> ft.Control:
    """The title, the month beside it, and the menu."""
    return ft.Row(
        spacing=t.SPACE_2,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
        controls=[
            ft.Text("ICDS Reports", style=t.PAGE_TITLE, expand=True),
            _month_row(workspace),
            menu(workspace),
        ],
    )


def menu(workspace: Workspace) -> ft.PopupMenuButton:
    """The app's only menu, behind the overflow button."""
    return ft.PopupMenuButton(
        icon=ft.Icons.MORE_VERT,
        icon_size=20,
        padding=4,
        tooltip="Menu",
        items=[
            ft.PopupMenuItem(
                content="Reset data",
                icon=ft.Icons.RESTART_ALT,
                key="menu-reset",
                on_click=partial(_ask_to_reset, workspace),
            )
        ],
    )


def _month_row(workspace: Workspace) -> ft.Container:
    """The month the whole worksheet is about, opening the list of months."""
    return ft.Container(
        key="month-picker",
        height=34,
        padding=ft.Padding.symmetric(horizontal=10),
        bgcolor=t.SURFACE,
        border=t.field_border(),
        border_radius=t.RADIUS_PILL,
        alignment=ft.Alignment.CENTER,
        tooltip="Change month",
        on_click=partial(_pick_month, workspace),
        content=ft.Row(
            spacing=6,
            tight=True,
            controls=[
                ft.Icon(ft.Icons.CALENDAR_MONTH, size=16, color=t.TEXT_SECONDARY),
                t.label(data.month_label(workspace.state.month), t.CELL),
                ft.Icon(ft.Icons.KEYBOARD_ARROW_DOWN, size=16, color=t.TEXT_SECONDARY),
            ],
        ),
    )


def step_state(workspace: Workspace, index: int) -> str:
    """Where a step sits against the open one: passed, current or upcoming."""
    if index < workspace.step:
        return "passed"
    if index == workspace.step:
        return "current"
    return "upcoming"


def _stepper(workspace: Workspace) -> ft.Row:
    """Four nodes on a rail: how long the job is, and how much of it is done."""
    return ft.Row(
        spacing=0,
        controls=[_step_column(workspace, index) for index in range(len(STEPS))],
    )


def _step_column(workspace: Workspace, index: int) -> ft.Column:
    """One step: its node on the rail, and its name beneath."""
    status = step_state(workspace, index)
    return ft.Column(
        expand=True,
        spacing=t.SPACE_1,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        controls=[
            ft.Row(
                spacing=0,
                controls=[
                    _rail(workspace, index, before=True),
                    _node(workspace, index, status),
                    _rail(workspace, index, before=False),
                ],
            ),
            ft.Text(
                f"{index + 1}. {STEPS[index]}",
                style=t.STEP_LABEL_ACTIVE if status == "current" else t.STEP_LABEL,
                text_align=ft.TextAlign.CENTER,
                no_wrap=True,
                overflow=ft.TextOverflow.ELLIPSIS,
            ),
        ],
    )


def _rail(workspace: Workspace, index: int, *, before: bool) -> ft.Container:
    """The rail between two nodes: lit up to the open step, quiet after it."""
    edge = index if before else index + 1
    if not 0 < edge < len(STEPS):
        return ft.Container(expand=True, height=2)
    lit = workspace.step >= edge
    return ft.Container(
        expand=True, height=2, bgcolor=t.PRIMARY_500 if lit else t.BORDER_STRONG
    )


def _node(workspace: Workspace, index: int, status: str) -> ft.Container:
    """One node: a tick once passed, the step's number while it is open or ahead.

    The ring around the open node is drawn for every step, filled only for the open
    one, so all four labels keep the same baseline.
    """
    filled = status != "upcoming"
    circle = ft.Container(
        width=30,
        height=30,
        border_radius=t.RADIUS_PILL,
        bgcolor=t.PRIMARY_600 if filled else t.SURFACE,
        border=None if filled else ft.Border.all(1.5, t.BORDER_STRONG),
        alignment=ft.Alignment.CENTER,
        content=(
            ft.Icon(ft.Icons.CHECK, size=16, color=t.TEXT_INVERSE)
            if status == "passed"
            else t.label(
                str(index + 1), t.STEP_NUMBER if filled else t.STEP_NUMBER_AHEAD
            )
        ),
    )
    return ft.Container(
        key=f"step-{index + 1}",
        padding=4,
        border_radius=t.RADIUS_PILL,
        tooltip=f"Open {STEPS[index]}",
        on_click=partial(_open_step, workspace, index),
        content=ft.Container(
            padding=5,
            border_radius=t.RADIUS_PILL,
            bgcolor=t.PRIMARY_100 if status == "current" else None,
            content=circle,
        ),
    )


def footer(workspace: Workspace) -> ft.Container:
    """The one thing that never scrolls: where you are and where you can go."""
    return ft.Container(
        bgcolor=t.SURFACE,
        border=ft.Border(top=ft.BorderSide(1, t.BORDER_SUBTLE)),
        shadow=t.sheet_shadow(),
        padding=ft.Padding.symmetric(horizontal=t.SPACE_3, vertical=t.SPACE_2),
        content=ft.Column(
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                ft.Container(width=t.CONTENT_WIDTH, content=_navigation(workspace))
            ],
        ),
    )


def _navigation(workspace: Workspace) -> ft.Row:
    """The step change, from either end; the report swaps in the export pair."""
    if workspace.step == REPORT_STEP:
        buttons: list[ft.Control] = [
            c.button(
                "Export CSV",
                key="export-csv",
                icon=ft.Icons.DOWNLOAD,
                variant="outlined",
                expand=True,
                on_click=partial(_export, workspace, "csv"),
            ),
            c.button(
                "Download PDF",
                key="export-pdf",
                icon=ft.Icons.PICTURE_AS_PDF,
                expand=True,
                on_click=partial(_export, workspace, "pdf"),
            ),
        ]
    else:
        buttons = [
            c.button(
                "Back",
                key="back",
                icon=ft.Icons.ARROW_BACK,
                variant="outlined",
                expand=True,
                disabled=workspace.step == 0,
                on_click=partial(_open_step, workspace, max(0, workspace.step - 1)),
            ),
            c.button(
                "Next",
                key="next",
                icon=ft.Icons.ARROW_FORWARD,
                expand=True,
                on_click=partial(
                    _open_step, workspace, min(REPORT_STEP, workspace.step + 1)
                ),
            ),
        ]
    return ft.Row(spacing=t.SPACE_3, controls=buttons)


def save_failed(workspace: Workspace, page: ft.Page | None = None) -> None:
    """A small word when a write does not land; a successful save stays silent."""
    (page or ft.context.page).show_dialog(
        ft.SnackBar(
            content=t.label("Couldn't save this change", t.HINT, t.TEXT_INVERSE),
            behavior=ft.SnackBarBehavior.FLOATING,
            bgcolor=t.TEXT,
            show_close_icon=True,
            close_icon_color=t.TEXT_INVERSE,
            margin=ft.Margin.only(left=t.SPACE_4, right=t.SPACE_4, bottom=t.SPACE_2),
            duration=ft.Duration(seconds=5),
            action=ft.SnackBarAction(
                label="Retry",
                text_color=t.PRIMARY_100,
                on_click=partial(_retry, workspace),
            ),
            on_dismiss=partial(_toast_dismissed, workspace),
        )
    )


def _toast_dismissed(workspace: Workspace, event: Any = None) -> None:
    """Let a later failed write speak again once this toast is gone."""
    workspace.failure_shown = False


def _body(workspace: Workspace) -> ft.Control:
    """The open step's content."""
    builder = (_costings, _attendance, _inventory, _report)[workspace.step]
    return builder(workspace)


# Step 1 — Costings


def _costings(workspace: Workspace) -> ft.Control:
    """The two per-head tables: what a head costs, and what a head is given."""
    return ft.Column(
        spacing=t.SPACE_3,
        horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        controls=[
            c.section(
                ft.Icons.PAID,
                t.BLUE,
                "Costings",
                _rate_table(workspace, "costs", data.COST_ITEMS, "cost", total=True),
            ),
            c.section(
                ft.Icons.INVENTORY_2,
                t.MINT,
                "Per-head inventory",
                _rate_table(
                    workspace, "inventory", data.STOCK_ITEMS, "inventory", total=False
                ),
            ),
        ],
    )


def _rate_table(
    workspace: Workspace,
    table: str,
    items: tuple[str, ...],
    key_prefix: str,
    *,
    total: bool,
) -> ft.Control:
    """One row per item, under a band per head and a heading per day type.

    `table` names the state table being edited; `key_prefix` names the fields that
    edit it, which is shorter (`cost` for the `costs` table).
    """
    rows: list[ft.Control] = [_head_band(), _rate_headings()]
    rows += [_rate_row(workspace, table, item, key_prefix) for item in items]
    if total:
        rows.append(_total_row(workspace.state.costs))
    return c.table(rows)


def _head_band() -> ft.Control:
    """The band that names the two heads and spans the day types beneath them."""
    return ft.Row(
        spacing=0,
        controls=[
            c.cell(None, flex=LABEL_FLEX, bgcolor=t.TABLE_HEADER),
            c.cell(
                t.label("Mother", t.GROUP_HEADER, t.MOTHER_INK),
                flex=FIELD_FLEX * 2,
                bgcolor=HEAD_TINTS[MOTHER][0],
            ),
            c.cell(
                t.label("Children", t.GROUP_HEADER, t.CHILDREN_INK),
                flex=FIELD_FLEX * 2,
                bgcolor=HEAD_TINTS[CHILDREN][0],
            ),
        ],
    )


def _rate_headings() -> ft.Control:
    """The day types, each heading the field beneath it."""
    return c.row([
        c.heading_cell("Item", flex=LABEL_FLEX, align=ft.Alignment.CENTER_LEFT),
        *[
            c.heading_cell(day_type, flex=FIELD_FLEX, bgcolor=HEAD_TINTS[head][1])
            for head, day_type in data.RATE_COLUMNS
        ],
    ])


def _item_cell(item: str) -> ft.Container:
    """A commodity's tile and name, at the head of its row."""
    icon, colors = ITEM_TILES[item]
    return c.cell(
        ft.Row(
            spacing=t.SPACE_1,
            controls=[
                c.icon_tile(icon, colors),
                ft.Text(_item_label(item), style=t.CELL, expand=True),
            ],
        ),
        flex=LABEL_FLEX,
        align=None,
    )


def _number_cell(field: ft.TextField) -> ft.Container:
    """A number field inside a table cell."""
    return c.cell(field, flex=FIELD_FLEX, padding=(3, 4))


def _rate_row(
    workspace: Workspace, table: str, item: str, key_prefix: str
) -> ft.Control:
    """One item and its four rates, each a field in place."""
    return c.row([
        _item_cell(item),
        *[
            _number_cell(
                c.number_field(
                    _rate(workspace.state, table, item, head, day_type),
                    key=f"{key_prefix}-{item}-{head}-{day_type}",
                    on_change=partial(
                        _set_rate, workspace, table, item, head, day_type
                    ),
                )
            )
            for head, day_type in data.RATE_COLUMNS
        ],
    ])


def _total_row(costs: pd.DataFrame) -> ft.Control:
    """The total per head of the items the editor lists, as the paper sheet has it."""
    totals = costs.loc[list(data.COST_ITEMS)].sum()
    return c.row(
        [
            c.cell(
                ft.Row(
                    spacing=4,
                    controls=[
                        ft.Icon(ft.Icons.FUNCTIONS, size=14, color=t.TEXT_SECONDARY),
                        t.label("Total per head", t.TOTAL_LABEL),
                    ],
                ),
                flex=LABEL_FLEX,
                align=None,
                bgcolor=t.SURFACE_MUTED,
            ),
            *[
                c.cell(
                    t.label(str(int(totals[(head, day_type)])), t.TOTAL_VALUE),
                    flex=FIELD_FLEX,
                    bgcolor=HEAD_TINTS[head][1],
                )
                for head, day_type in data.RATE_COLUMNS
            ],
        ],
        rule=False,
    )


def _item_label(item: str) -> str:
    """An item's name, with its unit appended where the quantity carries one."""
    unit = data.ITEM_UNITS.get(item)
    return f"{data.ITEM_LABELS[item]} ({unit})" if unit else data.ITEM_LABELS[item]


def _opening_stock(state: State, item: str) -> int:
    """A commodity's opening stock as the whole number the field shows."""
    amount = state.opening.at[item, "opening"]
    # pandas hands back a numpy number, which is a `Real` but not an `int`.
    return int(float(amount)) if isinstance(amount, Real) else 0


def _rate(state: State, table: str, item: str, head: str, day_type: str) -> int:
    """One rate out of a shared table."""
    return int(getattr(state, table).at[item, (head, day_type)])


# Step 2 — Attendance


def _attendance(workspace: Workspace) -> ft.Control:
    """Holidays first, because they are what closes a day, then the daily counts."""
    return ft.Column(
        spacing=t.SPACE_3,
        horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        controls=[
            c.section(
                ft.Icons.CALENDAR_MONTH, t.MINT, "Holidays", _holidays(workspace)
            ),
            c.section(
                ft.Icons.GROUPS, t.BLUE, "Daily attendance", _attendance_grid(workspace)
            ),
        ],
    )


def _holidays(workspace: Workspace) -> ft.Control:
    """The month's closed days, as chips, and the way to close another."""
    closed = workspace.state.holidays()
    if closed:
        listed: ft.Control = ft.Row(
            wrap=True,
            spacing=10,
            run_spacing=10,
            controls=[_chip(workspace, day) for day in closed],
        )
    else:
        listed = c.empty_state(
            ft.Icons.CALENDAR_MONTH,
            "No closed days this month",
            "Every day is a working day.",
        )
    return ft.Column(
        spacing=t.SPACE_3,
        horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        controls=[
            t.label(data.month_label(workspace.state.month), t.SECTION_TITLE),
            listed,
            c.button(
                "Add holiday",
                key="add-holiday",
                icon=ft.Icons.ADD,
                variant="tinted",
                on_click=partial(_pick_holiday, workspace),
            ),
        ],
    )


def _chip(workspace: Workspace, day: date) -> ft.Container:
    """One closed day: the weekday, then the date, and the button that reopens it."""
    return ft.Container(
        padding=ft.Padding.only(left=10, right=6, top=6, bottom=8),
        bgcolor=t.MOTHER_BG,
        border=t.hairline(),
        border_radius=t.RADIUS_FIELD,
        content=ft.Row(
            spacing=6,
            tight=True,
            vertical_alignment=ft.CrossAxisAlignment.START,
            controls=[
                ft.Column(
                    spacing=0,
                    controls=[
                        t.label(f"{day:%a}", t.CHIP_WEEKDAY),
                        t.label(f"{day:%d}", t.CHIP_DATE),
                        t.label(f"{day:%b}", t.CHIP_MONTH),
                    ],
                ),
                ft.Container(
                    key=f"holiday-delete-{day.isoformat()}",
                    width=24,
                    height=24,
                    border=t.hairline(),
                    border_radius=t.RADIUS_PILL,
                    alignment=ft.Alignment.CENTER,
                    tooltip="Reopen this day",
                    on_click=partial(_delete_holiday, workspace, day),
                    content=ft.Icon(ft.Icons.CLOSE, size=14, color=t.TEXT_SECONDARY),
                ),
            ],
        ),
    )


def _attendance_grid(workspace: Workspace) -> ft.Control:
    """One row per day of the month: the date, then the two counts."""
    state = workspace.state
    days = list(data.days_in(state.month))
    rows: list[ft.Control] = [
        c.row([
            c.heading_cell("Date", flex=DATE_FLEX, align=ft.Alignment.CENTER_LEFT),
            c.heading_cell("Mother", flex=FIELD_FLEX, bgcolor=HEAD_TINTS[MOTHER][1]),
            c.heading_cell(
                "Children", flex=FIELD_FLEX, bgcolor=HEAD_TINTS[CHILDREN][1]
            ),
        ]),
        *[_attendance_row(workspace, day, last=day == days[-1]) for day in days],
    ]
    return c.table(rows)


def _attendance_row(
    workspace: Workspace, day: date, *, last: bool = False
) -> ft.Control:
    """A day's two counts. A closed day carries none, so its cells stay empty."""
    state = workspace.state
    closed = state.is_holiday(day)
    return c.row(
        [
            c.cell(
                ft.Text(
                    f"{day:%a %d}", style=t.CELL, color=t.CLOSED_INK if closed else None
                ),
                flex=DATE_FLEX,
                align=ft.Alignment.CENTER_LEFT,
            ),
            *[
                _number_cell(
                    c.number_field(
                        None if closed else count,
                        key=f"attendance-{day.isoformat()}-{head}",
                        on_change=partial(_set_counts, workspace, day, head),
                        disabled=closed,
                    )
                )
                for head, count in zip(
                    ("mothers", "children"), state.counts(day), strict=True
                )
            ],
        ],
        bgcolor=t.CLOSED_ROW if closed else None,
        rule=not last,
    )


# Step 3 — Inventory


def _inventory(workspace: Workspace) -> ft.Control:
    """Where each commodity starts, and what arrives during the month."""
    return ft.Column(
        spacing=t.SPACE_3,
        horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        controls=[
            c.section(
                ft.Icons.INVENTORY_2,
                t.MINT,
                "Opening stock",
                _opening_stock_table(workspace),
            ),
            c.section(
                ft.Icons.LOCAL_SHIPPING,
                t.BLUE,
                "Added inventory",
                _deliveries(workspace),
            ),
        ],
    )


def _opening_stock_table(workspace: Workspace) -> ft.Control:
    """One row per commodity, in the order the register lists them."""
    state = workspace.state
    rows: list[ft.Control] = [
        c.row([
            c.heading_cell(
                "Commodity", flex=LABEL_FLEX, align=ft.Alignment.CENTER_LEFT
            ),
            c.heading_cell("Opening", flex=FIELD_FLEX),
        ])
    ]
    for item in data.STOCK_ITEMS:
        rows.append(
            c.row(
                [
                    _item_cell(item),
                    _number_cell(
                        c.number_field(
                            _opening_stock(state, item),
                            key=f"opening-{item}",
                            on_change=partial(_set_opening, workspace, item),
                        )
                    ),
                ],
                rule=item != data.STOCK_ITEMS[-1],
            )
        )
    return c.table(rows)


def _deliveries(workspace: Workspace) -> ft.Column:
    """One bordered row per delivery, or the empty state that asks for one."""
    additions = workspace.state.additions()
    rows: list[ft.Control] = (
        [_delivery(workspace, index, row) for index, row in enumerate(additions)]
        if additions
        else [
            c.empty_state(
                ft.Icons.LOCAL_SHIPPING,
                "No deliveries added yet",
                "Tap the button below to add a delivery.",
            )
        ]
    )
    rows.append(
        c.button(
            "Add item",
            key="add-delivery",
            icon=ft.Icons.ADD,
            variant="tinted",
            on_click=partial(_add_delivery, workspace),
        )
    )
    return ft.Column(
        spacing=8, horizontal_alignment=ft.CrossAxisAlignment.STRETCH, controls=rows
    )


def _delivery(workspace: Workspace, index: int, row: dict[str, Any]) -> ft.Control:
    """One delivery: which commodity, which day, how much."""
    item = str(row["item"])
    day = date.fromisoformat(str(row["date"]))
    icon, colors = ITEM_TILES[item]
    return ft.Container(
        bgcolor=t.SURFACE_MUTED,
        border=t.hairline(),
        border_radius=t.RADIUS_FIELD,
        padding=10,
        content=ft.Column(
            spacing=6,
            controls=[
                ft.Row(
                    spacing=t.SPACE_2,
                    controls=[
                        c.icon_tile(icon, colors),
                        ft.Dropdown(
                            key=f"delivery-{index}-item",
                            value=item,
                            expand=True,
                            dense=True,
                            text_size=13,
                            border=ft.NoInputBorder(),
                            content_padding=ft.Padding.symmetric(horizontal=4),
                            options=[
                                ft.DropdownOption(
                                    key=stock, text=data.ITEM_LABELS[stock]
                                )
                                for stock in data.STOCK_ITEMS
                            ],
                            on_select=partial(_set_delivery_item, workspace, index),
                        ),
                        ft.IconButton(
                            icon=ft.Icons.DELETE_OUTLINE,
                            key=f"delivery-{index}-delete",
                            tooltip="Delete this delivery",
                            icon_color=t.TEXT_SECONDARY,
                            on_click=partial(_remove_delivery, workspace, index),
                        ),
                    ],
                ),
                ft.Row(
                    spacing=t.SPACE_2,
                    controls=[
                        c.button(
                            f"{day:%d %b %Y}",
                            key=f"delivery-{index}-date",
                            icon=ft.Icons.CALENDAR_MONTH,
                            variant="outlined",
                            on_click=partial(_pick_delivery_day, workspace, index),
                        ),
                        c.number_field(
                            float(row["amount"]),
                            key=f"delivery-{index}-amount",
                            on_change=partial(_set_delivery_amount, workspace, index),
                            flex=FIELD_FLEX,
                        ),
                        t.label(data.ITEM_UNITS[item], t.HINT),
                    ],
                ),
            ],
        ),
    )


# Step 4 — Report


def _report(workspace: Workspace) -> ft.Control:
    """Both sheets, one at a time, with the export pair in the footer."""
    return c.section(
        ft.Icons.DESCRIPTION,
        t.BLUE,
        f"Report — {data.month_label(workspace.state.month)}",
        ft.Column(
            expand=True,
            spacing=t.SPACE_3,
            controls=[
                _sheet_switch(workspace),
                report_ui.hint(),
                report_ui.sheet(workspace.state, workspace.report_sheet),
            ],
        ),
        expand=True,
    )


def _sheet_switch(workspace: Workspace) -> ft.SegmentedButton:
    """The two sheets, one of them marked as the one on screen."""
    return ft.SegmentedButton(
        key="report-sheet",
        allow_empty_selection=False,
        selected=[workspace.report_sheet],
        segments=[
            ft.Segment(value=option.key, label=ft.Text(option.title))
            for option in reports.SHEETS.values()
        ],
        style=ft.ButtonStyle(
            bgcolor={ft.ControlState.SELECTED: t.PRIMARY_100},
            color={
                ft.ControlState.SELECTED: t.PRIMARY_600,
                ft.ControlState.DEFAULT: t.TEXT_SECONDARY,
            },
            side=ft.BorderSide(1.5, t.BORDER_STRONG),
            shape=ft.RoundedRectangleBorder(radius=t.RADIUS_BAND),
            padding=ft.Padding.symmetric(horizontal=10, vertical=4),
            text_style=ft.TextStyle(size=13, weight=ft.FontWeight.W_600),
        ),
        on_change=partial(_switch_sheet, workspace),
    )


# Edits


def _whole(text: str) -> int | None:
    """A whole number from a field's text: blank is 0, anything else unreadable is `None`."""
    text = text.strip()
    if not text:
        return 0
    try:
        return max(0, int(float(text)))
    except ValueError:
        return None


def _open_step(
    workspace: Workspace, index: int, event: ft.Event[ft.Control] | None = None
) -> None:
    """Show one of the four steps."""
    workspace.step = index
    workspace.rebuild()


def _switch_sheet(workspace: Workspace, event: ft.Event[ft.SegmentedButton]) -> None:
    """Show the other report."""
    workspace.report_sheet = event.control.selected[0]
    workspace.rebuild()


def _month_keys(state: State) -> list[str]:
    """The months the picker offers, with the open one first if it is older."""
    keys = data.months_offered()
    if state.month not in keys:
        keys.insert(0, state.month)
    return keys


def _month_option(workspace: Workspace, key: str) -> ft.Container:
    """One month in the picker, ticked when it is the open one."""
    current = key == workspace.state.month
    return ft.Container(
        key=f"month-{key}",
        height=40,
        padding=ft.Padding.symmetric(horizontal=8),
        bgcolor=t.PRIMARY_100 if current else None,
        border_radius=t.RADIUS_FIELD,
        on_click=partial(_open_month, workspace, key),
        content=ft.Row(
            controls=[
                ft.Text(data.month_label(key), style=t.CELL, expand=True),
                ft.Icon(ft.Icons.CHECK, size=16, color=t.PRIMARY_600, visible=current),
            ]
        ),
    )


def _pick_month(workspace: Workspace, event: Any = None) -> None:
    """Offer the months, newest first, with the open month ticked."""
    ft.context.page.show_dialog(
        ft.AlertDialog(
            modal=True,
            title=t.label("Month", t.DIALOG_TITLE),
            content=ft.Column(
                spacing=2,
                height=340,
                scroll=ft.ScrollMode.AUTO,
                controls=[
                    _month_option(workspace, key)
                    for key in _month_keys(workspace.state)
                ],
            ),
        )
    )


def _open_month(workspace: Workspace, key: str, event: Any = None) -> None:
    """Open another month, which is kept as it was left."""
    ft.context.page.pop_dialog()
    workspace.state.select_month(key)
    workspace.rebuild()


def _commit(
    workspace: Workspace, event: ft.Event[ft.TextField], apply: Callable[[int], None]
) -> None:
    """Read a number field, apply the value it holds, and save.

    Unreadable text leaves the value as it was; blank means 0.
    """
    value = _whole(event.control.value)
    if value is None:
        return
    apply(value)
    workspace.touch()


def _set_rate(
    workspace: Workspace,
    table: str,
    item: str,
    head: str,
    day_type: str,
    event: ft.Event[ft.TextField],
) -> None:
    """Record one rate. A blank field means 0, which means not served."""

    def apply(value: int) -> None:
        getattr(workspace.state, table).loc[item, (head, day_type)] = value

    _commit(workspace, event, apply)


def _set_opening(
    workspace: Workspace, item: str, event: ft.Event[ft.TextField]
) -> None:
    """Record one commodity's opening stock."""

    def apply(value: int) -> None:
        workspace.state.opening.loc[item, "opening"] = value

    _commit(workspace, event, apply)


def _set_counts(
    workspace: Workspace, day: date, head: str, event: ft.Event[ft.TextField]
) -> None:
    """Record one of a day's two counts, leaving the other as it was."""

    def apply(value: int) -> None:
        workspace.state.set_count(day, head, value)

    _commit(workspace, event, apply)


def _retry(workspace: Workspace, event: Any = None) -> None:
    """Ask for the last edit to be written again."""
    workspace.rebuild()


def _delete_holiday(workspace: Workspace, day: date, event: Any = None) -> None:
    """Reopen a day, bringing its counts back."""
    workspace.state.remove_holiday(day)
    workspace.rebuild()


def _pick_day(
    workspace: Workspace,
    help_text: str,
    on_picked: Callable[[ft.Event[ft.DatePicker]], None],
) -> None:
    """Open a date picker over the open month."""
    days = list(data.days_in(workspace.state.month))
    ft.context.page.show_dialog(
        ft.DatePicker(
            first_date=days[0],
            last_date=days[-1],
            value=days[0],
            help_text=help_text,
            on_change=on_picked,
        )
    )


def _pick_holiday(workspace: Workspace, event: Any = None) -> None:
    """Ask for the day to close."""
    _pick_day(workspace, "Add a holiday", partial(_holiday_picked, workspace))


def _holiday_picked(workspace: Workspace, event: ft.Event[ft.DatePicker]) -> None:
    """Close the day that was picked."""
    picked = _picked_date(event)
    if picked is not None:
        workspace.state.add_holiday(picked)
        ft.context.page.pop_dialog()
        workspace.rebuild()


def _add_delivery(workspace: Workspace, event: Any = None) -> None:
    """Start a new delivery row on the month's first day."""
    first = next(data.days_in(workspace.state.month))
    workspace.state.add_delivery(data.STOCK_ITEMS[0], first, 0)
    workspace.rebuild()


def _remove_delivery(workspace: Workspace, index: int, event: Any = None) -> None:
    """Drop a delivery row."""
    workspace.state.remove_delivery(index)
    workspace.rebuild()


def _set_delivery_item(
    workspace: Workspace, index: int, event: ft.Event[ft.Dropdown]
) -> None:
    """Record which commodity a delivery brought."""
    workspace.state.set_delivery(index, item=event.control.value)
    workspace.rebuild()


def _set_delivery_amount(
    workspace: Workspace, index: int, event: ft.Event[ft.TextField]
) -> None:
    """Record how much a delivery brought."""

    def apply(value: int) -> None:
        workspace.state.set_delivery(index, amount=value)

    _commit(workspace, event, apply)


def _pick_delivery_day(workspace: Workspace, index: int, event: Any = None) -> None:
    """Ask for the day a delivery arrived."""
    _pick_day(workspace, "Date added", partial(_delivery_day_picked, workspace, index))


def _delivery_day_picked(
    workspace: Workspace, index: int, event: ft.Event[ft.DatePicker]
) -> None:
    """Record the day that was picked, clamped into the month."""
    picked = _picked_date(event)
    if picked is not None:
        workspace.state.set_delivery(index, day=picked)
        ft.context.page.pop_dialog()
        workspace.rebuild()


def _picked_date(event: ft.Event[ft.DatePicker]) -> date | None:
    """The date a date picker confirmed, from either of the places Flet puts it.

    Flet sends the picked day back as UTC, so midnight of the 5th east of UTC arrives
    as the evening of the 4th. Reading the day back in local time undoes that shift.
    """
    value = event.control.value
    if value is None:
        value = event.data
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.astimezone().date()
    if isinstance(value, date):
        return value
    return None


async def _export(workspace: Workspace, kind: str, event: Any = None) -> None:
    """Build the open sheet as a file, then let the platform save it."""
    chosen = reports.SHEETS[workspace.report_sheet]
    headings, rows = report_ui.grid(workspace.state, chosen.key)
    month = data.month_label(workspace.state.month)
    content = (
        export.csv_bytes(headings, rows)
        if kind == "csv"
        else export.pdf_bytes("ICDS Reports", month, chosen.title, headings, rows)
    )
    if workspace.files is None:
        return
    await workspace.files.save_file(
        dialog_title=f"Save {chosen.title}",
        file_name=export.file_name(chosen.title, month, kind),
        allowed_extensions=[kind],
        src_bytes=content,
    )


def _ask_to_reset(workspace: Workspace, event: Any = None) -> None:
    """Ask before throwing every edit away."""
    page = ft.context.page

    def close(inner: Any = None) -> None:
        page.pop_dialog()

    def reset(inner: Any = None) -> None:
        workspace.state.reset()
        workspace.step = 0
        page.pop_dialog()
        workspace.rebuild()

    page.show_dialog(
        ft.AlertDialog(
            modal=True,
            title=t.label("Reset all data?", t.DIALOG_TITLE),
            content=t.label(
                "Every edit goes back to the shipped defaults, and the saved copy "
                "is deleted.",
                t.DIALOG_BODY,
            ),
            actions=[
                ft.TextButton(content="Cancel", key="reset-cancel", on_click=close),
                c.button(
                    "Reset", key="reset-confirm", variant="destructive", on_click=reset
                ),
            ],
        )
    )
