"""End-to-end CLI tests that never touch the LLM."""

import json

import pytest

from touchgrass.cli import _strip_markdown, main


@pytest.fixture()
def home(tmp_path, monkeypatch):
    """Isolate the saved profile for tests that rely on it."""
    monkeypatch.setenv("TOUCHGRASS_HOME", str(tmp_path))
    return tmp_path


def test_plan_runs_offline(capsys):
    assert main(["plan", "denver", "--date", "2026-03-15"]) == 0
    out = capsys.readouterr().out
    assert "TOUCH GRASS GARDEN" in out
    assert "Denver, CO" in out
    assert "DO THIS WEEK" in out
    assert "offline" in out.lower()


def test_plan_json_output(capsys):
    assert main(["plan", "denver", "--date", "2026-03-15", "--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["app"] == "touchgrass"
    assert data["location"]["city"] == "Denver"
    assert data["tasks"]


def test_plan_ics_export(tmp_path, capsys):
    target = tmp_path / "out.ics"
    assert main(["plan", "denver", "--date", "2026-03-15",
                 "--ics", str(target)]) == 0
    assert target.is_file()
    text = target.read_text(encoding="utf-8")
    assert text.startswith("BEGIN:VCALENDAR")
    assert "BEGIN:VEVENT" in text


def test_plan_bad_date_is_usage_error(capsys):
    assert main(["plan", "denver", "--date", "not-a-date"]) == 2
    assert "not a valid date" in capsys.readouterr().err


def test_plan_without_city_uses_saved_profile(home, capsys):
    assert main(["config", "set-city", "portland"]) == 0
    capsys.readouterr()
    assert main(["plan", "--date", "2026-03-15"]) == 0
    out = capsys.readouterr().out
    assert "Portland, OR" in out


def test_plan_without_city_or_profile_is_usage_error(home, capsys):
    assert main(["plan", "--date", "2026-03-15"]) == 2
    assert "No location configured" in capsys.readouterr().err


def test_config_set_city_rejects_unknown(capsys):
    assert main(["config", "set-city", "atlantis"]) == 2
    assert "not in the dataset" in capsys.readouterr().err


def test_config_set_frost_and_plan_uses_it(home, capsys):
    code = main(["config", "set-frost", "--place", "My Farm",
                 "--last", "05-10", "--first", "10-01", "--zone", "5a"])
    assert code == 0
    assert "Saved custom frost dates" in capsys.readouterr().out
    assert main(["plan", "--date", "2026-03-15"]) == 0
    out = capsys.readouterr().out
    assert "My Farm" in out
    assert "May 10" in out


def test_config_clear(home, capsys):
    main(["config", "set-city", "denver"])
    capsys.readouterr()
    assert main(["config", "clear"]) == 0
    assert main(["config", "show"]) == 0
    assert "No profile configured" in capsys.readouterr().out



def test_cities_lists_dataset(capsys):
    assert main(["cities"]) == 0
    out = capsys.readouterr().out
    assert "Denver" in out and "Seattle" in out


def test_doctor_reports(capsys):
    code = main(["doctor"])
    out = capsys.readouterr().out
    assert "Touch Grass Garden" in out
    assert code in (0, 1)


def test_unknown_city_fails_cleanly(capsys):
    assert main(["plan", "atlantis"]) == 2
    err = capsys.readouterr().err
    assert "No built-in frost dates" in err


def test_bare_invocation_prints_help_and_exits_2(capsys):
    assert main([]) == 2
    assert "usage: touchgrass" in capsys.readouterr().out


def test_version_flag(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == 0
    assert "1.0.0" in capsys.readouterr().out


def test_doctor_version_matches_package(capsys):
    from touchgrass import __version__

    main(["doctor"])
    assert __version__ in capsys.readouterr().out


def test_strip_markdown_removes_markers_and_emoji():
    raw = "**Bold** and 🌱 emoji with curly \u2019quotes\u2019 and 50\u00b0F"
    cleaned = _strip_markdown(raw)
    assert cleaned == "Bold and emoji with curly 'quotes' and 50 degrees F"
    assert all(ord(ch) < 128 for ch in cleaned)


def test_strip_markdown_handles_dashes_and_ellipsis():
    raw = "a\u2014b\u2013c\u2026 done \u226410"
    assert _strip_markdown(raw) == "a-b-c... done <=10"
