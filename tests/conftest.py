"""Shared test setup.

Every test runs against its own empty data directory, so a test can never read or
write the real worksheet file, and the order the tests run in does not matter.
"""

import pytest


@pytest.fixture(autouse=True)
def isolated_data_dir(tmp_path, monkeypatch):
    """Point the store at a throwaway directory for the length of one test."""
    target = tmp_path / "data"
    target.mkdir()
    monkeypatch.setenv("ICDS_DATA_DIR", str(target))
    # A packaged app sets this; a test must never inherit it from a running build.
    monkeypatch.delenv("FLET_ASSETS_DIR", raising=False)
    yield target
