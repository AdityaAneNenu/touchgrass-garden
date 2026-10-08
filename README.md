# 🌱 Touch Grass Garden

**An offline garden planner with a local open-weight LLM at its core — built for the Hacktoberfest 2026 Open-Source AI Challenge, Week 1: "Touch Grass."**

You tell it your city. It tells you exactly what to start, sow, or transplant *this week* based on your average frost dates — and a small open-weight model (`Qwen2.5-1.5B-Instruct`) that runs **entirely on your laptop** writes the weekly briefing and answers follow-up questions. No API keys, no cloud, no telemetry. Unplug the network after setup and everything still works.

**→ See [DEMO.md](DEMO.md) for full, real terminal transcripts of every command.**

```
> touchgrass brief denver
==========================================================================
  TOUCH GRASS GARDEN - week of Sunday, March 15, 2026
  Denver, CO (zone 5b)
==========================================================================
  Next last-frost:  May 05   First fall-frost: Oct 05   Season: 153 days
--------------------------------------------------------------------------
  DO THIS WEEK (9 jobs, in priority order):
  + Start indoors Peppers                                Mar 10 (5 day(s) ago)
  + Start indoors Tomatoes                               Mar 24 (in 9 days)
  ...
--------------------------------------------------------------------------
  WEEKLY BRIEFING (local Qwen2.5-1.5B, running on this machine)
  ...model-generated encouragement and priority list...
```

## Why open innovation matters here

| Closed/cloud approach | What this does instead |
| --- | --- |
| Weather + gardening API with a key, rate limits, and a privacy policy | Frost dates and crop rules are **bundled JSON** — the deterministic core never calls out |
| GPT/Claude call for the briefing: costs per token, dies offline, sends your location to a third party | A **1.04 GB Apache-2.0 GGUF quant** of Qwen2.5 runs via `llama-cpp-python` on CPU. Your location and questions never leave the machine |
| "Works on our servers" | Runs on a $0/month, 8 GB-RAM, GPU-less Windows laptop. Model load ≈ 8 s, generation ≈ 6 tok/s |
| Model is a fixed black box | Swap in **any** GGUF (`TOUCHGRASS_MODEL=/path/to/model.gguf`) — smaller for speed, bigger for quality, fine-tuned if you want |

The architecture deliberately keeps the **rules deterministic and the prose generative**: the LLM never decides *what* is safe to plant (frost math is code with a 61-test suite); it only turns verified facts into a briefing that gets you out the door. That split is only practical because open models let us run inference where the data already lives — on your machine, next to your garden.

## The "Touch Grass" angle

The screen time is the shortest part:

1. Run `touchgrass brief <city>` once (≈1 minute, mostly model load).
2. Close the laptop.
3. Go start the seeds the briefing listed, check the actual soil, and touch grass.
4. Come back in a week.

The plan output even ends with *"Your yard beats averages: check soil, not just the calendar."*

## Quick start

