"""The saved worksheet: what survives, and what an unreadable payload does."""

import json
from datetime import date

import pytest

import reports
import store
from state import State


async def test_saving_then_loading_gives_back_the_same_sheet(prefs):
    state = State.new("2026-10")
    state.costs.loc["egg", ("mother", "MWF")] = 900
    state.add_delivery("rice_g", date(2026, 10, 17), 30000)

    assert await store.save(prefs, store.Saved(state)) is True
    restored = await store.load(prefs)

    assert restored.state.costs.at["egg", ("mother", "MWF")] == 900
    assert restored.state.additions() == state.additions()


async def test_every_input_survives_a_round_trip(prefs):
    """The whole worksheet is written to the store and read back, input by input."""
    state = State.new("2026-10")
    state.costs.loc["egg", ("mother", "MWF")] = 901
    state.inventory.loc["rice_g", ("children", "TTS")] = 76
    state.opening.loc["rice_g", "opening"] = 11_111
    state.set_attendance(date(2026, 10, 5), 13, 51)
    state.add_holiday(date(2026, 10, 6))
    state.remove_holiday(date(2026, 10, 4))
    state.add_delivery("mustard_oil_ml", date(2026, 10, 9), 500)

    await store.save(prefs, store.Saved(state))
    restored = (await store.load(prefs)).state

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


async def test_the_screen_the_user_left_is_saved_too(prefs):
    """The step and the report sheet are app state, so they are saved with the sheet."""
    await store.save(
        prefs, store.Saved(State.new("2026-10"), step=2, sheet="stock_register")
    )

    restored = await store.load(prefs)

    assert restored.step == 2
    assert restored.sheet == "stock_register"


async def test_saving_writes_one_readable_json_payload(prefs):
    await store.save(prefs, store.Saved(State.new("2026-10")))

    payload = json.loads(prefs.values[store.KEY])

    assert payload["state"]["month"] == "2026-10"
    assert "costs" in payload["state"] and "months" in payload["state"]
    # No pickles: the entry is data a person can read.
    assert isinstance(payload["state"], dict)


async def test_a_first_run_loads_the_shipped_defaults(prefs):
    restored = await store.load(prefs)

    assert restored.state.costs.at["egg", ("mother", "MWF")] == 850
    assert restored.state.additions() == []
    assert restored.step is None and restored.sheet is None


@pytest.mark.parametrize(
    "content",
    [
        "not json at all",
        "{}",
        "[]",
        '{"state": {}}',
        '{"state": {"month": "2026-10"}}',
        '{"state": {"month": "2026-10", "months": []}}',
    ],
)
async def test_a_payload_that_cannot_be_read_falls_back_to_the_defaults(prefs, content):
    prefs.values[store.KEY] = content

    restored = await store.load(prefs)

    assert restored.state.costs.at["egg", ("mother", "MWF")] == 850
    assert restored.step is None


async def test_a_save_reports_whether_the_store_took_it(prefs, monkeypatch):
    async def refuse(key, value):
        return False

    monkeypatch.setattr(prefs, "set", refuse)

    assert await store.save(prefs, store.Saved(State.new("2026-10"))) is False


async def test_a_reset_deletes_the_entry_and_returns_the_defaults(prefs):
    state = State.new("2026-10")
    state.costs.loc["egg", ("mother", "MWF")] = 900
    await store.save(prefs, store.Saved(state, step=2, sheet="stock_register"))

    fresh = await store.reset(prefs)

    assert store.KEY not in prefs.values
    assert fresh.state.costs.at["egg", ("mother", "MWF")] == 850
    assert fresh.step is None and fresh.sheet is None


async def test_a_reset_with_nothing_saved_still_returns_the_defaults(prefs):
    assert (await store.reset(prefs)).state.costs.at["egg", ("mother", "MWF")] == 850
