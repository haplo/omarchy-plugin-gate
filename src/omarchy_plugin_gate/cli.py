"""Command-line entry point."""

import argparse
import io
import os
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import NoReturn

from . import __version__, proc
from .commands import add, approve, check, doctor, post_merge, status, update
from .config import Config
from .context import Context
from .output import GateError, say, warn

USAGE = """\
omarchy-plugin-gate — review Omarchy plugin updates before they reach the shell

  add <git-url> [--dir NAME] [--no-enable]
      Clone into the gate root, review the initial tree, install it disabled,
      enable it only on REVIEW PASS.

  check [-p NAME]
      Fetch upstream, review new commits, stage approved ones. Never installs.
      Hard structural failures are held without a model call; other structural
      findings go to the reviewer, which must clear each one.

  approve <name> [--sha SHA] [--reason TEXT] [--show] [-n|--dry-run]
      One-time human approval for a candidate the gate held back. Shows the
      verdict and findings, asks why (the answer may be empty), and advances
      gate-approved. Run update afterwards.

  update [-p NAME]
      Apply approved commits to ~/.config/omarchy/plugins/<id> and rescan.

  status [-p NAME]
      What is installed, approved, upstream, and held.

  doctor [-p NAME] [--fix]
      Verify the wiring (hooks, origin, refs, reviewer model). --fix installs
      missing hooks.

Environment:
  OMARCHY_PLUGIN_GATE_ROOT     gate root      (default ~/Work/omarchy-plugins)
  OMARCHY_PLUGIN_GATE_MODEL    reviewer model (default: OpenCode's default)
  OMARCHY_PLUGIN_GATE_NOTIFY   all|ready|none (default all)
  OMARCHY_PLUGIN_GATE_TIMEOUT  reviewer timeout in seconds (default 420)
  OMARCHY_PLUGIN_GATE_MAX_PATCH  patch size limit in bytes (default 2097152)
"""


class _Parser(argparse.ArgumentParser):
    """argparse that reports errors like the rest of the gate (exit 1, no usage dump)."""

    def error(self, message: str) -> NoReturn:
        raise GateError(message)


def _parser(prog: str) -> _Parser:
    p = _Parser(prog=f"omarchy-plugin-gate {prog}", add_help=False, allow_abbrev=False)
    p.add_argument("-h", "--help", action="store_true")
    return p


def _plugin_option(p: argparse.ArgumentParser) -> None:
    p.add_argument("-p", "--plugin", default="")


def _parse(prog: str, args: Sequence[str]) -> argparse.Namespace | None:
    """Parse one subcommand's arguments, or print usage and return None for --help."""
    p = _parser(prog)
    match prog:
        case "add":
            p.add_argument("url", nargs="?", default="")
            p.add_argument("--dir", default="")
            p.add_argument("--no-enable", action="store_true")
        case "approve":
            p.add_argument("name", nargs="?", default="")
            _plugin_option(p)
            p.add_argument("--sha", default="")
            p.add_argument("--reason", nargs="?", const="", default=None)
            p.add_argument("--show", action="store_true")
            p.add_argument("-n", "--dry-run", action="store_true")
        case _:
            _plugin_option(p)
            p.add_argument("--fix", action="store_true")
    ns = p.parse_args(list(args))
    if ns.help:
        say(USAGE.rstrip("\n"))
        return None
    for flag, attr in (
        ("--dir", "dir"),
        ("-p", "plugin"),
        ("--plugin", "plugin"),
        ("--sha", "sha"),
    ):
        if flag in args and getattr(ns, attr, None) == "":
            raise GateError(f"{flag} needs a value")
    return ns


def _context(self_path: Path) -> Context:
    return Context.create(Config.from_env(os.environ, self_path))


def dispatch(self_path: Path, argv: Sequence[str]) -> int:
    cmd, args = (argv[0], argv[1:]) if argv else ("", [])
    match cmd:
        case "" | "-h" | "--help" | "help":
            say(USAGE.rstrip("\n"))
            return 0
        case "--version":
            say(__version__)
            return 0
        case "_post-merge":
            return post_merge.run(_context(self_path), args[0] if args else "")
        case "add":
            if (ns := _parse(cmd, args)) is None:
                return 0
            return add.run(
                _context(self_path), add.AddArgs(ns.url, dir=ns.dir, enable=not ns.no_enable)
            )
        case "approve":
            if (ns := _parse(cmd, args)) is None:
                return 0
            if ns.name and ns.plugin:
                raise GateError(f"unexpected argument: {ns.name}")
            return approve.run(
                _context(self_path),
                approve.ApproveArgs(
                    ns.name or ns.plugin,
                    sha=ns.sha,
                    reason=ns.reason,
                    show=ns.show,
                    dry_run=ns.dry_run,
                ),
            )
        case "check" | "update" | "status" | "doctor":
            if (ns := _parse(cmd, args)) is None:
                return 0
            ctx = _context(self_path)
            if cmd == "check":
                return check.run(ctx, ns.plugin)
            if cmd == "update":
                return update.run(ctx, ns.plugin)
            if cmd == "status":
                return status.run(ctx, ns.plugin)
            return doctor.run(ctx, ns.plugin, ns.fix)
        case _:
            warn(f"unknown command: {cmd}")
            print(USAGE.rstrip("\n"), file=sys.stderr)
            return 1


def main(self_path: Path, argv: Sequence[str] | None = None) -> int:
    if isinstance(sys.stdout, io.TextIOWrapper):
        sys.stdout.reconfigure(line_buffering=True)
    try:
        return dispatch(self_path, sys.argv[1:] if argv is None else argv)
    except GateError as e:
        warn(str(e))
        return 1
    except proc.CommandError as e:
        warn(str(e))
        return 1
    except KeyboardInterrupt:
        return 130
