"""ICDS reports — the four-step worksheet app.

One entry point for every platform. The app reads the saved worksheet (or the
shipped defaults on a first run), draws the four steps, and saves after every edit,
so a phone that is put down mid-entry loses nothing.
"""

import flet as ft

import store
import ui


def main(page: ft.Page) -> None:
    page.title = "ICDS Reports"
    page.theme_mode = ft.ThemeMode.LIGHT
    page.padding = 12
    root = page.views[0]
    root.padding = 0
    # The page scrolls; the content is as tall as it needs to be. The view fills the
    # width either way, so the grids use the whole screen.
    root.scroll = ft.ScrollMode.AUTO
    root.horizontal_alignment = ft.CrossAxisAlignment.STRETCH

    state = store.reset() if reset_requested(page) else store.load()

    def save() -> None:
        store.save(workspace.state)

    def render() -> None:
        root.controls = ui.build(workspace)
        page.update()

    workspace = ui.Workspace(state, on_edit=save, on_rebuild=render)
    root.appbar = ui.app_bar(workspace)
    render()


def reset_requested(page: ft.Page) -> bool:
    """Whether the page was opened with `?reset=1`, the way a web user starts over."""
    try:
        return page.query.to_dict.get("reset") == "1"
    except (TypeError, ValueError):
        return False


if __name__ == "__main__":
    ft.run(main)
