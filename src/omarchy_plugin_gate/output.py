"""User-facing output. Diagnostics go to stderr with the command name."""

import sys

PREFIX = "omarchy-plugin-gate"


class GateError(Exception):
    """A user-facing failure: printed with the prefix, exit status 1."""


def say(msg: str = "") -> None:
    print(msg)


def info(msg: str) -> None:
    print(f"  {msg}")


def ok(msg: str) -> None:
    print(f"  ✓ {msg}")


def bad(msg: str) -> None:
    print(f"  ✗ {msg}")


def warn(msg: str) -> None:
    sys.stdout.flush()
    print(f"{PREFIX}: {msg}", file=sys.stderr, flush=True)


def indented(lines: list[str], width: int = 14) -> None:
    pad = " " * width
    for line in lines:
        print(f"{pad}{line}")


def printable(text: str) -> str:
    """Escape control characters and undecodable bytes so one value stays on one line."""
    return "".join(
        c if c.isprintable() else c.encode("unicode_escape").decode("ascii") for c in text
    )
