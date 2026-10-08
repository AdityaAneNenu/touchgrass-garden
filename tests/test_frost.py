"""Tests for frost-date math and location lookup (no model required)."""

from datetime import date

import pytest

from touchgrass.frost import FrostDates, days_until, find_city, load_frost_dates


@pytest.fixture(scope="module")
def cities():
    return load_frost_dates()


def test_dataset_loads_and_is_nonempty(cities):
    assert len(cities) >= 30


def test_find_city_exact(cities):
    matches = find_city("denver", cities)
    assert len(matches) == 1
    assert matches[0].state == "CO"


def test_find_city_by_state(cities):
    matches = find_city("CO", cities)
    assert any(c.city == "Denver" for c in matches)


def test_find_city_no_match(cities):
    assert find_city("atlantis", cities) == []


def test_resolve_before_last_frost_same_year():
    loc = FrostDates("X", "YY", "6a", last_frost=(4, 15), first_frost=(10, 25))
    resolved = loc.resolve(date(2026, 3, 1))
    assert resolved.last_spring_frost == date(2026, 4, 15)
    assert resolved.first_fall_frost == date(2026, 10, 25)
    assert resolved.growing_season_days == 193


def test_resolve_after_all_frost_rolls_to_next_year():
    """On Nov 20 (past first frost), the *next* spring's last frost matters
    and first frost must not be in the past."""
    loc = FrostDates("X", "YY", "6a", last_frost=(4, 15), first_frost=(10, 25))
    resolved = loc.resolve(date(2026, 11, 20))
    assert resolved.last_spring_frost == date(2027, 4, 15)
    assert resolved.first_fall_frost == date(2027, 10, 25)


def test_days_until():
    assert days_until(date(2026, 10, 11), date(2026, 10, 5)) == 6
