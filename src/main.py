"""ICDS reports — the four-step worksheet app.

One entry point for every platform. The app reads the saved worksheet (or the
shipped defaults on a first run), draws the four steps, and saves after every edit,
so a phone that is put down mid-entry loses nothing.
"""

import flet as ft

import store
import theme
import ui


def main(page: ft.Page) -> None:
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
    state = store.reset() if reset_requested(page) else store.load()

    def save() -> bool:
        return store.save(workspace.state)

    def render() -> None:
        root.controls = ui.build(workspace)
        page.update()

    workspace = ui.Workspace(state, on_edit=save, on_rebuild=render, files=picker)
    workspace.step = ui.REPORT_STEP
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
    """Whether the page was opened with `?reset=1`, the way a web user starts over."""
    try:
        return page.query.to_dict.get("reset") == "1"
    except (TypeError, ValueError):
        return False


if __name__ == "__main__":
    ft.run(main)
