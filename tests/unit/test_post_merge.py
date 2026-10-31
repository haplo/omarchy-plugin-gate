"""The tripwire works out its plugin from the hook, never from the merged files."""

from pathlib import Path

import pytest

from omarchy_plugin_gate.commands import post_merge
from omarchy_plugin_gate.config import APPROVED_REF
from omarchy_plugin_gate.context import Context
from omarchy_plugin_gate.plugins import approved_manifest_id
from support import Upstream, git


@pytest.fixture
def wired(
    ctx: Context, upstream: Upstream, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[Path, list[str], list[str]]:
    """A gate clone `demo` with gate-approved at its HEAD, an installed copy that
    tracks it, and records of what the tripwire reviewed and disabled."""
    ctx.cfg.root.mkdir(parents=True)
    clone = ctx.clone_dir("demo")
    git(tmp_path, "clone", "-q", str(upstream.path), str(clone))
    git(clone, "update-ref", APPROVED_REF, "HEAD")
    idir = ctx.cfg.installed_root / "selftest.demo"
    git(tmp_path, "clone", "-q", str(clone), str(idir))

    reviewed: list[str] = []
    disabled: list[str] = []

    def review(_ctx: Context, name: str, _clone: object, old: str, new: str) -> bool:
        reviewed.append(f"{name} {old}..{new}")
        return False

    monkeypatch.setattr(post_merge, "review", review)
    monkeypatch.setattr(post_merge, "disable_plugin", disabled.append)
    monkeypatch.setattr(post_merge, "notify", lambda *_args: None)
    return idir, reviewed, disabled


def change_id_upstream(ctx: Context, upstream: Upstream) -> str:
    upstream.manifest(id="selftest.other")
    new = upstream.commit("change the id")
    git(ctx.clone_dir("demo"), "fetch", "-q")
    return new


def test_approved_manifest_id_ignores_the_working_tree(ctx: Context, upstream: Upstream) -> None:
    ctx.cfg.root.mkdir(parents=True)
    clone = ctx.clone_dir("demo")
    git(clone.parent, "clone", "-q", str(upstream.path), str(clone))
    assert approved_manifest_id(ctx.clone("demo")) == ""
    git(clone, "update-ref", APPROVED_REF, "HEAD")
    (clone / "manifest.json").write_text('{"id": "selftest.other"}')
    assert approved_manifest_id(ctx.clone("demo")) == "selftest.demo"


def test_installed_copy_that_changes_its_id_is_reviewed_and_rolled_back(
    ctx: Context, upstream: Upstream, wired: tuple[Path, list[str], list[str]]
) -> None:
    idir, reviewed, disabled = wired
    old = git(idir, "rev-parse", "HEAD")
    new = change_id_upstream(ctx, upstream)
    git(idir, "pull", "-q", "--ff-only", "origin", "refs/remotes/origin/main")
    assert git(idir, "rev-parse", "HEAD") == new

    assert post_merge.run(ctx, "demo", str(idir)) == 1
    assert reviewed == [f"demo {old}..{new}"]
    assert git(idir, "rev-parse", "HEAD") == old
    assert disabled == ["selftest.demo"]


def test_clone_rollback_does_not_disable(
    ctx: Context, upstream: Upstream, wired: tuple[Path, list[str], list[str]]
) -> None:
    _idir, reviewed, disabled = wired
    clone = ctx.clone_dir("demo")
    old = git(clone, "rev-parse", "HEAD")
    new = change_id_upstream(ctx, upstream)
    git(clone, "merge", "-q", "--ff-only", "origin/main")

    assert post_merge.run(ctx, "demo", str(clone)) == 1
    assert reviewed == [f"demo {old}..{new}"]
    assert git(clone, "rev-parse", "HEAD") == old
    assert disabled == []


@pytest.mark.parametrize("name", ["nothing", "", "../demo"])
def test_unknown_plugin_is_left_alone(
    ctx: Context, upstream: Upstream, wired: tuple[Path, list[str], list[str]], name: str
) -> None:
    idir, reviewed, _disabled = wired
    new = change_id_upstream(ctx, upstream)
    git(idir, "pull", "-q", "--ff-only", "origin", "refs/remotes/origin/main")
    assert post_merge.run(ctx, name, str(idir)) == 0
    assert reviewed == []
    assert git(idir, "rev-parse", "HEAD") == new


def test_directory_of_another_plugin_is_left_alone(
    ctx: Context,
    upstream: Upstream,
    wired: tuple[Path, list[str], list[str]],
    tmp_path: Path,
) -> None:
    _idir, reviewed, _disabled = wired
    stray = tmp_path / "stray"
    git(tmp_path, "clone", "-q", str(ctx.clone_dir("demo")), str(stray))
    upstream.write("Widget.qml", "import QtQuick\nItem { width: 3 }\n")
    upstream.commit()
    git(ctx.clone_dir("demo"), "fetch", "-q")
    git(stray, "pull", "-q", "--ff-only", "origin", "refs/remotes/origin/main")

    assert post_merge.run(ctx, "demo", str(stray)) == 0
    assert reviewed == []
    log = (ctx.state.root / "gate.log").read_text()
    assert f"hook: {stray} is neither the clone nor the installed copy" in log
