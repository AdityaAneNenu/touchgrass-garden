"""Command-line interface for Touch Grass Garden.

Subcommands:
  plan    [city]  - this week's planting tasks (offline, no LLM needed)
  brief   [city]  - plan + local-LLM weekly briefing
  ask     [city]  - one-shot question to the local model
  chat    [city]  - interactive REPL (model loads once)
  config          - show/set your saved location or custom frost dates
  cities          - list bundled frost-date locations
  doctor          - check model/runtime availability

Exit codes: 0 success | 1 runtime/model error | 2 usage error | 130 Ctrl+C
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import date

from touchgrass import __version__
from touchgrass.config import (
    Profile,
    load_profile,
    resolve_profile_location,
    save_profile,
)
from touchgrass.errors import TouchGrassError, UsageError
from touchgrass.frost import ResolvedFrost, find_city, load_frost_dates
from touchgrass.planner import Plan, Task
from touchgrass.planner import plan as build_plan

log = logging.getLogger("touchgrass.cli")


# --------------------------------------------------------------- location

def _resolve_location(city_query: str | None, today: date) -> tuple[ResolvedFrost, str]:
    """Resolve a city argument, falling back to the saved profile.

    Returns (resolved_frost, human label); raises UsageError on problems.
    """
    if not city_query:
        entry, label = resolve_profile_location()
        return entry.resolve(today), label

    matches = find_city(city_query)
    if not matches:
        known = ", ".join(c.city for c in load_frost_dates()[:8])
        raise UsageError(
            f"No built-in frost dates for '{city_query}'. "
            f"Try one of: {known}, ... (command: touchgrass cities)\n"
            f"Or set custom dates: touchgrass config set-frost "
            f"--place \"My Garden\" --last 05-05 --first 10-05"
        )
    if len(matches) > 1:
        opts = ", ".join(f"{c.city}, {c.state}" for c in matches[:5])
        log.warning("'%s' matches several places: %s - using the first",
                    city_query, opts)
    chosen = matches[0]
    return chosen.resolve(today), f"{chosen.city}, {chosen.state} (zone {chosen.zone})"


def _plan_date(args: argparse.Namespace) -> date:
    raw = getattr(args, "date", None)
    if not raw:
        return date.today()
    try:
        return date.fromisoformat(raw)
    except ValueError:
        raise UsageError(
            f"'{raw}' is not a valid date - expected YYYY-MM-DD, e.g. 2026-03-15"
        ) from None


# ------------------------------------------------------------- formatting

def _task_line(task: Task, today: date) -> str:
    when = "today" if task.days_until == 0 else (
        f"in {task.days_until} days" if task.days_until > 0
        else f"{-task.days_until} day(s) ago")
    marker = "*" if abs(task.days_until) <= 3 else "+"
    return (f"  {marker} {task.action:<13} {task.crop:<38} "
            f"{task.target_date:%b %d} ({when})")


def _strip_markdown(text: str) -> str:
    """Small models love **bold** and emoji even when told not to.

    Clean for two hazards: markdown tokens, and Unicode that legacy Windows
    consoles mangle (emoji, curly quotes, degree signs) - we normalize to
    ASCII so output is readable in any terminal.
    """
    for token in ("**", "__", "##", "# "):
        text = text.replace(token, "")
    for src, dst in (
        ("\u2018", "'"), ("\u2019", "'"),
        ("\u201c", '"'), ("\u201d", '"'),
        ("\u2013", "-"), ("\u2014", "-"),
        ("\u2026", "..."), ("\u2264", "<="), ("\u2265", ">="),
        ("\u00b0F", " degrees F"), ("\u00b0C", " degrees C"),
        ("\u00b0", " degrees "),
        ("\u00a0", " "),
    ):
        text = text.replace(src, dst)
    cleaned = "".join(ch for ch in text if ord(ch) < 128)
    return " ".join(cleaned.split())


def _print_plan(result: Plan, label: str, today: date) -> None:
    loc = result.location
    last_note = (" (next year)" if loc.last_spring_frost.year != today.year else "")
    first_note = (" (next year)" if loc.first_fall_frost.year != today.year else "")
    print("=" * 74)
    print(f"  TOUCH GRASS GARDEN - week of {today:%A, %B %d, %Y}")
    print(f"  {label}")
    print("=" * 74)
    print(f"  Next last-frost:  {loc.last_spring_frost:%b %d}{last_note}   "
          f"First fall-frost: {loc.first_fall_frost:%b %d}{first_note}   "
          f"Season: {loc.growing_season_days} days")
    print("-" * 74)
    if result.tasks:
        print(f"  DO THIS WEEK ({len(result.tasks)} jobs, in priority order):")
        for task in result.tasks:
            print(_task_line(task, today))
    elif result.later_tasks:
        print("  No jobs due this week - coming up next:")
        for task in result.later_tasks[:3]:
            print(_task_line(task, today))
    else:
        print("  Off-season: nothing due this week.")
        print(f"    - The garden wakes up again around {loc.last_spring_frost:%b %d}.")
        print("    - Good week for: cleaning tools, reading seed catalogs,")
        print("      composting leftover beds, and planning next year's layout.")
    if result.later_tasks:
        print("-" * 74)
        print("  ON DECK (next 45 days):")
        for task in result.later_tasks[:5]:
            print(_task_line(task, today))
    if result.harvest_reminders:
        print("-" * 74)
        print("  ROUGH HARVEST FORECASTS:")
        for line in result.harvest_reminders[:4]:
            print(f"    ~ {line}")
    print("-" * 74)
    print("  Data: bundled frost normals + crop rules (offline, no API calls).")
    print("  Your yard beats averages: check soil, not just the calendar.")
    print("=" * 74)


def _context_for_llm(result: Plan, label: str, today: date) -> str:
    loc = result.location
    lines = [
        f"Date: {today:%A, %B %d, %Y}",
        f"Location: {label}",
        f"Average last spring frost: {loc.last_spring_frost:%B %d}",
        f"Average first fall frost: {loc.first_fall_frost:%B %d}",
        "Tasks due this week:",
    ]
    lines += [f"- {t.action} {t.crop} by {t.target_date:%B %d} ({t.detail})"
              for t in result.tasks] or ["- (no fixed-deadline tasks)"]
    if result.later_tasks:
        lines.append("Coming up:")
        lines += [f"- {t.action} {t.crop} around {t.target_date:%B %d}"
                  for t in result.later_tasks[:5]]
    return "\n".join(lines)


def _maybe_export(result: Plan, label: str, args: argparse.Namespace) -> bool:
    """Handle --json / --ics export flags. Returns True when the caller
    should skip the human-readable render (i.e. --json was used)."""
    ics_path = getattr(args, "ics", None)
    if ics_path:
        _write_ics(result, label, ics_path)
    if getattr(args, "json", False):
        from touchgrass.exporters import plan_to_json

        print(plan_to_json(result, label))
        return True
    return False


def _write_ics(result: Plan, label: str, ics_path: str) -> None:
    from pathlib import Path

    from touchgrass.exporters import plan_to_ics

    out = Path(ics_path)
    out.write_text(plan_to_ics(result, label), encoding="utf-8", newline="")
    log.info("Calendar export written: %s", out.resolve())
    print(f"  Calendar export written: {out.resolve()}", file=sys.stderr)


def cmd_plan(args: argparse.Namespace) -> int:
    today = _plan_date(args)
    loc, label = _resolve_location(args.city, today)
    log.debug("Planning for %s on %s", label, today)
    result = build_plan(loc, today)
    if _maybe_export(result, label, args):
        return 0
    _print_plan(result, label, today)
    return 0


def cmd_brief(args: argparse.Namespace) -> int:
    from touchgrass.llm import GardenCoach

    today = _plan_date(args)
    loc, label = _resolve_location(args.city, today)
    result = build_plan(loc, today)
    if _maybe_export(result, label, args):
        return 0
    _print_plan(result, label, today)

    print("\n  WEEKLY BRIEFING (local Qwen2.5-1.5B, running on this machine)\n")
    coach = GardenCoach()  # raises ModelError -> handled in main()
    context = _context_for_llm(result, label, today)
    text = coach.weekly_briefing(context)
    for paragraph in text.splitlines():
        cleaned = _strip_markdown(paragraph)
        if cleaned:
            print(f"  {cleaned}")
    print(f"\n  [{coach.model_path.name} loaded in {coach.load_seconds:.1f}s, "
          f"generated at {coach.last_tokens_per_second:.1f} tok/s, offline]")
    return 0


def cmd_ask(args: argparse.Namespace) -> int:
    from touchgrass.llm import GardenCoach

    today = _plan_date(args)
    loc, label = _resolve_location(args.city, today)
    result = build_plan(loc, today)
    question = " ".join(args.question).strip()
    if not question:
        raise UsageError(
            "Ask something:  touchgrass ask denver \"when do I plant garlic?\""
        )
    coach = GardenCoach()
    context = _context_for_llm(result, label, today)
    answer = _strip_markdown(coach.advise(context, question))
    if getattr(args, "json", False):
        import json as _json
        print(_json.dumps({
            "question": question,
            "answer": answer,
            "model": coach.model_path.name,
            "tokens_per_second": round(coach.last_tokens_per_second, 1),
        }, indent=2))
        return 0
    print(answer)
    print(f"\n[{coach.model_path.name}, {coach.last_tokens_per_second:.1f} tok/s, offline]")
    return 0


def cmd_chat(args: argparse.Namespace) -> int:
    """Interactive REPL. The model loads exactly once for the whole session."""
    from touchgrass.chat import ChatSession, run_repl
    from touchgrass.llm import SYSTEM_PROMPT, GardenCoach

    state: dict = {"date": _plan_date(args)}

    def snapshot() -> tuple[Plan, str]:
        loc, label = _resolve_location(args.city, state["date"])
        return build_plan(loc, state["date"]), label

    current, current_label = snapshot()

    def context_builder() -> str:
        return (SYSTEM_PROMPT + "\n\nContext about my garden:\n"
                + _context_for_llm(current, current_label, state["date"]))

    def on_plan() -> None:
        _print_plan(current, current_label, state["date"])

    def on_date_change(target: date) -> None:
        nonlocal current, current_label
        state["date"] = target
        current, current_label = snapshot()

    print(f"Model loading for {current_label} ...")
    coach = GardenCoach()
    session = ChatSession(
        context_builder=context_builder,
        responder=lambda messages: _strip_markdown(
            coach.complete(messages, max_tokens=260)),
        on_plan=on_plan,
        on_date_change=on_date_change,
    )
    log.debug("Model ready in %.1fs", coach.load_seconds)

    def _prompt(text: str) -> None:
        sys.stdout.write(text)
        sys.stdout.flush()

    code = run_repl(session, sys.stdin, prompt=_prompt)
    print(f"\n[session: {session.turns} question(s), "
          f"{coach.model_path.name}, offline]")
    return code


def cmd_config(args: argparse.Namespace) -> int:
    """show | set-city | set-frost | clear - manage the saved profile."""
    action = args.config_action

    if action == "show":
        from touchgrass.config import config_path

        profile = load_profile(strict=True)
        path = config_path()
        if profile.is_empty:
            print(f"No profile configured ({path})")
            print("Set one:  touchgrass config set-city denver")
            return 0
        print(f"Profile ({path}):")
        for key, value in profile.to_dict().items():
            if key != "version":
                print(f"  {key}: {value}")
        return 0

    if action == "set-city":
        matches = find_city(args.query)
        if not matches:
            raise UsageError(
                f"'{args.query}' is not in the dataset - see: touchgrass cities"
            )
        chosen = matches[0]
        save_profile(Profile(city=f"{chosen.city}, {chosen.state}"))
        print(f"Saved default location: {chosen.city}, {chosen.state} "
              f"(zone {chosen.zone})")
        return 0

    if action == "set-frost":
        if not (args.place and args.last and args.first):
            raise UsageError(
                "set-frost needs --place, --last MM-DD and --first MM-DD:\n"
                "  touchgrass config set-frost --place \"My Garden\" "
                "--last 05-05 --first 10-05 --zone 6a"
            )
        # Validate before saving via the Profile round-trip
        candidate = Profile(place=args.place, zone=args.zone,
                            last_frost=args.last, first_frost=args.first)
        entry = candidate.frost_entry()  # raises ConfigError on bad dates
        save_profile(candidate)
        print(f"Saved custom frost dates for {entry.city}: "
              f"last {args.last}, first {args.first}"
              + (f", zone {args.zone}" if args.zone else ""))
        return 0

    if action == "clear":
        from touchgrass.config import config_path

        path = config_path()
        if path.is_file():
            path.unlink()
            print(f"Removed {path}")
        else:
            print("Nothing to remove.")
        return 0

    raise UsageError(f"Unknown config action: {action}")


def cmd_cities(_args: argparse.Namespace) -> int:
    cities = load_frost_dates()
    print(f"{'CITY':<22}{'ST':<5}{'ZONE':<6}{'LAST FROST':<12}{'FIRST FROST':<12}")
    for c in cities:
        lf = f"{c.last_frost[0]:02d}-{c.last_frost[1]:02d}"
        ff = f"{c.first_frost[0]:02d}-{c.first_frost[1]:02d}"
        print(f"{c.city:<22}{c.state:<5}{c.zone:<6}{lf:<12}{ff:<12}")
    print(f"\n{len(cities)} locations, all bundled offline. "
          f"Approximate normals - verify locally.")
    return 0


def cmd_doctor(_args: argparse.Namespace) -> int:
    from touchgrass.llm import DEFAULT_MODEL_DIR, find_model

    print(f"Touch Grass Garden {__version__}")
    ok = True

    try:
        import llama_cpp  # noqa: F401
        print("  [ok] llama-cpp-python installed")
    except ImportError:
        print("  [!!] llama-cpp-python missing - run: uv sync")
        ok = False

    model = find_model()
    if model:
        size_mb = model.stat().st_size / 1e6
        print(f"  [ok] model found: {model.name} ({size_mb:.0f} MB)")
    else:
        print(f"  [!!] no model in {DEFAULT_MODEL_DIR} - run: "
              f"powershell -File scripts/download-model.ps1")
        ok = False

    print("  [ok] frost dates + crop rules bundled (offline data)")
    profile = load_profile()
    where = "saved profile" if not profile.is_empty else "none (pass a city)"
    print(f"  [{'ok' if not profile.is_empty else '--'}] default location: {where}")
    print("\n" + ("Everything present - you can go touch grass." if ok
                  else "Fix the items marked [!!] above."))
    return 0 if ok else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="touchgrass",
        description="Offline garden planner with a local open-weight LLM.",
        epilog="Exit codes: 0 success, 1 runtime/model error, "
               "2 usage error, 130 interrupted.",
    )
    parser.add_argument("--version", action="version",
                        version=f"touchgrass {__version__}")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="debug logging to stderr")
    sub = parser.add_subparsers(dest="command")

    def add_common(p: argparse.ArgumentParser) -> None:
        p.add_argument("city", nargs="?",
                       help="city/state to look up (default: saved profile)")
        p.add_argument("--date", help="override today (YYYY-MM-DD)")
        p.add_argument("--json", action="store_true",
                       help="machine-readable JSON output")

    p_plan = sub.add_parser("plan", help="this week's planting tasks (no AI needed)")
    add_common(p_plan)
    p_plan.add_argument("--ics", metavar="FILE",
                        help="also export tasks to an iCalendar (.ics) file")
    p_plan.set_defaults(func=cmd_plan)

    p_brief = sub.add_parser("brief", help="plan + local-LLM weekly briefing")
    add_common(p_brief)
    p_brief.add_argument("--ics", metavar="FILE",
                         help="also export tasks to an iCalendar (.ics) file")
    p_brief.set_defaults(func=cmd_brief)

    p_ask = sub.add_parser("ask", help="ask the local model a garden question")
    add_common(p_ask)
    p_ask.add_argument("question", nargs="*", help="your question")
    p_ask.set_defaults(func=cmd_ask)

    p_chat = sub.add_parser("chat", help="interactive REPL (model loads once)")
    add_common(p_chat)
    p_chat.set_defaults(func=cmd_chat)

    p_cfg = sub.add_parser("config", help="manage your saved location/profile")
    cfg_sub = p_cfg.add_subparsers(dest="config_action", required=True)
    p_show = cfg_sub.add_parser("show", help="print the current profile")
    p_show.set_defaults(func=cmd_config)
    p_city = cfg_sub.add_parser("set-city", help="save a bundled city as default")
    p_city.add_argument("query")
    p_city.set_defaults(func=cmd_config)
    p_frost = cfg_sub.add_parser("set-frost", help="save custom frost dates")
    p_frost.add_argument("--place", required=True, help="name for your location")
    p_frost.add_argument("--last", required=True, metavar="MM-DD",
                         help="average last spring frost")
    p_frost.add_argument("--first", required=True, metavar="MM-DD",
                         help="average first fall frost")
    p_frost.add_argument("--zone", help="USDA zone, e.g. 6a (optional)")
    p_frost.set_defaults(func=cmd_config)
    p_clear = cfg_sub.add_parser("clear", help="delete the saved profile")
    p_clear.set_defaults(func=cmd_config)

    p_cities = sub.add_parser("cities", help="list bundled frost-date locations")
    p_cities.set_defaults(func=cmd_cities)

    p_doc = sub.add_parser("doctor", help="check model + runtime availability")
    p_doc.set_defaults(func=cmd_doctor)

    return parser


def main(argv: list[str] | None = None) -> int:
    # The local model emits Unicode punctuation; make sure the terminal pipe
    # uses UTF-8 rather than a legacy code page.
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
        except (AttributeError, OSError):
            pass

    parser = build_parser()
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if getattr(args, "verbose", False) else logging.WARNING,
        format="%(levelname)s %(name)s: %(message)s",
        stream=sys.stderr,
    )

    if not getattr(args, "func", None):
        # Bare `touchgrass`: friendly nudge instead of argparse's error.
        parser.print_help()
        return 2

    try:
        return args.func(args)
    except TouchGrassError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return exc.exit_code
    except KeyboardInterrupt:
        print("\ninterrupted", file=sys.stderr)
        return 130
    except BrokenPipeError:
        return 0


if __name__ == "__main__":
    raise SystemExit(main())



