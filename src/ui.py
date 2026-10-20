"""The four-step worksheet: the month picker, the three input steps and the report.

The layout is structure only: rows and columns with flex weights, never a fixed
width or height, so Flutter sizes everything for the screen it is on. The screen
redraws when its shape changes — a step, a month, a holiday, a delivery, a reset.
Typing in a field only records the value and saves it, because the field already
shows what was typed.
"""

from collections.abc import Callable
from datetime import date, datetime
from functools import partial
from numbers import Real
from typing import Any

import flet as ft
import pandas as pd

import data
import report_ui
import reports
from state import State

STEPS = ("Costings", "Attendance", "Inventory", "Report")

MUTED = ft.Colors.GREY_700
HEADER_SIZE = 11

# How much room a row's label takes, against one rate field. A label is twice as
# wide as a field, which keeps a name readable without crowding the four fields.
LABEL_FLEX = 4
FIELD_FLEX = 2


class Workspace:
    """The screen's own state — the open step and the open sheet — and its way back.

    `touch` records an edit and saves it; `rebuild` does that and draws the screen
    again, for the changes that alter its shape.
    """

    def __init__(
        self,
        state: State,
        on_edit: Callable[[], None] | None = None,
        on_rebuild: Callable[[], None] | None = None,
    ):
        self.state = state
        self.step = 0
        self.report_sheet = report_ui.SABJI
        self._on_edit = on_edit or (lambda: None)
        self._on_rebuild = on_rebuild or (lambda: None)

    def touch(self) -> None:
        """An edit in place: save it, leave the screen as it is."""
        self._on_edit()

    def rebuild(self) -> None:
        """A change of shape: save it and draw the screen again."""
        self._on_edit()
        self._on_rebuild()


