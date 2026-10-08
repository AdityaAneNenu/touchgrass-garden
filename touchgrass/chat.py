"""Interactive chat REPL - loads the model once, keeps conversation state.

Separation of concerns makes this testable without a model: `ChatSession`
holds history and dispatches commands; the LLM is injected as a callable.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date
from typing import TextIO

log = logging.getLogger("touchgrass.chat")

HELP_TEXT = """\
Commands:
  /plan       show this week's planting plan again
  /date DATE  jump to another date (YYYY-MM-DD)
  /clear      forget the conversation so far
  /help       this message
  /quit       exit (or Ctrl+C, or Ctrl+D)
Anything else is asked to Sprout, the on-device garden coach."""

WELCOME = """\
Sprout - your offline garden coach (model runs on this machine)
Type /help for commands, /quit to leave. Ask anything about your garden."""


@dataclass
class ChatSession:
    """Conversation state + command dispatch. No model dependency."""

    context_builder: Callable[[], str]
    responder: Callable[[list[dict]], str]
    history: list[dict] = field(default_factory=list)
    on_plan: Callable[[], None] | None = None
    on_date_change: Callable[[date], None] | None = None
    max_turns: int = 20  # cap prompt size for small models

    def ask(self, text: str) -> str | None:
        """Handle one input line. Returns a reply, or None if it was a
        command that already produced output / asked to quit."""
        text = text.strip()
        if not text:
            return None
        if text in ("/quit", "/exit", "/q"):
            raise SystemExit(0)
        if text == "/help":
            print(HELP_TEXT)
            return None
        if text == "/plan":
            if self.on_plan:
                self.on_plan()
            else:
                print("(plan not available in this session)")
            return None
        if text == "/clear":
            self.history.clear()
            return "(conversation cleared)"
        if text.startswith("/date"):
            if text == "/date":
                print("usage: /date 2026-03-15")
            else:
                raw = text[len("/date"):].strip()
                try:
                    target = date.fromisoformat(raw)
                except ValueError:
                    print(f"'{raw}' is not a valid date (expected YYYY-MM-DD)")
                    target = None
                if target and self.on_date_change:
                    self.on_date_change(target)
                    return f"(planning for {target:%A, %B %d, %Y})"
            return None
        if text.startswith("/"):
            print(f"Unknown command '{text.split()[0]}' - try /help")
            return None

        # Regular question: ground it in fresh context, keep bounded history.
        self.history.append({"role": "user", "content": text})
        messages = (
            [{"role": "system", "content": self.context_builder()}]
            + self.history[-self.max_turns:]
        )
        reply = self.responder(messages)
        self.history.append({"role": "assistant", "content": reply})
        return reply

    @property
    def turns(self) -> int:
        return len([m for m in self.history if m["role"] == "user"])


def run_repl(session: ChatSession,
             stdin: TextIO,
             prompt: Callable[[str], None] | None = None,
             reply: Callable[[str], None] = print) -> int:
    """Drive the REPL over arbitrary streams (real terminal or test fakes).

    `prompt` prints the input prompt (no newline); defaults to writing
    "you> " via the `reply` sink when none is given.
    """
    prompt = prompt or (lambda text: reply(text.rstrip("\n")))
    reply(WELCOME)
    while True:
        prompt("you> ")
        line = stdin.readline()
        if line == "":  # EOF (Ctrl+D / piped input exhausted)
            reply("")
            return 0
        try:
            answer = session.ask(line)
        except SystemExit as exc:
            return int(exc.code or 0)
        except KeyboardInterrupt:
            reply("")
            return 130
        if answer is not None:
            reply(f"sprout> {answer}")
    return 0
