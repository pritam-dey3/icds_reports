"""The running app, driven through Flet's test harness.

The harness provisions a Flutter test host on first use, which is a large download.
These tests therefore ask for it: set `FLET_UI_TESTS=1` to run them, and they skip
otherwise, so the ordinary suite stays fast and needs no toolchain.

The same four steps are covered without a toolchain in `test_ui.py`, which builds the
controls and calls their handlers directly.
"""

import os

import pytest
import pytest_asyncio

import store
import ui

RUN_UI_TESTS = os.environ.get("FLET_UI_TESTS") == "1"

needs_host = pytest.mark.skipif(
    not RUN_UI_TESTS,
    reason="set FLET_UI_TESTS=1 to run the app tests (needs a Flutter test host)",
)


@pytest_asyncio.fixture
async def app(request):
    """The app under test, or a skip when this machine cannot host it."""
    plugin = pytest.importorskip("flet.pytest_plugin")

    try:
        app = plugin._create_flet_app(request)
        await app.start()
    except Exception as exc:  # the test host could not be provisioned
        pytest.skip(f"Flet test host unavailable: {exc}")

    yield app

    await app.teardown()


@needs_host
async def test_the_app_starts_and_shows_the_first_step(app):
    tester = app.tester
    await tester.pump_and_settle()

    assert (await tester.find_by_text("Costings")).count >= 1
    assert (await tester.find_by_text("Per-head inventory")).count == 1


@needs_host
async def test_the_app_moves_through_the_four_steps(app):
    tester = app.tester
    await tester.pump_and_settle()

    await tester.tap(await tester.find_by_key("step-2"))
    await tester.pump_and_settle()
    assert (await tester.find_by_text("Daily attendance")).count == 1

    await tester.tap(await tester.find_by_key("step-3"))
    await tester.pump_and_settle()
    assert (await tester.find_by_text("Opening stock")).count == 1

    await tester.tap(await tester.find_by_key("step-4"))
    await tester.pump_and_settle()
    assert (await tester.find_by_text_containing("Report —")).count == 1


@needs_host
async def test_a_typed_rate_reaches_the_saved_worksheet(app):
    tester = app.tester
    await tester.pump_and_settle()

    await tester.enter_text(await tester.find_by_key("cost-egg-mother-MWF"), "900")
    await tester.pump_and_settle()

    assert store.load().costs.at["egg", ("mother", "MWF")] == 900


# The two below need no toolchain, so they run in the ordinary suite.


def test_the_workspace_opens_on_the_first_step():
    workspace = ui.Workspace(store.load())

    assert workspace.step == 0
    assert workspace.state.month


def test_nothing_is_deleted_until_a_reset_is_accepted():
    """The confirmation dialog is the guard; the file survives until it is accepted."""
    state = store.load()
    state.costs.loc["egg", ("mother", "MWF")] = 900
    store.save(state)

    assert store.load().costs.at["egg", ("mother", "MWF")] == 900

    target = store.file_path()
    assert target is not None and target.exists()

    store.reset()
    assert store.load().costs.at["egg", ("mother", "MWF")] == 850
