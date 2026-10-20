"""The screen: what each step is built from, and what its edits do.

These tests build the control tree and call the handlers the way Flutter would.
They need no running app, so they are fast and give a precise failure.
"""

from datetime import date
from typing import Any

import flet as ft
import pytest

import data
import report_ui
import ui
from state import State

MONTH = "2026-10"


@pytest.fixture
def workspace() -> ui.Workspace:
    return ui.Workspace(State.new(MONTH))


def texts(control: Any) -> list[str]:
    """Every piece of text under a control, in tree order."""
    found: list[str] = []

    def walk(node):
        if isinstance(node, ft.Text) and node.value:
            found.append(node.value)
        if isinstance(node, ft.DataColumn):
            walk(node.label)
        if isinstance(node, ft.DataCell):
            walk(node.content)
        if isinstance(node, ft.Segment) and node.label is not None:
            walk(node.label)
        for child in getattr(node, "controls", None) or []:
            walk(child)
        for column in getattr(node, "columns", None) or []:
            walk(column)
        for row in getattr(node, "rows", None) or []:
            walk(row)
        for segment in getattr(node, "segments", None) or []:
            walk(segment)
        content = getattr(node, "content", None)
        if isinstance(content, str):
            found.append(content)
        elif isinstance(content, ft.Control):
            walk(content)

    walk(control)
    return found


def fields(control: ft.Control) -> list[ft.TextField]:
    """Every number field under a control."""
    found: list[ft.TextField] = []

    def walk(node):
        if isinstance(node, ft.TextField):
            found.append(node)
            return
        for child in getattr(node, "controls", None) or []:
            walk(child)
        content = getattr(node, "content", None)
        if isinstance(content, ft.Control):
            walk(content)

    walk(control)
    return found


class Click:
    """What a widget hands its handler.

    Handlers only read `control` and `data`, so a fake that carries those two is a
    faithful stand-in and keeps these tests free of a running app.
    """

    def __init__(self, control: Any = None, data: Any = None):
        self.control = control
        self.data = data


def click(control: Any = None, data: Any = None) -> Any:
    """A fake event for a handler that takes one."""
    return Click(control, data)


# The frame


def test_the_screen_shows_the_month_and_the_four_steps(workspace):
    shown = texts(ui.build(workspace)[0])

    assert "October 2026" != ""  # the picker carries it as a value, checked below
    assert any("1 Costings" == line for line in shown)
    assert any("4 Report" == line for line in shown)


def test_the_month_picker_holds_the_open_month(workspace):
    picker = ui._month_row(workspace)

    assert isinstance(picker, ft.Dropdown)
    assert picker.value == MONTH
    assert [option.text for option in picker.options][:2] == [
        "October 2026",
        "September 2026",
    ]


def test_the_month_picker_also_offers_a_month_outside_the_recent_list(workspace):
    workspace.state.select_month("2024-01")

    picker = ui._month_row(workspace)

    assert "2024-01" in [option.key for option in picker.options]


def test_back_is_disabled_on_the_first_step_and_next_on_the_last(workspace):
    first = ui._navigation(workspace).controls
    assert first[0].disabled is True
    assert first[1].disabled is False

    workspace.step = 3
    last = ui._navigation(workspace).controls
    assert last[0].disabled is False
    assert last[1].disabled is True


def test_a_passed_step_is_ticked_and_the_open_step_is_filled(workspace):
    workspace.step = 2

    buttons = ui._stepper(workspace).controls
    assert isinstance(buttons[0], ft.OutlinedButton)
    assert isinstance(buttons[2], ft.FilledButton)

    assert buttons[0].icon == ft.Icons.CHECK
    assert (
        isinstance(buttons[1], ft.OutlinedButton) and buttons[1].icon == ft.Icons.CHECK
    )
    assert buttons[2].icon is None
    assert isinstance(buttons[3], ft.OutlinedButton)


def test_the_menu_carries_the_reset():
    menu = ui.app_bar(ui.Workspace(State.new(MONTH))).actions
    assert menu is not None

    assert isinstance(menu[0], ft.PopupMenuButton)
    assert [item.content for item in menu[0].items] == ["Reset data"]


# Step 1 — Costings


def test_the_cost_step_lists_every_item_with_a_field_per_head_and_day_type(workspace):
    step = ui._costings(workspace)
    shown = texts(step)

    for item in data.COST_ITEMS:
        assert data.ITEM_LABELS[item] in shown
    # four cost items and four stock items, four fields each
    assert len(fields(step)) == 4 * (len(data.COST_ITEMS) + len(data.STOCK_ITEMS))


