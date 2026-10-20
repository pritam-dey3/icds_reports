"""The saved worksheet: where it lives, what survives, and what a bad file does."""

import json
from datetime import date

import pytest

import reports
import store
from state import State


def saved_file(directory):
    return directory / store.FILE_NAME


def test_the_state_file_lives_in_the_app_data_directory(tmp_path):
    assert store.file_path(tmp_path) == tmp_path / store.FILE_NAME


def test_the_override_directory_wins_over_the_app_storage_directory(
    monkeypatch, tmp_path
):
    monkeypatch.setenv("ICDS_DATA_DIR", str(tmp_path / "override"))
    monkeypatch.setenv("FLET_APP_STORAGE_DATA", str(tmp_path / "app"))

    assert store.data_dir() == tmp_path / "override"


def test_the_app_storage_directory_is_used_when_no_override_is_set(
    monkeypatch, tmp_path
):
    """The data directory is the durable one; the cache can be emptied by the OS."""
    monkeypatch.delenv("ICDS_DATA_DIR", raising=False)
    monkeypatch.setenv("FLET_APP_STORAGE_DATA", str(tmp_path / "app"))

    assert store.data_dir() == tmp_path / "app"


def test_with_no_directory_at_all_the_app_still_opens(monkeypatch, tmp_path):
    """In a browser there is no disk: the app runs, it just cannot save."""
    monkeypatch.delenv("ICDS_DATA_DIR", raising=False)
    monkeypatch.delenv("FLET_APP_STORAGE_DATA", raising=False)
    monkeypatch.chdir(tmp_path)

    assert store.data_dir() is None
    assert store.save(State.new("2026-10")) is False
    assert store.load().month  # the shipped defaults, not a crash


def test_saving_then_loading_gives_back_the_same_sheet(tmp_path):
    state = State.new("2026-10")
    state.costs.loc["egg", ("mother", "MWF")] = 900
    state.add_delivery("rice_g", __import__("datetime").date(2026, 10, 17), 30000)

    assert store.save(state, tmp_path) is True
    restored = store.load(tmp_path)

    assert restored.costs.at["egg", ("mother", "MWF")] == 900
    assert restored.additions() == state.additions()


def test_every_input_survives_a_round_trip_through_the_file(tmp_path):
    """The whole worksheet is written to disk and read back, input by input."""
    state = State.new("2026-10")
    state.costs.loc["egg", ("mother", "MWF")] = 901
    state.inventory.loc["rice_g", ("children", "TTS")] = 76
    state.opening.loc["rice_g", "opening"] = 11_111
    state.set_attendance(date(2026, 10, 5), 13, 51)
    state.add_holiday(date(2026, 10, 6))
    state.remove_holiday(date(2026, 10, 4))
    state.add_delivery("mustard_oil_ml", date(2026, 10, 9), 500)

    store.save(state, tmp_path)
    restored = store.load(tmp_path)

    assert restored.month == "2026-10"
    assert restored.costs.at["egg", ("mother", "MWF")] == 901
    assert restored.inventory.at["rice_g", ("children", "TTS")] == 76
    assert restored.opening.at["rice_g", "opening"] == 11_111
    assert restored.counts(date(2026, 10, 5)) == (13, 51)
    assert restored.is_holiday(date(2026, 10, 6))
    assert not restored.is_holiday(date(2026, 10, 4))
    assert restored.additions() == [
        {"item": "mustard_oil_ml", "date": "2026-10-09", "amount": 500.0}
    ]
    # And the report agrees, so the restored figures really are the ones used.
    # The 5th is a Mon/Wed/Fri day, where the edited mother rate applies:
    # 13 mothers x 901 + 51 children x 850 = 55063 paisa.
    bill = reports.sabji_bill(restored)
    fifth = bill[bill["Date"] == 5].iloc[0]
    assert fifth["Total Egg Cost"] == pytest.approx(550.63)


def test_saving_writes_a_readable_json_file(tmp_path):
    store.save(State.new("2026-10"), tmp_path)

    payload = json.loads(saved_file(tmp_path).read_text(encoding="utf-8"))

    assert payload["month"] == "2026-10"
    assert "costs" in payload and "months" in payload
    # No pickles: the file is data a person can read.
    assert saved_file(tmp_path).suffix == ".json"


def test_saving_leaves_no_temporary_file_behind(tmp_path):
    store.save(State.new("2026-10"), tmp_path)

    leftovers = [path.name for path in tmp_path.iterdir() if path.name.endswith(".tmp")]
    assert leftovers == []
    assert saved_file(tmp_path).exists()


def test_a_missing_file_loads_the_shipped_defaults(tmp_path):
    restored = store.load(tmp_path)

    assert restored.costs.at["egg", ("mother", "MWF")] == 850
    assert restored.additions() == []


@pytest.mark.parametrize(
    "content",
    [
        "not json at all",
        "{}",
        '{"month": "2026-10"}',
        '{"month": "2026-10", "months": []}',
    ],
)
def test_a_file_that_cannot_be_read_falls_back_to_the_defaults(tmp_path, content):
    saved_file(tmp_path).write_text(content, encoding="utf-8")

    restored = store.load(tmp_path)

    assert restored.costs.at["egg", ("mother", "MWF")] == 850


def test_a_reset_deletes_the_file_and_returns_the_defaults(tmp_path):
    state = State.new("2026-10")
    state.costs.loc["egg", ("mother", "MWF")] = 900
    store.save(state, tmp_path)

    fresh = store.reset(tmp_path)

    assert not saved_file(tmp_path).exists()
    assert fresh.costs.at["egg", ("mother", "MWF")] == 850


def test_a_reset_with_no_file_still_returns_the_defaults(tmp_path):
    assert store.reset(tmp_path).costs.at["egg", ("mother", "MWF")] == 850
