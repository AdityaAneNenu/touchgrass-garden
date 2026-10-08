"""Tests for the user profile / config subsystem (hermetic via TOUCHGRASS_HOME)."""

import json

import pytest

from touchgrass.config import (
    Profile,
    config_path,
    load_profile,
    resolve_profile_location,
    save_profile,
)
from touchgrass.errors import ConfigError, UsageError


@pytest.fixture()
def home(tmp_path, monkeypatch):
    """Point the config at a temp dir so tests never touch the real profile."""
    monkeypatch.setenv("TOUCHGRASS_HOME", str(tmp_path))
    return tmp_path


def test_missing_profile_is_empty(home):
    profile = load_profile()
    assert profile.is_empty
    assert not profile.has_custom_frost


def test_save_and_load_city_roundtrip(home):
    save_profile(Profile(city="Denver, CO"))
    loaded = load_profile()
    assert loaded.city == "Denver, CO"
    assert config_path().is_file()


def test_save_is_atomic_no_tmp_left_behind(home):
    save_profile(Profile(city="Portland, OR"))
    leftovers = list(home.glob("*.tmp"))
    assert leftovers == []


def test_profile_json_has_version(home):
    save_profile(Profile(city="Denver, CO"))
    raw = json.loads(config_path().read_text(encoding="utf-8"))
    assert raw["version"] == 1
    assert raw["city"] == "Denver, CO"


def test_resolve_profile_city(home):
    save_profile(Profile(city="Denver, CO"))
    entry, label = resolve_profile_location()
    assert entry.city == "Denver"
    assert "Denver" in label


def test_resolve_profile_empty_raises_usage_error(home):
    with pytest.raises(UsageError) as exc:
        resolve_profile_location()
    assert "config set-city" in str(exc.value)


def test_resolve_profile_stale_city_raises(home):
    save_profile(Profile(city="Atlantis, XX"))
    with pytest.raises(UsageError) as exc:
        resolve_profile_location()
    assert "not in the dataset" in str(exc.value)


def test_custom_frost_profile(home):
    save_profile(Profile(place="My Farm", zone="5a",
                         last_frost="05-10", first_frost="10-01"))
    entry, label = resolve_profile_location()
    assert entry.last_frost == (5, 10)
    assert entry.first_frost == (10, 1)
    assert "custom frost dates" in label
    assert "5a" in label


def test_corrupt_config_strict_raises(home):
    config_path().parent.mkdir(parents=True, exist_ok=True)
    config_path().write_text("{not json", encoding="utf-8")
    with pytest.raises(ConfigError):
        load_profile(strict=True)


def test_corrupt_config_lenient_returns_empty(home):
    config_path().parent.mkdir(parents=True, exist_ok=True)
    config_path().write_text("{not json", encoding="utf-8")
    assert load_profile().is_empty


def test_invalid_frost_date_in_profile_raises(home):
    profile = Profile(place="X", last_frost="13-99", first_frost="10-01")
    with pytest.raises(ConfigError):
        profile.frost_entry()
