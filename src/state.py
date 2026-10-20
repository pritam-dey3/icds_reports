"""Everything the user can change, one month at a time.

The three per-head tables are shared by every month. What belongs to a single month
is its attendance, its holidays and the stock delivered during it, so those live in
`months`, keyed by `YYYY-MM`.

Two conventions are worth knowing:

* Attendance is stored per day of the month, not per date, so a new month can be
  laid out from the month before by day of month.
* A holiday is a mask, not a value. The day keeps the counts it had before it was
  closed, so reopening it brings them back instead of resetting them.
"""

from datetime import date

import pandas as pd

import data
from data import DEFAULT_CHILDREN, DEFAULT_MOTHERS


class State:
    """The whole worksheet: the shared tables, the open month, and every month's inputs."""

    def __init__(
        self,
        month: str,
        costs: pd.DataFrame,
        inventory: pd.DataFrame,
        opening: pd.DataFrame,
        months: dict[str, dict] | None = None,
    ):
        self.month = month
        self.costs = costs
        self.inventory = inventory
        self.opening = opening
        self.months: dict[str, dict] = months or {}
        self.inputs()

    @classmethod
    def new(cls, month: str | None = None) -> "State":
        """A worksheet with nothing edited: the shipped defaults, and Sundays closed."""
        return cls(
            month=month or data.month_key(date.today()),
            costs=data.cost_defaults(),
            inventory=data.inventory_defaults(),
            opening=data.opening_defaults(),
        )

    # The open month

    def select_month(self, key: str) -> None:
        """Open another month, building it from defaults if this is its first visit."""
        self.month = key
        self.inputs()

    def inputs(self, month: str | None = None) -> dict:
        """The open month's editable inputs, built on first use."""
        key = month or self.month
        if key not in self.months:
            self.months[key] = {
                "attendance": self._carried_attendance(key),
                "holidays": [day.isoformat() for day in data.sundays(key)],
                "additions": [],
            }
        return self.months[key]

    def _carried_attendance(self, key: str) -> dict[str, list[int]]:
        """A new month's counts: the newest month's counts, by day of month.

        A day of the month the newest month does not have falls back to the counts a
        working day starts at.
        """
        source = max(self.months, default=None)
        counts = self.months[source]["attendance"] if source else {}
        sheet: dict[str, list[int]] = {}
        for day in data.days_in(key):
            carried = counts.get(str(day.day))
            sheet[str(day.day)] = (
                list(carried) if carried else [DEFAULT_MOTHERS, DEFAULT_CHILDREN]
            )
        return sheet

    # Attendance

    def attendance_frame(self, month: str | None = None) -> pd.DataFrame:
        """The month as the calculation reads it: date-indexed, a blank count on a
        closed day."""
        key = month or self.month
        inputs = self.inputs(key)
        closed = set(inputs["holidays"])
        days = list(data.days_in(key))
        rows = []
        for day in days:
            if day.isoformat() in closed:
                rows.append((float("nan"), float("nan")))
                continue
            mothers, children = self.counts(day)
            rows.append((float(mothers), float(children)))
        return pd.DataFrame(
            rows,
            index=pd.DatetimeIndex(days, name="date"),
            columns=["mothers", "children"],
        )

    def counts(self, day: date) -> tuple[int, int]:
        """The counts a day holds, and would show again if it reopened."""
        stored = self.inputs(data.month_key(day))["attendance"].get(str(day.day))
        return (stored[0], stored[1]) if stored else (DEFAULT_MOTHERS, DEFAULT_CHILDREN)

    def set_attendance(
        self, day: date, mothers: int | None, children: int | None
    ) -> None:
        """Record a day's counts. A closed day takes no counts, so edits to one drop."""
        inputs = self.inputs(data.month_key(day))
        if day.isoformat() in inputs["holidays"]:
            return
        inputs["attendance"][str(day.day)] = [
            DEFAULT_MOTHERS if mothers is None else max(0, mothers),
            DEFAULT_CHILDREN if children is None else max(0, children),
        ]

    # Holidays

    def holidays(self, month: str | None = None) -> list[date]:
        """The closed days of the month, in date order."""
        return [date.fromisoformat(stamp) for stamp in self.inputs(month)["holidays"]]

    def is_holiday(self, day: date) -> bool:
        """Whether the day is closed."""
        return day.isoformat() in self.inputs(data.month_key(day))["holidays"]

    def add_holiday(self, day: date) -> None:
        """Close a day. A date outside the open month is ignored."""
        if data.month_key(day) != self.month:
            return
        holidays = self.inputs()["holidays"]
        stamp = day.isoformat()
        if stamp not in holidays:
            holidays.append(stamp)
            holidays.sort()

    def remove_holiday(self, day: date) -> None:
        """Reopen a day, bringing back the counts it had before it closed."""
        holidays = self.inputs(data.month_key(day))["holidays"]
        stamp = day.isoformat()
        if stamp in holidays:
            holidays.remove(stamp)

    # Added inventory

    def deliveries(self, month: str | None = None) -> pd.DataFrame | None:
        """The month's deliveries in the shape the register reads, or `None` if none."""
        rows = self.inputs(month)["additions"]
        if not rows:
            return None
        return pd.DataFrame({
            "date": pd.to_datetime([row["date"] for row in rows]),
            "item": [row["item"] for row in rows],
            "amount": [float(row["amount"]) for row in rows],
        })

    def additions(self, month: str | None = None) -> list[dict]:
        """The month's delivery rows as they are stored."""
        return self.inputs(month)["additions"]

    def add_delivery(self, item: str, day: date, amount: float) -> None:
        """Record a delivery, clamped into the open month."""
        days = list(data.days_in(self.month))
        clamped = min(max(day, days[0]), days[-1])
        self.inputs()["additions"].append({
            "item": item,
            "date": clamped.isoformat(),
            "amount": max(0.0, amount),
        })

    def set_delivery(
        self,
        index: int,
        item: str | None = None,
        day: date | None = None,
        amount: float | None = None,
    ) -> None:
        """Edit one delivery in place."""
        row = self.inputs()["additions"][index]
        if item is not None:
            row["item"] = item
        if day is not None:
            days = list(data.days_in(self.month))
            row["date"] = min(max(day, days[0]), days[-1]).isoformat()
        if amount is not None:
            row["amount"] = max(0.0, amount)

    def remove_delivery(self, index: int) -> None:
        """Drop one delivery."""
        self.inputs()["additions"].pop(index)

    # Persistence helpers

    def reset(self) -> None:
        """Throw every edit away and go back to the shipped defaults."""
        defaults = State.new(self.month)
        self.costs = defaults.costs
        self.inventory = defaults.inventory
        self.opening = defaults.opening
        self.months = {}
        self.inputs()

    def to_dict(self) -> dict:
        """The whole state as plain JSON-ready data."""
        return {
            "month": self.month,
            "costs": _per_head_payload(self.costs),
            "inventory": _per_head_payload(self.inventory),
            "opening": {
                "commodities": list(self.opening.index),
                "values": self.opening.iloc[:, 0].tolist(),
            },
            "months": self.months,
        }

    @classmethod
    def from_dict(cls, payload: dict) -> "State":
        """Rebuild a state saved by `to_dict`.

        Raises:
            ValueError: If the payload does not carry the tables the reports need.
        """
        months = payload["months"]
        if not isinstance(months, dict):
            raise ValueError("months must be a mapping")
        return cls(
            month=payload["month"],
            costs=_per_head_frame(payload["costs"]),
            inventory=_per_head_frame(payload["inventory"]),
            opening=_opening_frame(payload["opening"]),
            months=months,
        )


def _per_head_payload(frame: pd.DataFrame) -> dict:
    """A per-head table as items, its column pairs, and a grid of rates."""
    return {
        "items": list(frame.index),
        "columns": [[head, day_type] for head, day_type in frame.columns],
        "values": frame.to_numpy().tolist(),
    }


def _per_head_frame(payload: dict) -> pd.DataFrame:
    """Rebuild a per-head table, or raise if the grid does not match its headings."""
    columns = pd.MultiIndex.from_tuples([tuple(pair) for pair in payload["columns"]])
    values = payload["values"]
    if len(values) != len(payload["items"]):
        raise ValueError("per-head table has a row count mismatch")
    if any(len(row) != len(columns) for row in values):
        raise ValueError("per-head table has a column count mismatch")
    return pd.DataFrame(
        values, index=pd.Index(payload["items"], name="item"), columns=columns
    )


def _opening_frame(payload: dict) -> pd.DataFrame:
    """Rebuild the opening stock the calculation starts each ledger from."""
    if len(payload["commodities"]) != len(payload["values"]):
        raise ValueError("opening stock has a count mismatch")
    return pd.DataFrame(
        {"opening": payload["values"]},
        index=pd.Index(payload["commodities"], name="commodity"),
    )
