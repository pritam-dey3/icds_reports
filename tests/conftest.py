"""Shared test setup.

Every test gets its own in-memory key-value store, so a test can never read or write
the real worksheet, and the order the tests run in does not matter.
"""

import flet as ft
import pytest
from flet.controls.services.shared_preferences import SharedPreferencesValueType


class FakePrefs(ft.SharedPreferences):
    """The platform's key-value store, kept in a dictionary instead."""

    def __init__(self) -> None:
        super().__init__()
        self.values: dict[str, SharedPreferencesValueType] = {}

    async def get(self, key: str) -> SharedPreferencesValueType | None:
        return self.values.get(key)

    async def set(self, key: str, value: SharedPreferencesValueType) -> bool:
        self.values[key] = value
        return True

    async def remove(self, key: str) -> bool:
        return self.values.pop(key, None) is not None


@pytest.fixture(autouse=True)
def isolated_assets(monkeypatch):
    """A packaged app sets this; a test must never inherit it from a running build."""
    monkeypatch.delenv("FLET_ASSETS_DIR", raising=False)


@pytest.fixture
def prefs() -> FakePrefs:
    """A fresh store, for the length of one test."""
    return FakePrefs()
