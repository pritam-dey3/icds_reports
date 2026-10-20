"""ICDS reports — the four-step worksheet app.

One entry point for every platform. The app reads the saved worksheet from shared
preferences (or the shipped defaults on a first run), draws the step and sheet it was
left on, and saves after every edit, so a phone that is put down mid-entry loses
nothing.
"""

import asyncio
import urllib.parse

import flet as ft

import report_ui
import store
import theme
import ui


async def main(page: ft.Page) -> None:
    page.title = "ICDS Reports"
    page.theme_mode = ft.ThemeMode.LIGHT
    page.padding = 0
    page.bgcolor = theme.CANVAS
    page.theme = app_theme()
    root = page.views[0]
    root.padding = 0
    # The screen fits the window; the cards scroll inside it and the footer stays put.
    root.scroll = None
    root.horizontal_alignment = ft.CrossAxisAlignment.STRETCH

    picker = ft.FilePicker()
    page.services.append(picker)
    prefs = ft.SharedPreferences()
    saved = await (store.reset(prefs) if reset_requested(page) else store.load(prefs))
    writes = asyncio.Lock()

    async def persist() -> None:
        """Write the whole worksheet and screen, one queued write at a time."""
        record = store.Saved(workspace.state, workspace.step, workspace.report_sheet)
        async with writes:
            landed = await store.save(prefs, record)
        if not landed and not workspace.failure_shown:
            workspace.failure_shown = True
            ui.save_failed(workspace, page)

    def save() -> None:
        """Queue a write, so an edit never waits on the store."""
        page.run_task(persist)

    def render() -> None:
        root.controls = ui.build(workspace)
        page.update()

    workspace = ui.Workspace(saved.state, on_edit=save, on_rebuild=render, files=picker)
    # Where the user left off: the report on a first run, then the step and sheet
    # they closed the app on, as long as this build can draw them.
    step = ui.REPORT_STEP if saved.step is None else saved.step
    workspace.step = min(max(step, 0), len(ui.STEPS) - 1)
    if saved.sheet is not None and saved.sheet in (report_ui.SABJI, report_ui.REGISTER):
        workspace.report_sheet = saved.sheet
    render()


def app_theme() -> ft.Theme:
    """One theme for the whole app: the design's blue, and a neutral reading surface."""
    return ft.Theme(
        use_material3=True,
        color_scheme=ft.ColorScheme(
            primary=theme.PRIMARY_600,
            on_primary=theme.TEXT_INVERSE,
            secondary=theme.PRIMARY_500,
            surface=theme.SURFACE,
            on_surface=theme.TEXT,
            outline=theme.BORDER_STRONG,
            outline_variant=theme.BORDER_SUBTLE,
            error=theme.DANGER,
        ),
        scaffold_bgcolor=theme.CANVAS,
        canvas_color=theme.CANVAS,
        divider_color=theme.BORDER_SUBTLE,
        hint_color=theme.TEXT_TERTIARY,
        font_family="Inter",
    )


def reset_requested(page: ft.Page) -> bool:
    """Whether the page was opened with `?reset=1`, the way a web user starts over.

    The first route carries the browser's query string; `page.query` is only filled
    in once a route change has been dispatched, which is after this first run.
    """
    query = urllib.parse.urlparse(page.route).query
    return dict(urllib.parse.parse_qsl(query)).get("reset") == "1"


if __name__ == "__main__":
    ft.run(main)
