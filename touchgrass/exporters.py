"""Machine-readable exporters: JSON for scripting, iCal for real calendars.

Both are stdlib-only and deterministic - same plan in, same bytes out
(allowing for the DTSTAMP generation time in iCal).
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, date, datetime

from touchgrass import __version__
from touchgrass.planner import Plan


def plan_to_dict(result: Plan, label: str) -> dict:
    """Serialize a Plan to a stable JSON-friendly dict."""
    loc = result.location

    def task_dict(task) -> dict:
        return {
            "crop": task.crop,
            "action": task.action,
            "target_date": task.target_date.isoformat(),
            "days_until": task.days_until,
            "detail": task.detail,
            "tip": task.tip,
        }

    return {
        "app": "touchgrass",
        "app_version": __version__,
        "location": {
            "label": label,
            "city": loc.city,
            "state": loc.state,
            "zone": loc.zone,
            "last_spring_frost": loc.last_spring_frost.isoformat(),
            "first_fall_frost": loc.first_fall_frost.isoformat(),
            "growing_season_days": loc.growing_season_days,
        },
        "week_of": result.week_of.isoformat(),
        "tasks": [task_dict(t) for t in result.tasks],
        "on_deck": [task_dict(t) for t in result.later_tasks],
        "harvest_reminders": list(result.harvest_reminders),
        "offline": True,
    }


def plan_to_json(result: Plan, label: str, *, indent: int = 2) -> str:
    return json.dumps(plan_to_dict(result, label), indent=indent, sort_keys=False)


# ---------------------------------------------------------------- iCal (ICS)

def _ics_escape(text: str) -> str:
    """RFC 5545 TEXT escaping."""
    return (text.replace("\\", "\\\\")
                .replace(";", "\\;")
                .replace(",", "\\,")
                .replace("\r\n", "\\n")
                .replace("\n", "\\n"))


def _fold(line: str) -> str:
    """RFC 5545 line folding: max 75 octets per line."""
    if len(line) <= 75:
        return line
    parts = [line[:75]]
    rest = line[75:]
    while rest:
        parts.append(" " + rest[:74])
        rest = rest[74:]
    return "\r\n".join(parts)


def _vevent(uid: str, when: date, summary: str, description: str,
            stamp: str) -> list[str]:
    return [
        "BEGIN:VEVENT",
        f"UID:{uid}",
        f"DTSTAMP:{stamp}",
        f"DTSTART;VALUE=DATE:{when.strftime('%Y%m%d')}",
        f"SUMMARY:{_ics_escape(summary)}",
        f"DESCRIPTION:{_ics_escape(description)}",
        "BEGIN:VALARM",
        "TRIGGER:-P1D",
        "ACTION:DISPLAY",
        f"DESCRIPTION:{_ics_escape('Tomorrow: ' + summary)}",
        "END:VALARM",
        "END:VEVENT",
    ]


def plan_to_ics(result: Plan, label: str) -> str:
    """Export due + on-deck tasks as all-day calendar events.

    Events land on the target date with the day-before reminder, so the
    plan reaches the gardener's phone where they actually are.
    """
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Touch Grass Garden//touchgrass " + __version__ + "//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        f"X-WR-CALNAME:{_ics_escape('Touch Grass Garden - ' + label)}",
    ]
    for task in [*result.tasks, *result.later_tasks]:
        summary = f"{task.action}: {task.crop}"
        description = (
            f"Target {task.target_date:%Y-%m-%d} ({task.detail}). "
            f"Tip: {task.tip} Plan by Touch Grass Garden for {label}."
        )
        # Stable UID (hashlib, not hash()) so re-exporting updates events
        # instead of duplicating them in the user's calendar.
        digest = hashlib.sha256(
            f"{task.crop}|{task.action}|{task.target_date}".encode()
        ).hexdigest()[:16]
        uid = f"touchgrass-{task.target_date:%Y%m%d}-{digest}@touchgrass"
        lines.extend(_vevent(uid, task.target_date, summary, description, stamp))
    lines.append("END:VCALENDAR")
    return "\r\n".join(_fold(line) for line in lines) + "\r\n"
