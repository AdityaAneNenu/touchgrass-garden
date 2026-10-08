# Changelog

All notable changes to Touch Grass Garden are documented here.
Format: [Keep a Changelog](https://keepachangelog.com/); versioning: [SemVer](https://semver.org/).

## [1.0.0] - 2026-10-07

Production release. First version with a stability contract.

### Added
- **Saved profile** (`touchgrass config`): set your default city once
  (`config set-city`) or enter fully **custom frost dates** for any location
  on Earth (`config set-frost --place ... --last MM-DD --first MM-DD`).
  `plan`/`brief`/`ask`/`chat` work with no city argument after that.
- **Interactive chat** (`touchgrass chat`): REPL where the model loads **once**
  for the whole session; `/plan`, `/date`, `/clear`, `/help`, `/quit` commands;
  bounded conversation history so prompts stay small for a 1.5B model.
- **JSON output** (`--json`) on `plan`, `brief`, and `ask` for scripting.
- **iCal export** (`--ics FILE`): due + on-deck tasks become all-day calendar
  events with a day-before reminder; stable UIDs so re-exports update events
  instead of duplicating them; RFC 5545 compliant (escaping, 75-octet folding).
- **Structured errors and stable exit codes**: 0 success, 1 runtime/model,
  2 usage, 130 interrupted. `touchgrass.errors` exception hierarchy.
- **Logging** (`--verbose`): structured debug logs on stderr.
- SHA-256 pin + verification in `scripts/download-model.ps1`.
- GitHub Actions CI (lint + tests on Python 3.11-3.13).
- ruff configuration (E/F/W/I/UP/B/C4), lint clean.
- LICENSE (MIT), CONTRIBUTING.md, this changelog.

### Changed
- `main()` now catches all expected errors centrally instead of ad-hoc
  `SystemExit` calls; bare `touchgrass` prints help and exits 2.
- Invalid `--date` values produce a friendly usage error (exit 2), not a
  traceback.
- Version single-sourced: `touchgrass.__version__` == `pyproject.toml`.
- Model loading and generation are logged at INFO/DEBUG levels.

### Fixed
- Frost dates no longer roll over to next year too early mid-season.
- `--date` is now honored when resolving the location (was resolving
  against wall-clock today).
- State-code city search ("CO") no longer matches city names first.
- Model output sanitized to ASCII (markdown, emoji, curly quotes, degree
  signs) so legacy Windows consoles don't render mojibake.

## [0.1.0] - 2026-10-06

Initial prototype: offline frost-date planner, local Qwen2.5-1.5B briefing,
one-shot `ask`, 20 tests.