def app_bar(workspace: Workspace) -> ft.AppBar:
    """The title bar, with the app's only menu behind the overflow button."""
    return ft.AppBar(
        title=ft.Text("ICDS Reports"),
        actions=[
            ft.PopupMenuButton(
                icon=ft.Icons.MORE_VERT,
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
        ],
    )


def build(workspace: Workspace) -> list[ft.BaseControl]:
    """The whole screen, drawn from the workspace's state.

    One column, top to bottom. The page does the scrolling; nothing here is given a
    fixed size, so the column is as tall as its content and as wide as the screen.
    """
    return [
        ft.SafeArea(
            content=ft.Column(
                spacing=12,
                controls=[
                    _month_row(workspace),
                    _stepper(workspace),
                    ft.Divider(),
                    _body(workspace),
                    ft.Divider(),
                    _navigation(workspace),
                ],
            )
        )
    ]


# The frame: month, steps, navigation


def _month_row(workspace: Workspace) -> ft.Dropdown:
    """The month the whole worksheet is about."""
    keys = data.months_offered()
    if workspace.state.month not in keys:
        keys.insert(0, workspace.state.month)
    return ft.Dropdown(
        label="Month",
        value=workspace.state.month,
        key="month-picker",
        options=[
            ft.DropdownOption(key=key, text=data.month_label(key)) for key in keys
        ],
        on_select=partial(_change_month, workspace),
    )


def _stepper(workspace: Workspace) -> ft.Row:
    """The four steps, each ticked once it has been passed."""
    buttons: list[ft.Control] = []
    for index, label in enumerate(STEPS):
        Button = ft.FilledButton if index == workspace.step else ft.OutlinedButton
        buttons.append(
            Button(
                content=ft.Text(f"{index + 1} {label}", size=12),
                icon=ft.Icons.CHECK if index < workspace.step else None,
                key=f"step-{index + 1}",
                on_click=partial(_open_step, workspace, index),
            )
        )
    return ft.Row(wrap=True, spacing=6, run_spacing=6, controls=buttons)


def _navigation(workspace: Workspace) -> ft.Row:
    """Back and Next: the same step change, from either end."""
    return ft.Row(
        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        controls=[
            ft.OutlinedButton(
                content="Back",
                icon=ft.Icons.ARROW_BACK,
                key="back",
                disabled=workspace.step == 0,
                on_click=partial(_open_step, workspace, max(0, workspace.step - 1)),
            ),
            ft.FilledButton(
                content="Next",
                icon=ft.Icons.ARROW_FORWARD,
                key="next",
                disabled=workspace.step == len(STEPS) - 1,
                on_click=partial(
                    _open_step, workspace, min(len(STEPS) - 1, workspace.step + 1)
                ),
            ),
        ],
    )


def _body(workspace: Workspace) -> ft.Control:
    """The open step's content."""
    builder = (_costings, _attendance, _inventory, _report)[workspace.step]
    return builder(workspace)


# Step 1 — Costings


def _costings(workspace: Workspace) -> ft.Control:
    """The two per-head tables: what a head costs, and what a head is given."""
    return ft.Column(
        spacing=16,
        controls=[
            _heading(
                "Costings",
                "Cost per head per day, in paisa. A rate of 0 means not served.",
            ),
            _per_head_grid(workspace, "costs", data.COST_ITEMS, "cost"),
            _total_row(workspace.state.costs),
            _heading(
                "Per-head inventory",
                "Quantity per head per serving day, in the item's own unit.",
            ),
            _per_head_grid(workspace, "inventory", data.STOCK_ITEMS, "inventory"),
        ],
    )


def _per_head_grid(
    workspace: Workspace, table: str, items: tuple[str, ...], prefix: str
) -> ft.Control:
    """One row per item: its name, then a field for each head and day type."""
    rows: list[ft.Control] = [
        _header("Item", *[heading for _, _, heading in data.RATE_COLUMNS])
    ]
    for item in items:
        rows.append(
            ft.Row(
                spacing=6,
                controls=[
                    ft.Text(_item_label(item), size=12, expand=LABEL_FLEX),
                    *[
                        _number_field(
                            value=_rate(workspace.state, table, item, head, day_type),
                            key=f"{prefix}-{item}-{head}-{day_type}",
                            on_change=partial(
                                _set_rate, workspace, table, item, head, day_type
                            ),
                        )
                        for head, day_type, _ in data.RATE_COLUMNS
                    ],
                ],
            )
        )
    return ft.Column(spacing=8, controls=rows)


def _total_row(costs: pd.DataFrame) -> ft.Control:
    """The total per head of the items the editor lists, as the paper sheet has it."""
    totals = costs.loc[list(data.COST_ITEMS)].sum()
    return ft.Container(
        padding=8,
        border_radius=6,
        bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
        content=ft.Row(
            spacing=6,
            controls=[
                ft.Text(
                    "Total per head",
                    size=12,
                    weight=ft.FontWeight.W_600,
                    expand=LABEL_FLEX,
                ),
                *[
                    ft.Text(
                        str(int(totals[(head, day_type)])),
                        size=12,
                        weight=ft.FontWeight.W_600,
                        text_align=ft.TextAlign.RIGHT,
                        expand=FIELD_FLEX,
                    )
                    for head, day_type, _ in data.RATE_COLUMNS
                ],
            ],
        ),
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
        spacing=16,
        controls=[
            _heading(
                "Holidays",
                "A closed day carries no counts and leaves the stock where it was.",
            ),
            _holidays(workspace),
            _heading(
                "Daily attendance",
                "Whole heads, minimum 0. Every Sunday starts closed.",
            ),
            _attendance_grid(workspace),
        ],
    )


def _holidays(workspace: Workspace) -> ft.Column:
    """One row per closed day, each with the button that reopens it."""
    rows: list[ft.Control] = [
        ft.Row(
            spacing=6,
            controls=[
                ft.Text(day.strftime("%d %b %Y"), size=12, expand=3),
                ft.Text(day.strftime("%A"), size=11, color=MUTED, expand=2),
                ft.IconButton(
                    icon=ft.Icons.DELETE_OUTLINE,
                    key=f"holiday-delete-{day.isoformat()}",
                    tooltip="Reopen this day",
                    on_click=partial(_delete_holiday, workspace, day),
                ),
            ],
        )
        for day in workspace.state.holidays()
    ]
    rows.append(
        ft.TextButton(
            content="Add holiday",
            icon=ft.Icons.ADD,
            key="add-holiday",
            on_click=partial(_pick_holiday, workspace),
        )
    )
    return ft.Column(spacing=4, controls=rows)


def _attendance_grid(workspace: Workspace) -> ft.Column:
    """One row per day of the month: the date, then the two counts."""
    rows: list[ft.Control] = [_header("Date", "Mother", "Children")]
    state = workspace.state
    for day in data.days_in(state.month):
        fields: list[ft.Control]
        if state.is_holiday(day):
            fields = [ft.Text("Holiday", size=12, color=MUTED, expand=4)]
        else:
            mothers, children = state.counts(day)
            fields = [
                _number_field(
                    value=mothers,
                    key=f"attendance-{day.isoformat()}-mothers",
                    on_change=partial(_set_counts, workspace, day, "mothers"),
                ),
                _number_field(
                    value=children,
                    key=f"attendance-{day.isoformat()}-children",
                    on_change=partial(_set_counts, workspace, day, "children"),
                ),
            ]
        rows.append(
            ft.Row(
                spacing=6,
                controls=[
                    ft.Text(day.strftime("%a %d"), size=12, expand=LABEL_FLEX),
                    *fields,
                ],
            )
        )
    return ft.Column(spacing=8, controls=rows)


# Step 3 — Inventory


def _inventory(workspace: Workspace) -> ft.Control:
    """Where each commodity starts, and what arrives during the month."""
    state = workspace.state
    opening: list[ft.Control] = [_header("Commodity", "Opening")]
    for item in data.STOCK_ITEMS:
        opening.append(
            ft.Row(
                spacing=6,
                controls=[
                    ft.Text(_item_label(item), size=12, expand=LABEL_FLEX),
                    _number_field(
                        value=_opening_stock(state, item),
                        key=f"opening-{item}",
                        on_change=partial(_set_opening, workspace, item),
                    ),
                ],
            )
        )

    return ft.Column(
        spacing=16,
        controls=[
            _heading("Opening stock", "The stock each commodity's ledger starts from."),
            ft.Column(spacing=8, controls=opening),
            _heading(
                "Added inventory",
                "A delivery counts from its own day on, and is clamped into the month.",
            ),
            _deliveries(workspace),
        ],
    )


def _deliveries(workspace: Workspace) -> ft.Column:
    """One card per delivery: which item, which day, how much."""
    rows: list[ft.Control] = [
        _delivery(workspace, index, row)
        for index, row in enumerate(workspace.state.additions())
    ]
    rows.append(
        ft.TextButton(
            content="Add item",
            icon=ft.Icons.ADD,
            key="add-delivery",
            on_click=partial(_add_delivery, workspace),
        )
    )
    return ft.Column(spacing=8, controls=rows)


def _delivery(workspace: Workspace, index: int, row: dict) -> ft.Control:
    """One delivery row."""
    item = str(row["item"])
    day = date.fromisoformat(str(row["date"]))
    return ft.Container(
        padding=10,
        border=ft.Border.all(1, ft.Colors.OUTLINE_VARIANT),
        border_radius=8,
        content=ft.Column(
            spacing=8,
            controls=[
                ft.Row(
                    spacing=6,
                    controls=[
                        ft.Dropdown(
                            label="Item",
                            key=f"delivery-{index}-item",
                            value=item,
                            expand=3,
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
                            on_click=partial(_remove_delivery, workspace, index),
                        ),
                    ],
                ),
                ft.Row(
                    spacing=6,
                    controls=[
                        ft.OutlinedButton(
                            content=ft.Text(day.strftime("%d %b %Y"), size=12),
                            icon=ft.Icons.CALENDAR_MONTH,
                            key=f"delivery-{index}-date",
                            on_click=partial(_pick_delivery_day, workspace, index),
                        ),
                        _number_field(
                            value=float(row["amount"]),
                            key=f"delivery-{index}-amount",
                            on_change=partial(_set_delivery_amount, workspace, index),
                        ),
                        ft.Text(data.ITEM_UNITS[item], size=11, color=MUTED),
                    ],
                ),
            ],
        ),
    )


# Step 4 — Report


def _report(workspace: Workspace) -> ft.Control:
    """Both sheets, one at a time, chosen by the switch above them."""
    return ft.Column(
        spacing=10,
        controls=[
            ft.Text(
                f"Report — {data.month_label(workspace.state.month)}",
                size=16,
                weight=ft.FontWeight.W_600,
            ),
            ft.Text(report_ui.SABJI_CAPTION, size=11, color=MUTED),
            ft.SegmentedButton(
                key="report-sheet",
                allow_empty_selection=False,
                selected=[workspace.report_sheet],
                segments=[
                    ft.Segment(value=option.key, label=ft.Text(option.title))
                    for option in reports.SHEETS.values()
                ],
                on_change=partial(_switch_sheet, workspace),
            ),
            report_ui.sheet(workspace.state, workspace.report_sheet),
        ],
    )


# Building blocks


def _heading(title: str, subtitle: str) -> ft.Control:
    """A step's title and the one line that explains it."""
    return ft.Column(
        spacing=2,
        controls=[
            ft.Text(title, size=15, weight=ft.FontWeight.W_600),
            ft.Text(subtitle, size=11, color=MUTED),
        ],
    )


def _header(name: str, *fields: str) -> ft.Row:
    """A grid's heading row: the name column, then one heading over each field."""
    return ft.Row(
        spacing=6,
        controls=[
            ft.Text(name, size=HEADER_SIZE, color=MUTED, expand=LABEL_FLEX),
            *[
                ft.Text(
                    label,
                    size=HEADER_SIZE,
                    color=MUTED,
                    text_align=ft.TextAlign.RIGHT,
                    expand=FIELD_FLEX,
                )
                for label in fields
            ],
        ],
    )


def _number_field(
    value: Any,
    key: str,
    on_change: Callable[[ft.Event[ft.TextField]], None],
    *,
    expand: int = FIELD_FLEX,
) -> ft.TextField:
    """A plain whole-number input: digits only, right-aligned, sized by its row."""
    return ft.TextField(
        value="" if value is None else str(value).removesuffix(".0"),
        expand=expand,
        text_size=13,
        text_align=ft.TextAlign.RIGHT,
        keyboard_type=ft.KeyboardType.NUMBER,
        input_filter=ft.InputFilter(allow=True, regex_string=r"^\d*$"),
        dense=True,
        key=key,
        on_change=on_change,
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


def _change_month(workspace: Workspace, event: ft.Event[ft.Dropdown]) -> None:
    """Open another month, which is kept as it was left."""
    if event.control.value:
        workspace.state.select_month(event.control.value)
        workspace.rebuild()


def _set_rate(
    workspace: Workspace,
    table: str,
    item: str,
    head: str,
    day_type: str,
    event: ft.Event[ft.TextField],
) -> None:
    """Record one rate. A blank field means 0, which means not served."""
    value = _whole(event.control.value)
    if value is None:
        return
    getattr(workspace.state, table).loc[item, (head, day_type)] = value
    workspace.touch()


def _set_opening(
    workspace: Workspace, item: str, event: ft.Event[ft.TextField]
) -> None:
    """Record one commodity's opening stock."""
    value = _whole(event.control.value)
    if value is None:
        return
    workspace.state.opening.loc[item, "opening"] = value
    workspace.touch()


def _set_counts(
    workspace: Workspace, day: date, head: str, event: ft.Event[ft.TextField]
) -> None:
    """Record one of a day's two counts, leaving the other as it was."""
    value = _whole(event.control.value)
    if value is None:
        return
    workspace.state.set_count(day, head, value)
    workspace.touch()


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
    value = _whole(event.control.value)
    if value is None:
        return
    workspace.state.set_delivery(index, amount=value)
    workspace.touch()


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
    """The date a date picker confirmed, from either of the places Flet puts it."""
    value = event.control.value
    if value is None:
        value = event.data
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return None


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
            title=ft.Text("Reset all data?"),
            content=ft.Text(
                "Every edit goes back to the shipped defaults, and the saved copy "
                "is deleted."
            ),
            actions=[
                ft.TextButton(content="Cancel", key="reset-cancel", on_click=close),
                ft.FilledButton(content="Reset", key="reset-confirm", on_click=reset),
            ],
        )
    )
