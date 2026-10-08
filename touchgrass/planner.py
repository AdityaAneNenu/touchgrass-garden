"""Turn frost dates + crop rules into a concrete to-do list for a given week."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path

from touchgrass.frost import ResolvedFrost

_DATA_DIR = Path(__file__).parent / "data"

# How far ahead/behind a target date we still consider it "due this week".
# 10 days gives a comfortable buffer around each target date so a weekly
# plan doesn't miss a job just because the ideal day fell on a weekday.
WINDOW_DAYS = 10


@dataclass(frozen=True)
class Crop:
    name: str
    type: str
    start_indoors_weeks: int | None
    direct_sow_weeks: int | None
    transplant_weeks: int | None
    days_to_maturity: int
    frost_tender: bool
    tip: str
    plant_before_first_frost_weeks: int | None = None


@dataclass
class Task:
    """One actionable job for the gardener this week."""

    crop: str
    action: str          # "Start indoors" | "Direct sow" | "Transplant" | "Plant"
    target_date: date
    detail: str          # human-readable "why now"
    tip: str
    days_until: int = 0   # target_date relative to the plan's "today"


@dataclass
class Plan:
    location: ResolvedFrost
    week_of: date
    tasks: list[Task] = field(default_factory=list)
    later_tasks: list[Task] = field(default_factory=list)
    harvest_reminders: list[str] = field(default_factory=list)

    is_offline_data = True


def load_crops(path: Path | None = None) -> list[Crop]:
    with open(path or (_DATA_DIR / "crops.json"), encoding="utf-8") as fh:
        raw = json.load(fh)
    return [Crop(**entry) for entry in raw["crops"]]


def _offset(anchor: date, weeks: int | None) -> date | None:
    if weeks is None:
        return None
    return anchor + timedelta(weeks=weeks)


def plan(location: ResolvedFrost, today: date, crops: list[Crop] | None = None) -> Plan:
    """Build this week's planting plan for a location.

    A task is 'due' when its target date falls within WINDOW_DAYS before or
    after `today`; tasks further out are listed as heads-ups.
    """
    crops = crops if crops is not None else load_crops()

    last = location.last_spring_frost
    first = location.first_fall_frost

    due: list[Task] = []
    later: list[Task] = []
    harvests: list[str] = []

    for crop in crops:
        candidates: list[tuple[str, date, str]] = []

        # Spring-season actions are anchored to the LAST spring frost
        # (the upcoming one if we're past this year's, which resolve() handles).
        spring_actions = (
            ("Start indoors", crop.start_indoors_weeks,
             lambda w: f"{abs(w)} weeks before last frost ({last:%b %d})"),
            ("Direct sow", crop.direct_sow_weeks,
             lambda w: (f"{abs(w)} weeks before last frost ({last:%b %d})" if w < 0
                        else f"{abs(w)} weeks after last frost ({last:%b %d})")),
            ("Transplant", crop.transplant_weeks,
             lambda w: f"{abs(w)} weeks after last frost ({last:%b %d})"),
        )
        for action, weeks, describe in spring_actions:
            if weeks is None:
                continue
            candidates.append((action, last + timedelta(weeks=weeks), describe(weeks)))

        # Fall-planted crops (garlic, bulbs) anchor to the FIRST autumn frost.
        if crop.plant_before_first_frost_weeks:
            weeks = crop.plant_before_first_frost_weeks
            candidates.append(("Plant", first - timedelta(weeks=weeks),
                               f"{weeks} weeks before first frost ({first:%b %d})"))

        for action, target, detail in candidates:
            if target is None or not detail:
                continue
            task = Task(crop=crop.name, action=action, target_date=target,
                        detail=detail, tip=crop.tip,
                        days_until=(target - today).days)
            delta = (today - target).days
            if abs(delta) <= WINDOW_DAYS:
                if action == "Start indoors" and delta > 0:
                    task.detail = f"was due {delta} day(s) ago ({detail}) - start now, it still works"
                due.append(task)
            elif target > today and (target - today).days <= 45:
                later.append(task)

        # Harvest reminder: approximate harvest date from transplant/direct-sow date
        sow_anchor = _offset(last, crop.transplant_weeks) or _offset(last, crop.direct_sow_weeks)
        if sow_anchor and crop.days_to_maturity <= 120:
            harvest = sow_anchor + timedelta(days=crop.days_to_maturity)
            if harvest >= today:
                year_note = f" {harvest.year}" if harvest.year != today.year else ""
                sow_year = f" {sow_anchor.year}" if sow_anchor.year != today.year else ""
                harvests.append(
                    f"{crop.name}: ~{harvest:%b %d}{year_note} "
                    f"from the earliest safe planting ({sow_anchor:%b %d}{sow_year})")

    due.sort(key=lambda t: abs((today - t.target_date).days))
    later.sort(key=lambda t: t.target_date)
    return Plan(location=location, week_of=today, tasks=due,
                later_tasks=later[:8], harvest_reminders=harvests[:6])
