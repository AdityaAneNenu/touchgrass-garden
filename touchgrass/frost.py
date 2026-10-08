"""Frost-date lookup and planting-window calculations (pure stdlib, fully offline)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

_DATA_DIR = Path(__file__).parent / "data"


@dataclass(frozen=True)
class FrostDates:
    """Average frost dates for one location, as month/day (no year attached)."""

    city: str
    state: str
    zone: str
    last_frost: tuple[int, int]   # (month, day) - average last spring frost
    first_frost: tuple[int, int]  # (month, day) - average first autumn frost

    def resolve(self, today: date) -> ResolvedFrost:
        """Attach this year's frost dates for planning from `today`.

        - During or before the current growing season (today <= first frost),
          anchor to THIS year's dates even if last frost already passed:
          offsets from a past last-frost remain meaningful ("2 weeks after
          last frost" may simply be *now*).
        - After this year's first frost, we're out of season: plan against
          NEXT year's dates.
        """
        ly, ld = self.last_frost
        fy, fd = self.first_frost
        last_this = date(today.year, ly, ld)
        first_this = date(today.year, fy, fd)

        if first_this <= last_this:
            # Data anomaly (e.g. southern-hemisphere rows): roll a full year.
            year = today.year + 1
            return ResolvedFrost(
                city=self.city, state=self.state, zone=self.zone,
                last_spring_frost=date(year, ly, ld),
                first_fall_frost=date(year, fy, fd),
            )

        if today > first_this:
            year = today.year + 1
            return ResolvedFrost(
                city=self.city, state=self.state, zone=self.zone,
                last_spring_frost=date(year, ly, ld),
                first_fall_frost=date(year, fy, fd),
            )

        return ResolvedFrost(
            city=self.city, state=self.state, zone=self.zone,
            last_spring_frost=last_this, first_fall_frost=first_this,
        )


@dataclass(frozen=True)
class ResolvedFrost:
    city: str
    state: str
    zone: str
    last_spring_frost: date
    first_fall_frost: date

    @property
    def growing_season_days(self) -> int:
        return (self.first_fall_frost - self.last_spring_frost).days


def _parse_mmdd(text: str) -> tuple[int, int]:
    month, day = text.split("-")
    return int(month), int(day)


def load_frost_dates(path: Path | None = None) -> list[FrostDates]:
    with open(path or (_DATA_DIR / "frost_dates.json"), encoding="utf-8") as fh:
        raw = json.load(fh)
    return [
        FrostDates(
            city=entry["city"], state=entry["state"], zone=entry["zone"],
            last_frost=_parse_mmdd(entry["last_frost"]),
            first_frost=_parse_mmdd(entry["first_frost"]),
        )
        for entry in raw["cities"]
    ]


def find_city(query: str, cities: list[FrostDates] | None = None) -> list[FrostDates]:
    """Case-insensitive substring search: 'denver', 'denver co', 'co' all work."""
    cities = cities if cities is not None else load_frost_dates()
    q = query.strip().lower()
    if not q:
        return []
    exact = [c for c in cities if f"{c.city}, {c.state}".lower() == q]
    if exact:
        return exact
    by_state = [c for c in cities if c.state.lower() == q]
    if by_state:
        return by_state
    starts = [c for c in cities if c.city.lower().startswith(q)]
    if starts:
        return starts
    return [
        c for c in cities
        if q in c.city.lower() or q in c.state.lower() or q in f"{c.city}, {c.state}".lower()
    ]


def days_until(target: date, today: date) -> int:
    return (target - today).days


def weeks_before(anchor: date, weeks: int) -> date:
    """Date `weeks` weeks after (or before, if negative) `anchor`.

    Offsets are expressed the way gardeners say them: a crop that is
    "started indoors 6 weeks before last frost" has start_indoors_weeks = -6,
    so weeks_before(anchor, -6) lands 6 weeks BEFORE the anchor.
    """
    return anchor + timedelta(weeks=weeks)
