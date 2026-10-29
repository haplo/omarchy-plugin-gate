"""The post-merge tripwire: a net for merges that did not come through the gate."""

import shlex
from pathlib import Path

from .config import Config
from .context import Context
from .git import Repo
from .output import printable, warn
from .state import write_atomic


def hook_path(directory: Path) -> Path | None:
    hooks = Repo(directory).git_path("hooks")
    return hooks / "post-merge" if hooks else None


def _command(cfg: Config) -> str:
    """The hook's gate invocation. The root and state are fixed when the hook is
    written, so the tripwire uses the same paths as the run that installed it."""
    gate = shlex.quote(str(cfg.self_path))
    root = shlex.quote(str(cfg.root))
    state = shlex.quote(str(cfg.state_root))
    return f"{gate} --root {root} --state {state} _post-merge"


def hook_text(cfg: Config, name: str) -> str:
    state = shlex.quote(str(cfg.state_root))
    log = shlex.quote(str(cfg.state_root / "hooks.log"))
    return f"""\
#!/usr/bin/env bash
# Installed by omarchy-plugin-gate for {printable(name)}. Reviews out-of-band merges.
top=$(git rev-parse --show-toplevel 2>/dev/null || pwd)
mkdir -p {state}
exec {_command(cfg)} "$top" >>{log} 2>&1
"""


def hook_ok(cfg: Config, directory: Path) -> bool:
    """Installed, pointing at this binary, and using this root and state."""
    path = hook_path(directory)
    if path is None or not path.is_file():
        return False
    try:
        return _command(cfg) in path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False


def install_hook(cfg: Config, directory: Path, name: str) -> bool:
    path = hook_path(directory)
    if path is None:
        return False
    try:
        write_atomic(path, hook_text(cfg, name))
        path.chmod(0o755)
    except OSError:
        return False
    return True


def ensure_hooks(ctx: Context, name: str) -> None:
    clone = ctx.clone_dir(name)
    if not hook_ok(ctx.cfg, clone) and not install_hook(ctx.cfg, clone, name):
        warn(f"could not install the tripwire in {clone}")
    installed = ctx.installed_dir(name)
    if (
        installed
        and installed.is_dir()
        and not hook_ok(ctx.cfg, installed)
        and not install_hook(ctx.cfg, installed, name)
    ):
        warn(f"could not install the tripwire in {installed}")


def is_upstream_commit(repo: Repo, sha: str) -> bool:
    """A commit belongs to us if it is not reachable from upstream. Only upstream
    commits are ever rolled back; local work is nobody's business but yours."""
    branch = repo.default_branch()
    if not branch:
        return False
    upstream = repo.upstream(branch)
    return upstream is not None and repo.is_ancestor(sha, upstream)
