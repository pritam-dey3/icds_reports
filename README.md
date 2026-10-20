# ICDS Reports

A four-step worksheet app for an ICDS (anganwadi) centre, built with Flet and aimed
at Android first. It turns a month of head counts, per-head rates and stock figures
into the two sheets the office submits: the **sabji bill** and the **stock register**.

The behaviour it reproduces is written out in
[`docs/streamlit_product.md`](docs/streamlit_product.md), which describes the original
Streamlit app. This repository is the Flet rebuild of that product.

---

## Running it

```bash
uv run flet run            # desktop window
uv run flet run --web      # browser
uv run flet run --android  # Android device or emulator
```

On Android the app is built and packaged with Flet:

```bash
uv run flet build apk
```

---

## What it produces

Both reports are one row per day of the chosen month, followed by a closing `Total`
row. Every figure is derived from the inputs; nothing is typed into a report directly.

| Sheet | What it answers |
|---|---|
| **Sabji bill** | What did the day's food cost, and how many heads were served? |
| **Stock register** | What came in, what was issued, what is left of each commodity — plus the same money figures |

---

## The four steps

| Step | What you edit |
|---|---|
| 1 — Costings | Cost per head per day, in paisa, and the quantity each head is given |
| 2 — Attendance | The holidays, then each day's mother and children counts |
| 3 — Inventory | Each commodity's opening stock, and the stock delivered during the month |
| 4 — Report | The two sheets, switched with one control |

The month sits above every step and applies to all of them.

---

## Rules worth knowing

| Situation | Behaviour |
|---|---|
| A rate of `0` | that column is written **blank**, never `0`: blank means "not served" |
| Sunday or a holiday | every column except `Date` is blank, and the stock ledger does not move |
| Deleting a holiday | the day reopens with the counts it had before it closed |
| Ration exceeds stock | only what is left is issued, and the balance settles at `0` |
| Delivery mid-month | in stock from its own day on, never before |
| Switching month | attendance carries over by day of month; holidays stay per month |
| Something changed above | the report recomputes on the next visit — there is no "generate" button |

---

## Where the figures come from

| Module | Responsibility |
|---|---|
| `src/calculation.py` | The two reports, column by column: day types, per-head arithmetic, the stock ledger, money conversion, the closing `Total` row. |
| `src/data.py` | The shipped defaults, item names and units, the months the picker offers, the calendar, the fresh attendance sheet. |
| `src/state.py` | Everything the user can edit, one month at a time: the shared rate tables and each month's attendance, holidays and deliveries. |
| `src/store.py` | Saving that state, and the screen it was left on, to shared preferences. |
| `src/reports.py` | The closing `Total` row, and every cell as the text the sheet shows. |
| `src/ui.py` | The four steps, the month picker, and the edits. |
| `src/report_ui.py` | The two sheets as read-only tables. |
| `src/main.py` | The entry point: load, draw, save. |

The first four are plain pandas and have no Flet import, so the report rules can be
tested without starting an app.

### Defaults

`src/assets/defaults/` holds the starting values, and every one of them is editable in
the app:

| File | Holds |
|---|---|
| `per_head_costs_paisa.csv` | paisa per head per serving day |
| `per_head_inventory.csv` | grams or millilitres per head per serving day |
| `initial_inventory.csv` | the stock each commodity's ledger starts from |

A per-head sheet may be written with one heading per column (`Mother MWF`) or with the
two heading rows the paper uses; both read the same way. The derived `total` row the
paper carries is dropped on read so it is never counted twice.

---

## Saving

Every edit is written to `ft.SharedPreferences`, the durable store on each platform: the
browser's local storage on the web, and the platform's preference store (UserDefaults,
DataStore, the registry) on desktop and mobile. The whole worksheet — the shared rate
tables, every month's attendance, holidays and deliveries, and the step and report sheet
the user left open — goes under one key, so a write lands whole or not at all, and a
reload brings back every input.

- **Reset data** in the app bar's overflow menu clears every edit, after asking.
- Opening the app with `?reset=1` also starts over, which is how a web user clears storage.
- There is no second copy on disk, and no environment variable: the store is the only
  place the worksheet lives, so the app behaves the same in a browser and on a device.

---

## Tests

```bash
uv run pytest
uvx pyrefly check
```

| File | Covers |
|---|---|
| `tests/test_calculation.py` | Both reports against a two-day month whose figures were worked out by hand, plus the closing `Total` row and the delivery rules |
| `tests/test_data.py` | The bundled sheets, the months offered, the calendar, the attendance sheet |
| `tests/test_state.py` | Holidays masking a day, carrying over by day of month, deliveries, reset, save/restore |
| `tests/test_store.py` | Round trips, the saved screen, and what an unreadable payload does |
| `tests/test_reports.py` | The `Total` row, two-decimal money, blanks as empty text |
| `tests/test_ui.py` | What each step is built from, and what every edit does |
| `tests/test_main.py` | The running app, driven through Flet's test harness |

The last file needs a Flutter test host, which is provisioned on first run. Where that
is not available it skips itself instead of failing.
