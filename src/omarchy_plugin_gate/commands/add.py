"""add: clone, review the initial tree, install, enable only on REVIEW PASS."""

import json
import re
import shutil
import sys
from dataclasses import dataclass

from .. import proc
from ..config import APPROVED_REF
from ..context import Context
from ..hooks import install_hook
from ..notify import notify
from ..output import GateError, info, say, warn
from ..plugins import read_manifest
from ..review import review


@dataclass(frozen=True, slots=True)
class AddArgs:
    url: str
    dir: str = ""
    enable: bool = True


def clone_name(url: str, override: str = "") -> str:
    name = override or url.rstrip("/").rsplit("/", 1)[-1]
    name = re.sub(r"[^A-Za-z0-9._-]", "-", name.removesuffix(".git"))
    if not name:
        raise GateError(f"cannot derive a directory name from '{url}'; pass --dir")
    if name.startswith("."):
        raise GateError(f"refusing a name starting with a dot: {name}")
    return name


def _echo(result: proc.Result) -> None:
    out = (result.stdout + result.stderr).decode("utf-8", "replace").strip()
    if out:
        print(out, file=sys.stderr)


def _already_installed(plugin_id: str) -> bool:
    result = proc.run(["omarchy", "plugin", "list", "--json"], check=False)
    if not result.ok:
        return False
    try:
        entries = json.loads(result.stdout)
    except ValueError:
        return False
    return isinstance(entries, list) and any(
        isinstance(e, dict) and e.get("id") == plugin_id for e in entries
    )


def _enable(plugin_id: str, manifest: dict[str, object]) -> None:
    kinds = manifest.get("kinds")
    kinds = kinds if isinstance(kinds, list) else []
    if "bar" in kinds:
        info(f"{plugin_id} is a full-bar plugin; enable it manually with omarchy bar")
        return
    argv = ["omarchy", "plugin", "enable", plugin_id]
    section = ""
    if "bar-widget" in kinds:
        widget = manifest.get("barWidget")
        value = widget.get("defaultSection") if isinstance(widget, dict) else None
        section = value if isinstance(value, str) and value else "center"
        argv += ["--section", section]
    result = proc.run(argv, check=False)
    if not result.ok:
        _echo(result)
        warn(f"{plugin_id} is installed but could not be enabled")
    elif section:
        info(f"enabled in the {section} section")


def run(ctx: Context, args: AddArgs) -> int:
    if not args.url:
        raise GateError("add needs a git URL")
    name = clone_name(args.url, args.dir)
    clone_dir = ctx.clone_dir(name)
    if clone_dir.exists():
        raise GateError(
            f"'{name}' already exists at {clone_dir} — use: omarchy-plugin-gate check -p {name}"
        )

    ctx.cfg.root.mkdir(parents=True, exist_ok=True)
    say(f"Cloning {args.url} into {clone_dir}")
    result = proc.run(["git", "clone", "--quiet", "--", args.url, str(clone_dir)], check=False)
    if not result.ok:
        _echo(result)
        raise GateError("clone failed")

    plugin_id = ctx.manifest_id(name)
    if not plugin_id:
        shutil.rmtree(clone_dir)
        raise GateError("no manifest.json id at the repository root; not a plugin")

    result = proc.run(["omarchy", "plugin", "validate", str(clone_dir)], check=False)
    if not result.ok:
        shutil.rmtree(clone_dir)
        _echo(result)
        raise GateError("manifest validation failed; clone removed")

    if _already_installed(plugin_id):
        raise GateError(
            f"plugin id '{plugin_id}' is already installed — "
            f"use: omarchy-plugin-gate check -p {name}"
        )

    clone = ctx.clone(name)
    head = clone.head()
    if not head:
        raise GateError(f"{clone_dir} has no HEAD commit")
    rd = ctx.state.review_dir(name, head)
    say(f"Reviewing the initial import of {plugin_id} ({head})")
    if not review(ctx, name, clone, None, head):
        ctx.state.log_event(name, "add: initial review failed")
        notify(ctx, f"{plugin_id}: review failed", "Nothing was installed. Open status to see why.")
        say()
        say("Held back. Reasons:")
        for line in rd.verdict_lines()[1:]:
            say(f"  {line}")
        info(f"patch: {rd.patch}")
        raise GateError(f"{plugin_id} was not installed")

    ctx.state.set_marker(name, head, "initial import")
    clone.update_ref(APPROVED_REF, head)
    if not install_hook(ctx.cfg, clone_dir, name):
        warn(f"could not install the tripwire in {clone_dir}")
    ncleared = rd.cleared_count()
    if ncleared:
        info(f"the reviewer cleared {ncleared} structural finding(s): {rd.cleared}")

    say(f"Installing {plugin_id}")
    result = proc.run(["omarchy", "plugin", "add", str(clone_dir), "--yes"], check=False)
    if not result.ok:
        _echo(result)
        notify(ctx, f"{plugin_id}: install failed", f"The clone is kept at {clone_dir}.")
        raise GateError(f"omarchy plugin add failed; the clone is kept at {clone_dir}")

    if args.enable:
        _enable(plugin_id, read_manifest(clone_dir / "manifest.json") or {})
    else:
        info("installed disabled (--no-enable)")

    idir = ctx.cfg.installed_root / plugin_id
    if idir.is_dir():
        install_hook(ctx.cfg, idir, name)

    suffix = (
        f" The reviewer cleared {ncleared} structural finding(s); check status." if ncleared else ""
    )
    if args.enable:
        notify(ctx, f"{plugin_id}: installed", f"Reviewed, installed and enabled.{suffix}")
    else:
        notify(ctx, f"{plugin_id}: installed", f"Reviewed and installed, left disabled.{suffix}")
    say()
    say(f"Done. {plugin_id} at {head[:12]} (installed from the reviewed clone)")
    info(f"upstream clone: {clone_dir}")
    info(f"review: {rd.path}")
    return 0
