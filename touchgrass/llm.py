"""Local open-weight LLM via llama-cpp-python (Qwen2.5-1.5B-Instruct, Q4_K_M).

Everything here runs on-device: no API keys, no telemetry, works with the
network cable pulled once the model file has been downloaded once.
"""

from __future__ import annotations

import logging
import os
import time
from pathlib import Path

from touchgrass.errors import ModelError

log = logging.getLogger("touchgrass.llm")

DEFAULT_MODEL_DIR = Path(__file__).resolve().parent.parent / "models"
DEFAULT_MODEL_NAME = "qwen2.5-1.5b-instruct-q4_k_m.gguf"
HF_DOWNLOAD_URL = (
    "https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF/resolve/main/"
    "qwen2.5-1.5b-instruct-q4_k_m.gguf"
)

SYSTEM_PROMPT = (
    "You are 'Sprout', a friendly garden coach living entirely on the user's "
    "laptop. You give practical, specific, no-fluff gardening advice grounded "
    "in the frost dates and crop data provided. Rules: never do arithmetic on "
    "dates - quote dates exactly as they appear in the context; no emoji; no "
    "markdown formatting; plain sentences only. You never recommend chemical "
    "shortcuts, you always say when something depends on local conditions, "
    "and you consistently nudge the user to go outside and check the actual "
    "soil. Keep answers under 150 words unless asked for more."
)


def find_model(model_dir: Path | None = None) -> Path | None:
    """Locate a .gguf file: env override > project models/ dir > any in dir."""
    env = os.environ.get("TOUCHGRASS_MODEL")
    if env and Path(env).is_file():
        return Path(env)
    directory = model_dir or DEFAULT_MODEL_DIR
    if not directory.is_dir():
        return None
    preferred = directory / DEFAULT_MODEL_NAME
    if preferred.is_file():
        return preferred
    candidates = sorted(directory.glob("*.gguf"))
    return candidates[0] if candidates else None


class GardenCoach:
    """Thin wrapper over a llama-cpp Llama instance with friendly errors."""

    def __init__(self, model_path: Path | None = None, verbose: bool = False):
        path = model_path or find_model()
        if path is None or not Path(path).is_file():
            raise ModelError(
                f"No model found. Expected {DEFAULT_MODEL_DIR / DEFAULT_MODEL_NAME}.\n"
                f"Run:  powershell -File scripts/download-model.ps1\n"
                f"(or set TOUCHGRASS_MODEL=/path/to/any.gguf)"
            )
        try:
            from llama_cpp import Llama
        except ImportError as exc:
            raise ModelError(
                "llama-cpp-python is not installed. Run: uv sync"
            ) from exc

        self.model_path = Path(path)
        t0 = time.perf_counter()
        log.info("Loading model %s (CPU) ...", self.model_path.name)
        self._llm = Llama(
            model_path=str(self.model_path),
            n_ctx=4096,
            n_threads=max(2, (os.cpu_count() or 4) - 2),
            n_gpu_layers=0,          # CPU-only: works on any machine
            verbose=verbose,
            seed=42,                 # reproducible answers for demos
        )
        self.load_seconds = time.perf_counter() - t0
        self.last_tokens_per_second = 0.0
        log.info("Model loaded in %.1fs", self.load_seconds)

    def complete(self, messages: list[dict], max_tokens: int = 220) -> str:
        """Run one chat completion over full message history.

        This is the primitive used by multi-turn chat; `advise` wraps it
        with the single-question pattern.
        """
        t0 = time.perf_counter()
        result = self._llm.create_chat_completion(
            messages=messages,
            max_tokens=max_tokens,
            temperature=0.6,
            top_p=0.9,
        )
        elapsed = time.perf_counter() - t0
        tokens = result["usage"]["completion_tokens"]
        self.last_tokens_per_second = tokens / elapsed if elapsed else 0.0
        text = result["choices"][0]["message"]["content"].strip()
        log.debug("Generated %d tokens in %.1fs (%.1f tok/s)",
                  tokens, elapsed, self.last_tokens_per_second)
        return text

    def advise(self, context: str, question: str, max_tokens: int = 220) -> str:
        """Answer `question` grounded in `context` (frost dates + task list)."""
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Context about my garden:\n{context}\n\n{question}"},
        ]
        return self.complete(messages, max_tokens=max_tokens)

    def weekly_briefing(self, context: str, max_tokens: int = 320) -> str:
        """Generate the standalone 'this week in your garden' narrative."""
        question = (
            "Write my weekly garden briefing for the week shown in the context: "
            "a short opening line that gets me excited to walk outside, then "
            "the 2-4 highest-priority jobs in priority order with one concrete "
            "tip each, then one thing to watch for. Plain text, no markdown "
            "headers, at most 180 words."
        )
        return self.advise(context, question, max_tokens=max_tokens)
