"""Where the worksheet is kept: one entry in the app's key-value store.

`SharedPreferences` is the durable store on every platform: browser storage on the
web, and the platform's preference store (UserDefaults, DataStore, the registry) on
desktop and mobile. The whole worksheet — every rate, every month's inputs, and the
screen the user left it on — goes under one key, so a write lands whole or not at all.
"""

import json
from dataclasses import dataclass

import flet as ft

from state import State

KEY = "icds-reports"


@dataclass
class Saved:
    """The worksheet, and the screen the user left it on."""

    state: State
    step: int | None = None
    sheet: str | None = None


async def load(prefs: ft.SharedPreferences) -> Saved:
    """The saved worksheet and screen, or the shipped defaults on a first run."""
    payload = await prefs.get(KEY)
    if isinstance(payload, str):
        saved = _decode(payload)
        if saved is not None:
            return saved
    return Saved(State.new())


async def save(prefs: ft.SharedPreferences, saved: Saved) -> bool:
    """Write the whole worksheet and screen, one key, one write."""
    payload = {"state": saved.state.to_dict(), "step": saved.step, "sheet": saved.sheet}
    return await prefs.set(KEY, json.dumps(payload))


async def reset(prefs: ft.SharedPreferences) -> Saved:
    """Delete the saved worksheet and return the shipped defaults."""
    await prefs.remove(KEY)
    return Saved(State.new())


def _decode(payload: str) -> Saved | None:
    """The saved worksheet, or `None` for anything this build cannot read.

    A payload that is unreadable or in an older shape is not an error the user can do
    anything about, so it counts as "nothing saved yet".
    """
    try:
        saved = json.loads(payload)
        state = State.from_dict(saved["state"])
        step = saved.get("step")
        sheet = saved.get("sheet")
    except (AttributeError, ValueError, KeyError, TypeError):
        return None
    return Saved(
        state,
        step if isinstance(step, int) else None,
        sheet if isinstance(sheet, str) else None,
    )
