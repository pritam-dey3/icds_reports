"""The app's inputs as data: the shipped defaults, item labels, months, attendance.

The three bundled sheets in `assets/defaults` are the starting values for the cost
table, the per-head inventory table and the opening stock. They are read once into
the shapes `calculation` expects, so a user edit never touches the files.

A per-head sheet is turned into the shape the calculation works with: one row per
item, and one column per `(head, day type)` pair.
"""

import os
from collections.abc import Iterator
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

from calculation import CHILDREN, LEDGER_COLUMNS, MOTHER, MWF, TTS

# The counts a working day starts at, before anyone edits it.
DEFAULT_MOTHERS = 4
DEFAULT_CHILDREN = 28

# The items each defaults sheet lists, in the order the sheets list them. One snack
# item serves both day types: its Mon/Wed/Fri rate on those days, its Tue/Thu/Sat
# rate on the others.
COST_ITEMS = ("egg", "vegetables", "potato", "morning_snack")
STOCK_ITEMS = tuple(LEDGER_COLUMNS)

# The per-head sheet's column headings, and the pair each one stands for.
PER_HEAD_COLUMNS = {
    "Mother MWF": (MOTHER, MWF),
    "Mother TTS": (MOTHER, TTS),
    "Children MWF": (CHILDREN, MWF),
    "Children TTS": (CHILDREN, TTS),
}

# The four rate fields the editors show, in screen order: the pair a field edits and
# the short heading above it. Derived from `PER_HEAD_COLUMNS`, so the headings and
# the fields they label can never fall out of step.
HEAD_INITIALS = {MOTHER: "M", CHILDREN: "C"}
RATE_COLUMNS = tuple(
    (head, day_type, f"{HEAD_INITIALS[head]} {day_type}")
    for head, day_type in PER_HEAD_COLUMNS.values()
)

# How each item is titled in the editor. The keys are the ones the defaults sheets use.
# The labels stay short so a row of four rate fields still fits a phone.
ITEM_LABELS = {
    "egg": "Egg",
    "vegetables": "Vegetables",
    "potato": "Potato",
    "morning_snack": "Morning snack",
    "rice_g": "Rice",
    "masoor_dal_g": "Masoor dal",
    "mustard_oil_ml": "Mustard oil",
    "iodised_salt_g": "Iodised salt",
}

# The unit an item's quantities are counted in.
ITEM_UNITS = {
    "rice_g": "g",
    "masoor_dal_g": "g",
    "mustard_oil_ml": "ml",
    "iodised_salt_g": "g",
}

# How many months the picker offers, newest first.
MONTHS_OFFERED = 12


def assets_dir() -> Path:
    """The directory the app's bundled files live in.

    A packaged build sets `FLET_ASSETS_DIR`; a plain `flet run` serves `assets/`
    next to `main.py`, which is where these defaults sit.
    """
    packaged = os.environ.get("FLET_ASSETS_DIR")
    return Path(packaged) if packaged else Path(__file__).parent / "assets"


def cost_defaults() -> pd.DataFrame:
    """The per-head cost table in paisa, indexed by item."""
    return per_head_sheet("per_head_costs_paisa.csv")


def inventory_defaults() -> pd.DataFrame:
    """The per-head quantity table, indexed by item, in the item's own unit."""
    return per_head_sheet("per_head_inventory.csv")


def opening_defaults() -> pd.DataFrame:
    """The opening stock, one column named `opening`, indexed by commodity.

    The sheet's own heading is kept flexible — the value is whichever column follows
    the commodity names — so a sheet written by an office still reads.
    """
    sheet = pd.read_csv(assets_dir() / "defaults" / "initial_inventory.csv")
    sheet = sheet.set_index(sheet.columns[0])
    values = pd.to_numeric(sheet.iloc[:, 0], errors="coerce")
    return pd.DataFrame({"opening": values})


