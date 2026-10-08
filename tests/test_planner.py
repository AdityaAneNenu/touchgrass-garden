"""Tests for the planting-plan logic (no model required)."""

from datetime import date

from touchgrass.frost import FrostDates
from touchgrass.planner import load_crops, plan

DENVER = FrostDates("Denver", "CO", "5b", last_frost=(5, 5), first_frost=(10, 5))


def test_crop_dataset_loads():
    crops = load_crops()
    assert len(crops) >= 25
    names = {c.name for c in crops}
    assert "Tomatoes" in names
    assert "Garlic (fall planting)" in names


def test_mid_march_denver_starts_seeds_indoors():
    """Mar 15 in Denver is ~7 weeks before last frost (May 5):
    tomato starts (6 weeks before = Mar 24) are due this week."""
    today = date(2026, 3, 15)
    result = plan(DENVER.resolve(today), today)
    actions = {(t.crop, t.action) for t in result.tasks}
    assert ("Tomatoes", "Start indoors") in actions
    assert ("Peppers", "Start indoors") in actions
    # Peas (4 wks before frost = Apr 6) aren't due yet, but are on deck
    assert any(t.crop.startswith("Peas") for t in result.later_tasks)
    # Frost-tender crops must NOT be pushed outdoors in mid-March in zone 5b
    assert not any(t.action == "Transplant" and "Tomato" in t.crop
                   for t in result.tasks)


def test_late_may_denver_transplants_tender_crops():
    result = plan(DENVER.resolve(date(2026, 5, 20)), date(2026, 5, 20))
    actions = {(t.crop, t.action) for t in result.tasks}
    assert ("Tomatoes", "Transplant") in actions
    assert ("Peppers", "Transplant") in actions


def test_october_denver_garlic_is_due():
    """In early October, fall-planted garlic (4 wks before first frost) is the job."""
    today = date(2026, 9, 5)  # first frost Oct 5 - 4 wks = Sep 7
    result = plan(DENVER.resolve(today), today)
    actions = {(t.crop, t.action) for t in result.tasks}
    assert ("Garlic (fall planting)", "Plant") in actions
    # No spring transplanting jobs in fall
    assert not any(t.action == "Transplant" for t in result.tasks)


def test_tasks_are_sorted_by_urgency():
    today = date(2026, 4, 10)
    result = plan(DENVER.resolve(today), today)
    deltas = [abs(t.days_until) for t in result.tasks]
    assert deltas == sorted(deltas)


def test_upcoming_tasks_are_in_the_future():
    today = date(2026, 3, 15)
    result = plan(DENVER.resolve(today), today)
    assert all(t.target_date > today for t in result.later_tasks)


def test_harvest_forecasts_present_for_fast_crops():
    today = date(2026, 5, 20)
    result = plan(DENVER.resolve(today), today)
    assert any("Radish" in line or "Beans" in line
               for line in result.harvest_reminders)