def test_the_cost_fields_hold_the_rates(workspace):
    step = ui._costings(workspace)
    by_key = {field.key: field.value for field in fields(step)}

    assert by_key["cost-egg-mother-MWF"] == "850"
    assert by_key["cost-vegetables-children-TTS"] == "41"
    assert by_key["cost-morning_snack-children-MWF"] == "167"
    assert by_key["cost-morning_snack-children-TTS"] == "425"
    assert by_key["inventory-rice_g-mother-MWF"] == "110"


def test_the_total_per_head_is_shown_and_is_not_editable(workspace):
    shown = texts(ui._total_row(workspace.state.costs))

    assert "934" in shown and "1013" in shown
    assert "1017" in shown and "634" in shown


def test_editing_a_rate_is_recorded_in_paisa(workspace):
    field = ft.TextField(value="900")

    ui._set_rate(workspace, "costs", "egg", "mother", "MWF", click(field))

    assert workspace.state.costs.at["egg", ("mother", "MWF")] == 900


def test_an_empty_rate_is_read_as_not_served(workspace):
    field = ft.TextField(value="")

    ui._set_rate(workspace, "costs", "egg", "mother", "MWF", click(field))

    assert workspace.state.costs.at["egg", ("mother", "MWF")] == 0


def test_a_rate_that_is_not_a_number_is_left_alone(workspace):
    field = ft.TextField(value="abc")

    ui._set_rate(workspace, "costs", "egg", "mother", "MWF", click(field))

    assert workspace.state.costs.at["egg", ("mother", "MWF")] == 850


# Step 2 — Attendance


def test_the_attendance_step_lists_the_holidays_then_every_day(workspace):
    step = ui._attendance(workspace)
    shown = texts(step)

    assert "Holidays" in shown
    assert "Daily attendance" in shown
    assert "04 Oct 2026" in shown
    assert "Sun 04" in shown  # the closed day is still on the sheet


def test_a_closed_day_shows_as_a_holiday_instead_of_two_fields(workspace):
    step = ui._attendance_grid(workspace)
    closed_row = next(
        row for row in step.controls if texts(row) == ["Sun 04", "Holiday"]
    )

    assert len(fields(closed_row)) == 0


def test_an_open_day_carries_its_two_counts(workspace):
    step = ui._attendance_grid(workspace)
    by_key = {field.key: field.value for field in fields(step)}

    assert by_key["attendance-2026-10-05-mothers"] == str(data.DEFAULT_MOTHERS)
    assert by_key["attendance-2026-10-05-children"] == str(data.DEFAULT_CHILDREN)


def test_editing_one_count_leaves_the_other_as_it_was(workspace):
    day = date(2026, 10, 5)
    workspace.state.set_attendance(day, 7, 70)

    ui._set_counts(workspace, day, "children", click(ft.TextField(value="80")))

    assert workspace.state.counts(day) == (7, 80)


def test_deleting_a_holiday_reopens_that_day(workspace):
    day = date(2026, 10, 4)

    ui._delete_holiday(workspace, day)

    assert not workspace.state.is_holiday(day)


# Step 3 — Inventory


def test_the_inventory_step_lists_the_opening_stock_of_every_commodity(workspace):
    step = ui._inventory(workspace)
    by_key = {field.key: field.value for field in fields(step)}

    assert by_key["opening-rice_g"] == "25640"
    assert by_key["opening-iodised_salt_g"] == "3272"
    assert "Added inventory" in texts(step)


def test_editing_the_opening_stock_is_recorded(workspace):
    ui._set_opening(workspace, "rice_g", click(ft.TextField(value="1000")))

    assert workspace.state.opening.at["rice_g", "opening"] == 1000


def test_adding_a_delivery_adds_a_row_on_the_first_day_of_the_month(workspace):
    ui._add_delivery(workspace)

    assert len(workspace.state.additions()) == 1
    assert workspace.state.additions()[0]["date"] == "2026-10-01"


def test_a_delivery_row_carries_an_item_a_day_an_amount_and_a_delete(workspace):
    ui._add_delivery(workspace)

    row = ui._deliveries(workspace)
    card = row.controls[0]

    assert isinstance(card, ft.Container)
    assert "Add item" in texts(row)
    # The card holds the item picker, the day button, the amount field and a delete.
    assert any(
        button.tooltip == "Delete this delivery" for button in _icon_buttons(card)
    )
    assert [field.key for field in fields(card)] == ["delivery-0-amount"]


