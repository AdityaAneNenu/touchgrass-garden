"""Tests for the chat REPL session logic (model injected as a fake)."""

import io

import pytest

from touchgrass.chat import HELP_TEXT, ChatSession, run_repl


def make_session(replies=None, **hooks):
    replies = replies or ["a fine answer"]
    calls = {"responder": 0}

    def responder(messages):
        calls["responder"] += 1
        return replies[(calls["responder"] - 1) % len(replies)]

    session = ChatSession(context_builder=lambda: "CONTEXT",
                          responder=responder, **hooks)
    return session, calls


def test_question_gets_reply_and_history_grows():
    session, _ = make_session()
    assert session.ask("what now?") == "a fine answer"
    assert session.ask("and then?") == "a fine answer"
    assert session.turns == 2
    assert [m["role"] for m in session.history] == ["user", "assistant"] * 2


def test_responder_receives_context_system_message():
    seen = {}

    def responder(messages):
        seen["messages"] = messages
        return "ok"

    session = ChatSession(context_builder=lambda: "FROST DATA",
                          responder=responder)
    session.ask("hello")
    assert seen["messages"][0] == {"role": "system", "content": "FROST DATA"}
    assert seen["messages"][1]["content"] == "hello"


def test_quit_raises_systemexit_zero():
    session, _ = make_session()
    with pytest.raises(SystemExit) as exc:
        session.ask("/quit")
    assert exc.value.code == 0


def test_help_is_a_command_not_a_question(capsys):
    session, calls = make_session()
    assert session.ask("/help") is None
    assert calls["responder"] == 0
    assert HELP_TEXT in capsys.readouterr().out


def test_plan_command_delegates(capsys):
    shown = []
    session, calls = make_session(on_plan=lambda: shown.append(1))
    assert session.ask("/plan") is None
    assert shown == [1]
    assert calls["responder"] == 0


def test_date_command_valid():
    dates = []
    session, _ = make_session(on_date_change=dates.append)
    reply = session.ask("/date 2026-04-01")
    assert dates == [__import__("datetime").date(2026, 4, 1)]
    assert "April 01, 2026" in reply


def test_date_command_invalid(capsys):
    session, _ = make_session()
    assert session.ask("/date nonsense") is None
    assert "not a valid date" in capsys.readouterr().out


def test_clear_resets_history():
    session, _ = make_session()
    session.ask("q1")
    assert "cleared" in (session.ask("/clear") or "")
    assert session.turns == 0


def test_unknown_slash_command_warns(capsys):
    session, calls = make_session()
    assert session.ask("/wat") is None
    assert "Unknown command" in capsys.readouterr().out
    assert calls["responder"] == 0


def test_blank_line_ignored():
    session, calls = make_session()
    assert session.ask("   ") is None
    assert calls["responder"] == 0


def test_run_repl_over_piped_stdin():
    stdin = io.StringIO("hello there\n/quit\n")
    session, calls = make_session(replies=["hi!"])
    out = []
    code = run_repl(session, stdin, prompt=lambda _t: None, reply=out.append)
    assert code == 0
    assert calls["responder"] == 1
    assert any(line.startswith("sprout> hi!") for line in out)


def test_run_repl_eof_clean_exit():
    stdin = io.StringIO("")  # Ctrl+D immediately
    session, calls = make_session()
    code = run_repl(session, stdin, prompt=lambda _t: None, reply=lambda *_: None)
    assert code == 0
    assert calls["responder"] == 0


def test_run_repl_continues_after_commands():
    stdin = io.StringIO("/help\nwhat is soil?\n/quit\n")
    session, calls = make_session(replies=["dirt"])
    out = []
    code = run_repl(session, stdin, prompt=lambda _t: None, reply=out.append)
    assert code == 0
    assert calls["responder"] == 1