Prerequisites: [uv](https://docs.astral.sh/uv/) (or Python 3.11+ + pip), ~2 GB free disk.

```powershell
# 1. Install dependencies (llama-cpp-python prebuilt CPU wheel)
uv sync

# 2. Download the open-weight model once (~1.04 GB, resumable, SHA-256 verified)
powershell -ExecutionPolicy Bypass -File scripts\download-model.ps1

# 3. Verify everything
uv run touchgrass doctor

# 4. Set your location once - after this, no city argument needed anywhere
uv run touchgrass config set-city denver
# ...or anywhere on Earth with your own frost dates:
uv run touchgrass config set-frost --place "My Garden" --last 05-05 --first 10-05 --zone 6a

# 5. Go touch grass
uv run touchgrass plan                     # this week's jobs (no model needed)
uv run touchgrass brief                    # plan + local-LLM weekly briefing
uv run touchgrass chat                     # REPL - model loads once, ask follow-ups
uv run touchgrass ask "is it too late for garlic?"
uv run touchgrass cities                   # 50 bundled locations
```

No `uv`? `pip install -e .` inside a virtualenv works too (llama-cpp-python may need a C++ toolchain if no wheel matches your platform).

## Command reference

| Command | What it does | Needs model? |
| --- | --- | --- |
| `plan [city]` | This week's jobs, on-deck list, harvest forecasts | no |
| `brief [city]` | `plan` + generated weekly briefing | yes |
| `ask [city] "…"` | One-shot grounded question | yes |
| `chat [city]` | Interactive REPL (`/plan`, `/date`, `/clear`, `/quit`) — model loads **once** | yes |
| `config show \| set-city \| set-frost \| clear` | Manage the saved profile | no |
| `cities` | List the 50 bundled locations | no |
| `doctor` | Check runtime, model, and profile | no |

**Flags** (on `plan`/`brief`/`ask`): `--date YYYY-MM-DD` plan for another day,
`--json` machine-readable output, `--ics FILE` export tasks as calendar events
with day-before reminders, `-v/--verbose` debug logging.

**Exit codes** (script-friendly): `0` success · `1` runtime/model error ·
`2` usage error · `130` interrupted (Ctrl+C).

**Environment variables**: `TOUCHGRASS_MODEL=/path/to/model.gguf` swap models ·
`TOUCHGRASS_HOME=/path` relocate the profile (used by tests).

## Testing & quality

```powershell
uv run pytest -q                # 61 tests, no model file needed
uv run ruff check touchgrass tests
```

The suite covers frost-date math (including year rollover), city search, plan windows for spring/summer/fall, the profile/config subsystem, JSON + iCal export (RFC 5545 compliance, stable UIDs), the chat REPL, CLI end-to-end behavior, and model-output sanitization — **none of them need the model**, which is exactly why CI can run them on every push (`.github/workflows/ci.yml`: lint + tests on Python 3.11–3.13, Linux + Windows).

## Model & data provenance

- **Model:** [Qwen2.5-1.5B-Instruct](https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF) (Apache-2.0), Q4_K_M GGUF, official Qwen release.
- **Runtime:** [llama-cpp-python](https://github.com/abetlen/llama-cpp-python) (MIT), CPU-only build.
- **Frost dates:** approximate long-term averages for 50 US metros, compiled from public almanac normals — verify locally before planting. The app says so on every run.
- **Crop rules:** standard extension-service guidance, encoded by hand in `crops.json`.

## How it works

```
touchgrass/
├── frost.py         # city lookup + frost-date math (pure stdlib)
├── planner.py       # crop rules → tasks due this week / on deck / harvests
├── llm.py           # llama-cpp-python wrapper (Qwen2.5-1.5B, CPU, seed=42)
├── config.py        # saved profile: default city or custom frost dates
├── chat.py          # REPL session logic (model injected - fully testable)
├── exporters.py     # JSON + iCal (RFC 5545) export
├── errors.py        # exception hierarchy with stable exit codes
├── cli.py           # plan | brief | ask | chat | config | cities | doctor
└── data/
    ├── frost_dates.json   # 50 US locations, avg first/last frost + USDA zone
    └── crops.json         # 30 crops: sow/transplant offsets, DTM, tips
```

- **Deterministic core:** every crop action is an offset from your last-spring or first-fall frost date (e.g. "tomatoes: start indoors 6 weeks before last frost"). A task is "due" when its target lands within ±10 days of today. Out-of-season dates roll to next year automatically.
- **Generative layer:** the plan is serialized to a compact context; the local model gets a fixed system prompt ("Sprout", the garden coach, ≤150 words, no fluff) and writes the briefing / answers questions, grounded in that context.
- **Graceful degradation:** `plan` works with no model file at all; `brief`/`ask`/`chat` fail loudly with instructions instead of silently calling a cloud API.

## Limitations (honest list)

- Bundled frost dataset covers 50 US metros — but any other location works via `config set-frost` (no code edits needed).
- 1.5B model occasionally drifts or bolds things despite instructions — that's why rules are code and the model only writes prose.
- ~6 tok/s on a CPU-only laptop; reduce `max_tokens` in `llm.py` for snappier output.
- Harvest dates are ±2-week estimates from days-to-maturity, not predictions.
- `chat` keeps the full history in memory only; sessions aren't persisted.

## License

MIT (code). Model weights: Apache-2.0 (Qwen). Frost/crop data: compiled from public sources, provided as-is.

#   t o u c h g r a s s - g a r d e n  
 