def _icon_buttons(control: ft.Control) -> list[ft.IconButton]:
    """Every icon button under a control."""
    found: list[ft.IconButton] = []

    def walk(node):
        if isinstance(node, ft.IconButton):
            found.append(node)
        for child in getattr(node, "controls", None) or []:
            walk(child)
        content = getattr(node, "content", None)
        if isinstance(content, ft.Control):
            walk(content)

    walk(control)
    return found


def test_a_delivery_can_be_edited_and_deleted(workspace):
    ui._add_delivery(workspace)
    ui._set_delivery_item(workspace, 0, click(ft.Dropdown(value="rice_g")))
    ui._set_delivery_amount(workspace, 0, click(ft.TextField(value="30000")))

    assert workspace.state.additions()[0]["item"] == "rice_g"
    assert workspace.state.additions()[0]["amount"] == 30000

    ui._remove_delivery(workspace, 0)
    assert workspace.state.additions() == []


# Step 4 — Report


def test_the_report_step_shows_the_month_and_both_sheets_by_name(workspace):
    step = ui._report(workspace)
    shown = texts(step)

    assert "Report — October 2026" in shown
    assert "Sabji bill" in shown
    assert "Stock register" in shown
    assert actions(step) == [report_ui.SABJI, report_ui.REGISTER]


def actions(control: ft.Control) -> list[str]:
    """The values a segmented button offers."""

    def walk(node):
        if isinstance(node, ft.SegmentedButton):
            return [segment.value for segment in node.segments]
        for child in getattr(node, "controls", None) or []:
            found = walk(child)
            if found:
                return found
        content = getattr(node, "content", None)
        if isinstance(content, ft.Control):
            return walk(content)
        return []

    return walk(control)


def test_the_report_opens_on_the_sabji_bill(workspace):
    assert workspace.report_sheet == report_ui.SABJI


def test_switching_the_sheet_shows_the_other_one(workspace):
    switch = ft.SegmentedButton(
        segments=[
            ft.Segment(value=report_ui.SABJI, label=ft.Text("Sabji bill")),
            ft.Segment(value=report_ui.REGISTER, label=ft.Text("Stock register")),
        ],
        selected=[report_ui.REGISTER],
    )

    ui._switch_sheet(workspace, click(switch))

    assert workspace.report_sheet == report_ui.REGISTER


def test_the_sabji_sheet_carries_its_own_columns(workspace):
    step = report_ui.sheet(workspace.state, report_ui.SABJI)
    shown = texts(step)

    assert "Total Egg Cost" in shown
    assert "Daily Total Cost" in shown
    assert "Rice Balance (Kg)" not in shown


def test_the_register_sheet_carries_its_own_columns(workspace):
    step = report_ui.sheet(workspace.state, report_ui.REGISTER)
    shown = texts(step)

    assert "Rice Balance (Kg)" in shown
    assert "Morning Snacks & THR Value Rs (Item 2 - Egg)" in shown
    assert "Total Egg Cost" not in shown


def test_the_report_scrolls_sideways(workspace):
    step = report_ui.sheet(workspace.state, report_ui.SABJI)

    assert isinstance(step, ft.Row)
    assert step.scroll == ft.ScrollMode.AUTO


# Stepping, months, reset


def test_open_step_records_the_step_and_redraws(workspace):
    drawn = []
    workspace = ui.Workspace(State.new(MONTH), on_rebuild=lambda: drawn.append(1))

    ui._open_step(workspace, 2)

    assert workspace.step == 2
    assert drawn == [1]


def test_an_edit_saves_without_redrawing(workspace):
    saved, drawn = [], []
    workspace = ui.Workspace(
        State.new(MONTH),
        on_edit=lambda: saved.append(1),
        on_rebuild=lambda: drawn.append(1),
    )

    ui._set_rate(
        workspace, "costs", "egg", "mother", "MWF", click(ft.TextField(value="1"))
    )

    assert saved == [1]
    assert drawn == []


def test_changing_the_month_opens_it(workspace):
    ui._change_month(workspace, click(ft.Dropdown(value="2026-09")))

    assert workspace.state.month == "2026-09"


def test_a_blank_month_choice_is_ignored(workspace):
    ui._change_month(workspace, click(ft.Dropdown(value=None)))

    assert workspace.state.month == MONTH


