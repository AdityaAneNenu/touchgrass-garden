"""Tests for JSON and iCal export (no model required)."""

import json
from datetime import date

from touchgrass.exporters import plan_to_dict, plan_to_ics, plan_to_json
from touchgrass.frost import FrostDates
from touchgrass.planner import plan

DENVER = FrostDates("Denver", "CO", "5b", last_frost=(5, 5), first_frost=(10, 5))


def _sample_plan(today=date(2026, 3, 15)):
    return plan(DENVER.resolve(today), today)


def test_plan_to_dict_shape():
    data = plan_to_dict(_sample_plan(), "Denver, CO (zone 5b)")
    assert data["app"] == "touchgrass"
    assert data["offline"] is True
    assert data["location"]["city"] == "Denver"
    assert data["week_of"] == "2026-03-15"
    assert isinstance(data["tasks"], list) and data["tasks"]
    task = data["tasks"][0]
    assert set(task) == {"crop", "action", "target_date",
                         "days_until", "detail", "tip"}
    date.fromisoformat(task["target_date"])  # parses


def test_plan_to_json_roundtrip():
    parsed = json.loads(plan_to_json(_sample_plan(), "label"))
    assert parsed["location"]["growing_season_days"] == 153


def test_ics_structure():
    ics = plan_to_ics(_sample_plan(), "Denver, CO")
    lines = ics.split("\r\n")
    assert lines[0] == "BEGIN:VCALENDAR"
    assert "END:VCALENDAR" in lines
    assert ics.count("BEGIN:VEVENT") == ics.count("END:VEVENT")
    assert ics.count("BEGIN:VEVENT") >= 1
    # All-day events use VALUE=DATE with YYYYMMDD
    assert any(line.startswith("DTSTART;VALUE=DATE:2026") for line in lines)
    # Each event carries a day-before reminder alarm
    assert ics.count("BEGIN:VALARM") == ics.count("BEGIN:VEVENT")


def test_ics_uids_stable_across_calls():
    """Same plan twice -> identical UIDs (else calendars duplicate events)."""
    first = plan_to_ics(_sample_plan(), "Denver, CO")
    second = plan_to_ics(_sample_plan(), "Denver, CO")

    def uids(ics: str) -> list[str]:
        return [line for line in ics.split("\r\n") if line.startswith("UID:")]

    assert uids(first) == uids(second)


def test_ics_line_folding():
    """No line exceeds 75 octets (RFC 5545 folding)."""
    ics = plan_to_ics(_sample_plan(), "Some Extremely Long Location Name " * 5)
    for line in ics.split("\r\n"):
        assert len(line.encode("utf-8")) <= 75


def test_ics_escapes_commas_and_semicolons():
    ics = plan_to_ics(_sample_plan(), "Denver, CO; Front Range")
    assert "Denver\\, CO\\; Front Range" in ics