def per_head_sheet(name: str) -> pd.DataFrame:
    """Read a per-head sheet into `(head, day type)` columns, dropping its total row.

    A per-head sheet is written either with one flat heading per column
    (`Mother MWF`) or with the two heading rows the paper uses (`head` over
    `day_type`); both are accepted. The sheets carry a `total` row so they read like
    the paper ones; it is derived from the other rows and would be counted twice, so
    it is dropped here.

    Raises:
        ValueError: If the sheet has no `item` column of its own.
    """
    path = assets_dir() / "defaults" / name
    headings = pd.read_csv(path, nrows=0).columns.tolist()
    if "item" in headings:
        return _flat_heading_sheet(path)
    if "head" in headings:
        return _two_heading_sheet(path)
    raise ValueError(f"{name} must start with an item column")


def _two_heading_sheet(path: Path) -> pd.DataFrame:
    """A sheet whose first two rows name the head and the day type."""
    raw = pd.read_csv(path, header=[0, 1])
    names = raw.iloc[:, 0]
    frame = raw.iloc[:, 1:].copy()
    frame.index = pd.Index(names.astype(str).str.strip(), name="item")
    frame = frame.loc[~frame.index.isin(["item", "total"])]
    frame.columns = pd.MultiIndex.from_tuples([
        _pair(f"{head} {day_type}") for head, day_type in frame.columns
    ])
    return _numbers(frame)


def _flat_heading_sheet(path: Path) -> pd.DataFrame:
    """A sheet with one heading per column, such as `Mother MWF`."""
    sheet = pd.read_csv(path)
    sheet = sheet[sheet["item"] != "total"].set_index("item")
    sheet.columns = pd.MultiIndex.from_tuples([
        _pair(heading) for heading in sheet.columns
    ])
    return _numbers(sheet)


def _pair(heading: str) -> tuple[str, str]:
    """The `(head, day type)` pair a column heading stands for."""
    label = heading.strip().lower()
    head = CHILDREN if "child" in label else MOTHER
    day_type = MWF if "mwf" in label else TTS
    return (head, day_type)


def _numbers(frame: pd.DataFrame) -> pd.DataFrame:
    """Read every rate as a number, treating a blank cell as a rate of 0."""
    frame = frame.apply(lambda column: pd.to_numeric(column, errors="coerce"))
    return frame.fillna(0)


def days_in(key: str) -> Iterator[date]:
    """Every day of the month `key` names, in order."""
    start = month_start(key)
    end = (
        date(start.year + 1, 1, 1)
        if start.month == 12
        else date(start.year, start.month + 1, 1)
    )
    day = start
    while day < end:
        yield day
        day += timedelta(days=1)


def month_start(key: str) -> date:
    """The first day of the month `key` names, `YYYY-MM`."""
    year, month = key.split("-")
    return date(int(year), int(month), 1)


def month_key(day: date) -> str:
    """The `YYYY-MM` key of the month `day` falls in."""
    return f"{day.year:04d}-{day.month:02d}"


def month_label(key: str) -> str:
    """The month written out, as the report heading writes it."""
    return month_start(key).strftime("%B %Y")


def months_offered(today: date | None = None) -> list[str]:
    """The month keys the picker offers, newest first."""
    cursor = month_start(month_key(today or date.today()))
    keys: list[str] = []
    for _ in range(MONTHS_OFFERED):
        keys.append(month_key(cursor))
        cursor = (cursor - timedelta(days=1)).replace(day=1)
    return keys


def sundays(key: str) -> list[date]:
    """Every Sunday of the month, the days a centre starts the month closed on."""
    return [day for day in days_in(key) if day.weekday() == 6]


def attendance_sheet(key: str) -> pd.DataFrame:
    """A fresh month's attendance: Sundays blank, every other day at the defaults.

    The frame is indexed by date and complete, which is the shape the calculation
    reads: a blank count means the day is closed.
    """
    days = list(days_in(key))
    closed = set(sundays(key))
    counts = [
        (float("nan"), float("nan"))
        if day in closed
        else (float(DEFAULT_MOTHERS), float(DEFAULT_CHILDREN))
        for day in days
    ]
    return pd.DataFrame(
        counts,
        index=pd.DatetimeIndex(days, name="date"),
        columns=["mothers", "children"],
    )