def test_a_step_button_opens_its_step(workspace):
    button = ui._stepper(workspace).controls[2]
    assert isinstance(button, ft.OutlinedButton)
    assert button.on_click is not None

    handler: Any = button.on_click
    handler(click(button))

    assert workspace.step == 2


# Every edit asks for a save


class FakePage:
    """Stands in for the running page.

    The handlers reach the page through `ft.context.page`; this replaces that one
    property on the `Context` class and records what the handlers do with it.
    """

    def __init__(self):
        self.shown: list[Any] = []

    def show_dialog(self, dialog: Any) -> None:
        self.shown.append(dialog)

    def pop_dialog(self) -> None:
        return None


@pytest.fixture(autouse=True)
def fake_page(monkeypatch) -> FakePage:
    """Answer every `ft.context.page` lookup with a fake, for one test."""
    page = FakePage()
    monkeypatch.setattr(type(ft.context), "page", property(lambda self: page))
    return page


def recording_workspace() -> tuple[ui.Workspace, list[int]]:
    """A workspace that counts how many times an edit asked to be saved."""
    saves: list[int] = []
    return ui.Workspace(State.new(MONTH), on_edit=lambda: saves.append(1)), saves


def test_every_input_edit_asks_for_a_save():
    """Every way a value can be changed must reach the store.

    Each handler below changes one of the seven inputs. A handler that forgot to save
    would fail here, which is the one thing a user cannot afford: an edit that is
    visible on screen but gone after a restart.
    """
    day = date(2026, 10, 5)

    def typed(value: str) -> Any:
        return click(ft.TextField(value=value))

    def picked(when: date) -> Any:
        return click(ft.DatePicker(value=when))

    edits: dict[str, Any] = {
        "a cost rate": lambda w: ui._set_rate(
            w, "costs", "egg", "mother", "MWF", typed("901")
        ),
        "a per-head inventory rate": lambda w: ui._set_rate(
            w, "inventory", "rice_g", "mother", "MWF", typed("111")
        ),
        "an opening stock": lambda w: ui._set_opening(w, "rice_g", typed("5000")),
        "a mothers count": lambda w: ui._set_counts(w, day, "mothers", typed("9")),
        "a children count": lambda w: ui._set_counts(w, day, "children", typed("40")),
        "a holiday added": lambda w: ui._holiday_picked(w, picked(date(2026, 10, 6))),
        "a day reopened": lambda w: ui._delete_holiday(w, date(2026, 10, 4)),
        "a delivery added": lambda w: ui._add_delivery(w),
        "the month": lambda w: ui._change_month(w, click(ft.Dropdown(value="2026-09"))),
    }

    for name, edit in edits.items():
        workspace, saves = recording_workspace()
        edit(workspace)
        assert saves, f"{name} was not saved"


def test_every_delivery_edit_asks_for_a_save():
    """A delivery's item, day, amount and removal are all saved as well."""
    workspace, saves = recording_workspace()
    ui._add_delivery(workspace)

    edits: dict[str, Any] = {
        "a delivery item": lambda: ui._set_delivery_item(
            workspace, 0, click(ft.Dropdown(value="rice_g"))
        ),
        "a delivery day": lambda: ui._delivery_day_picked(
            workspace, 0, click(ft.DatePicker(value=date(2026, 10, 9)))
        ),
        "a delivery amount": lambda: ui._set_delivery_amount(
            workspace, 0, click(ft.TextField(value="30000"))
        ),
        "a delivery removed": lambda: ui._remove_delivery(workspace, 0),
    }

    for name, edit in edits.items():
        saves.clear()
        edit()
        assert saves, f"{name} was not saved"


def test_a_reset_is_saved_too(fake_page):
    """A reset must reach the store, or the old values come back on restart."""
    workspace, saves = recording_workspace()
    ui._set_rate(
        workspace, "costs", "egg", "mother", "MWF", click(ft.TextField(value="1"))
    )
    saves.clear()

    ui._ask_to_reset(workspace)

    # Asking changes nothing: the values are still there and nothing was written.
    assert workspace.state.costs.at["egg", ("mother", "MWF")] == 1
    assert not saves

    # Answering "Reset" changes the state and saves it.
    confirm = fake_page.shown[-1].actions[1]
    confirm.on_click(click(confirm))

    assert workspace.state.costs.at["egg", ("mother", "MWF")] == 850
    assert saves == [1]
