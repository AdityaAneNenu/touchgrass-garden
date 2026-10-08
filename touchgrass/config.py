"""User profile: saved default city or fully custom frost dates.

Config lives at (first match wins):
    $TOUCHGRASS_HOME/config.json         (used by tests / portable installs)
    %APPDATA%\\touchgrass\\config.json     (Windows)
    $XDG_CONFIG_HOME/touchgrass/config.json
    ~/.config/touchgrass/config.json

Shape:
    {"version": 1, "city": "denver"}
or  {"version": 1, "place": "My Garden", "zone": "6a",
     "last_frost": "05-05", "first_frost": "10-05"}

The custom form lets anyone outside the 50 bundled US cities use the app
without editing shipped data files.
"""

from __future__ import annotations

import json
import logging
import os
import sys
from dataclasses import dataclass
from pathlib import Path

from touchgrass.errors import ConfigError, UsageError
from touchgrass.frost import FrostDates

log = logging.getLogger("touchgrass.config")

CONFIG_FILENAME = "config.json"
CONFIG_VERSION = 1


def config_dir() -> Path:
    """Directory where the profile is stored (env override for tests)."""
    env = os.environ.get("TOUCHGRASS_HOME")
    if env:
        return Path(env)
    if sys.platform == "win32":
        appdata = os.environ.get("APPDATA")
        base = Path(appdata) if appdata else Path.home() / "AppData" / "Roaming"
        return base / "touchgrass"
    xdg = os.environ.get("XDG_CONFIG_HOME")
    base = Path(xdg) if xdg else Path.home() / ".config"
    return base / "touchgrass"


def config_path() -> Path:
    return config_dir() / CONFIG_FILENAME


@dataclass
class Profile:
    """Saved user preferences. Either `city` or the custom frost fields."""

    city: str | None = None
    place: str | None = None
    zone: str | None = None
    last_frost: str | None = None   # "MM-DD"
    first_frost: str | None = None  # "MM-DD"

    @property
    def has_custom_frost(self) -> bool:
        return bool(self.place and self.last_frost and self.first_frost)

    @property
    def is_empty(self) -> bool:
        return not (self.city or self.has_custom_frost)

    def to_dict(self) -> dict:
        data: dict = {"version": CONFIG_VERSION}
        for key in ("city", "place", "zone", "last_frost", "first_frost"):
            value = getattr(self, key)
            if value is not None:
                data[key] = value
        return data

    def frost_entry(self) -> FrostDates | None:
        """Build a FrostDates from the custom fields, if fully set."""
        if not self.has_custom_frost:
            return None
        try:
            last = _parse_mmdd(self.last_frost or "")
            first = _parse_mmdd(self.first_frost or "")
        except ValueError as exc:
            raise ConfigError(
                f"Invalid frost dates in {config_path()}: {exc}. "
                f"Expected MM-DD, e.g. 05-05."
            ) from exc
        return FrostDates(
            city=self.place or "Custom", state="", zone=self.zone or "-",
            last_frost=last, first_frost=first,
        )


def _parse_mmdd(text: str) -> tuple[int, int]:
    month_str, day_str = text.split("-", 1)
    month, day = int(month_str), int(day_str)
    if not (1 <= month <= 12 and 1 <= day <= 31):
        raise ValueError(f"'{text}' is not a valid month-day")
    return month, day


def load_profile(*, strict: bool = False) -> Profile:
    """Read the profile. Missing file -> empty; corrupt file -> ConfigError
    only when strict (config subcommands), else warn and return empty."""
    path = config_path()
    if not path.is_file():
        return Profile()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError("top-level JSON must be an object")
        version = raw.get("version", 1)
        if version != CONFIG_VERSION:
            raise ValueError(f"unsupported config version {version}")
        known = {k: v for k, v in raw.items()
                 if k in ("city", "place", "zone", "last_frost", "first_frost")
                 and isinstance(v, str)}
        return Profile(**known)
    except (ValueError, TypeError) as exc:
        if strict:
            raise ConfigError(f"Cannot read {path}: {exc}") from exc
        log.warning("Ignoring unreadable config %s: %s", path, exc)
        return Profile()


def save_profile(profile: Profile) -> Path:
    """Atomically write the profile (tmp file + replace)."""
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(
        json.dumps(profile.to_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    tmp.replace(path)
    log.debug("Saved profile to %s", path)
    return path


def resolve_profile_location() -> tuple[FrostDates, str]:
    """Turn the saved profile into a FrostDates + human label.

    Raises UsageError when no profile is configured.
    """
    profile = load_profile()
    if profile.is_empty:
        raise UsageError(
            "No location configured. Set one with:\n"
            "  touchgrass config set-city denver\n"
            "  touchgrass config set-frost --place \"My Garden\" "
            "--last 05-05 --first 10-05 [--zone 6a]\n"
            "or pass a city:  touchgrass plan denver"
        )
    if profile.has_custom_frost:
        entry = profile.frost_entry()  # may raise ConfigError
        zone_note = f", zone {entry.zone}" if entry.zone != "-" else ""
        return entry, f"{entry.city} (custom frost dates{zone_note})"
    assert profile.city is not None
    from touchgrass.frost import find_city  # local import avoids cycle

    matches = find_city(profile.city)
    if not matches:
        raise UsageError(
            f"Saved city '{profile.city}' is not in the dataset. "
            f"Re-set it with: touchgrass config set-city <city> "
            f"(see: touchgrass cities)"
        )
    chosen = matches[0]
    zone = f", zone {chosen.zone}" if chosen.zone else ""
    return chosen, f"{chosen.city}, {chosen.state}{zone}"

