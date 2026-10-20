"""Where the worksheet is kept: one JSON file in the app's data directory.

The directory is `FLET_APP_STORAGE_DATA` — the app's private, durable storage, which
survives an app update. It is deliberately not the cache directory, which the OS may
empty when the device runs out of room.

`ICDS_DATA_DIR` overrides it, which is how the tests keep the real workspace clean.
Under `flet run` the storage directory is `.flet/storage/data`. In the browser there
is no such directory, so nothing is written and a refresh starts from the defaults.
"""

import json
import os
from pathlib import Path

from state import State

FILE_NAME = "icds-reports.json"


def data_dir() -> Path | None:
    """The directory the state file belongs in, or `None` where there is no disk."""
    override = os.environ.get("ICDS_DATA_DIR")
    if override:
        return Path(override)
    app_storage = os.environ.get("FLET_APP_STORAGE_DATA")
    if app_storage:
        return Path(app_storage)
    fallback = Path.cwd() / ".flet" / "storage" / "data"
    return fallback if fallback.is_dir() else None


def file_path(directory: Path | str | None = None) -> Path | None:
    """The state file's path, or `None` when the app has no writable directory."""
    base = Path(directory) if directory is not None else data_dir()
    return None if base is None else base / FILE_NAME


def load(directory: Path | str | None = None) -> State:
    """Read the saved worksheet, or start from the shipped defaults.

    A file that is missing, unreadable or in an older shape is not an error the user
    can do anything about, so it is treated as "nothing saved yet".
    """
    target = file_path(directory)
    if target is None or not target.exists():
        return State.new()
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
        return State.from_dict(payload)
    except (OSError, ValueError, KeyError, TypeError):
        return State.new()


def save(state: State, directory: Path | str | None = None) -> bool:
    """Write the worksheet, atomically so an interrupted write cannot corrupt it."""
    target = file_path(directory)
    if target is None:
        return False
    target.parent.mkdir(parents=True, exist_ok=True)
    pending = target.with_suffix(".json.tmp")
    pending.write_text(json.dumps(state.to_dict(), indent=2), encoding="utf-8")
    pending.replace(target)
    return True


def reset(directory: Path | str | None = None) -> State:
    """Delete the saved worksheet and return the shipped defaults."""
    target = file_path(directory)
    if target is not None and target.exists():
        target.unlink()
    return State.new()
