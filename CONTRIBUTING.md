# Contributing

Thanks for wanting to make Touch Grass Garden better! This is a small,
deliberately dependency-light project: the bar is "keeps the offline promise
and stays testable without a GPU".

## Development setup

```powershell
uv sync                       # creates .venv, installs llama-cpp-python wheel
uv run pytest -q              # full suite, no model file needed
uv run ruff check touchgrass tests
uv run ruff check --fix touchgrass tests   # auto-fix most issues
```

Optional (for exercising `brief`/`ask`/`chat` locally):

```powershell
powershell -ExecutionPolicy Bypass -File scripts\download-model.ps1
```

## Ground rules

1. **Offline is the product.** No new network calls at runtime. Data that
   the app needs must be bundled in `touchgrass/data/` or user-provided.
2. **Rules stay in code, prose stays in the model.** Anything safety- or
   date-related (frost math, planting windows) belongs in `planner.py` /
   `frost.py` with unit tests — never delegated to the LLM.
3. **Tests for every change.** The suite must pass without the model file
   so CI stays fast and free. Tests that need the model must be skipped
   gracefully, not failed.
4. **Stdlib first.** New runtime dependencies need a strong justification
   in the PR description (llama-cpp-python is the one big exception).
5. **Keep output terminal-safe.** Anything user-visible from model output
   should go through `_strip_markdown` (ASCII-only).

## Where to plug in

| You want to... | Start here |
| --- | --- |
| Add crops / fix planting rules | `touchgrass/data/crops.json`, `tests/test_planner.py` |
| Add locations | `touchgrass/data/frost_dates.json` (keep the `_comment` honest) |
| Improve prompts / briefing quality | `touchgrass/llm.py` (`SYSTEM_PROMPT`, `weekly_briefing`) |
| Add exports/formats | `touchgrass/exporters.py` + tests |
| Change CLI UX | `touchgrass/cli.py`, `tests/test_cli.py` |

## Pull requests

- One logical change per PR.
- `uv run ruff check` and `uv run pytest -q` must pass.
- Update `CHANGELOG.md` under an `Unreleased` heading.
- Describe *why* the change matters, not just what changed.
