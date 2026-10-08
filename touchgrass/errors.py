"""Structured exceptions with stable exit codes for scripting.

Exit code contract (documented in README):
    0   success
    1   runtime/model failure (missing model, llama-cpp not installed)
    2   usage error (unknown city, bad flags, missing question)
    130 interrupted by user (Ctrl+C)
"""

from __future__ import annotations


class TouchGrassError(Exception):
    """Base class for all expected, user-facing errors."""

    exit_code = 1


class UsageError(TouchGrassError):
    """Bad input from the caller (unknown city, bad date, missing args)."""

    exit_code = 2


class ModelError(TouchGrassError):
    """The local model is missing or the runtime cannot load it."""

    exit_code = 1


class ConfigError(TouchGrassError):
    """The saved profile exists but is unreadable/invalid."""

    exit_code = 1
