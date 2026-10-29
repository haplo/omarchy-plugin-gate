import subprocess
from pathlib import Path

import pytest

from omarchy_plugin_gate import __version__, cli
from omarchy_plugin_gate.commands.add import clone_name
from omarchy_plugin_gate.commands.status import plugin_state
from omarchy_plugin_gate.config import Config
from omarchy_plugin_gate.hooks import hook_ok, hook_text, install_hook
from omarchy_plugin_gate.output import GateError, printable
from support import Upstream

LAUNCHER = Path(__file__).parents[2] / "bin" / "omarchy-plugin-gate"


def gate(*args: str, **env: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(LAUNCHER), *args],
        capture_output=True,
        text=True,
        env={"PATH": "/usr/bin:/bin", "HOME": "/nonexistent", **env},
        check=False,
    )


def test_launcher_version() -> None:
    r = gate("--version")
    assert (r.returncode, r.stdout) == (0, f"{__version__}\n")


def test_launcher_ignores_pythonpath(tmp_path: Path) -> None:
    evil = tmp_path / "omarchy_plugin_gate"
    evil.mkdir()
    (evil / "__init__.py").write_text("raise SystemExit('hijacked')\n")
    r = gate("--version", PYTHONPATH=str(tmp_path))
    assert r.returncode == 0, r.stderr


def test_unknown_command(capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main(LAUNCHER, ["frob"]) == 1
    err = capsys.readouterr().err
    assert err.startswith("omarchy-plugin-gate: unknown command: frob\n")


@pytest.mark.parametrize(
    "argv",
    [
        ["check", "--bogus"],
        ["approve", "demo", "--reas", "x"],
        ["add", "--dir"],
        ["add", "url", "--dir", ""],
        ["status", "-p", ""],
    ],
)
def test_bad_arguments_exit_1(argv: list[str], capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main(LAUNCHER, argv) == 1
    assert capsys.readouterr().err.startswith("omarchy-plugin-gate: ")


def test_help_needs_no_config(capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main(LAUNCHER, ["check", "--help"]) == 0
    assert "approve <name>" in capsys.readouterr().out


def test_bad_environment_is_reported(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OMARCHY_PLUGIN_GATE_TIMEOUT", "soon")
    assert cli.main(LAUNCHER, ["status"]) == 1
    assert "OMARCHY_PLUGIN_GATE_TIMEOUT" in capsys.readouterr().err


@pytest.mark.parametrize(
    ("url", "override", "name"),
    [
        ("https://github.com/o/omasync.git", "", "omasync"),
        ("https://github.com/o/omasync/", "", "omasync"),
        ("git@github.com:o/my plugin.git", "", "my-plugin"),
        ("host:repo", "", "host-repo"),
        ("https://x/y", "custom", "custom"),
    ],
)
def test_clone_name(url: str, override: str, name: str) -> None:
    assert clone_name(url, override) == name


@pytest.mark.parametrize("url", ["https://x/.hidden", "/"])
def test_clone_name_refuses(url: str) -> None:
    with pytest.raises(GateError):
        clone_name(url)


@pytest.mark.parametrize(
    ("approved", "installed", "exists", "held", "state"),
    [
        (None, None, False, None, "not reviewed yet"),
        ("a", "a", True, None, "installed"),
        ("a", "b", True, None, "ready to install"),
        ("a", None, True, None, "ready to install"),
        ("a", None, False, None, "approved, not installed"),
        ("a", "a", True, "c", "held back"),
        ("a", "a", True, "a", "installed"),
        (None, None, False, "c", "held back"),
    ],
)
def test_plugin_state(
    approved: str | None, installed: str | None, exists: bool, held: str | None, state: str
) -> None:
    assert plugin_state(approved, installed, exists, held) == state


def test_printable() -> None:
    assert printable("a\nb\tc\x1b") == "a\\nb\\tc\\x1b"
    assert printable("caf\u00e9 \u2603") == "caf\u00e9 \u2603"
    assert printable("raw\udcff") == "raw\\udcff"


def test_hook_quotes_paths_and_names(tmp_path: Path) -> None:
    cfg = Config.from_env(
        {"HOME": str(tmp_path), "OMARCHY_PLUGIN_GATE_STATE": str(tmp_path / "st ate")},
        tmp_path / "my repo" / "bin" / "omarchy-plugin-gate",
    )
    text = hook_text(cfg, "evil\nrm -rf ~")
    assert "\nrm -rf" not in text
    assert f"exec '{cfg.self_path}' _post-merge" in text
    assert f">>'{tmp_path / 'st ate' / 'hooks.log'}' 2>&1" in text
    r = subprocess.run(["bash", "-n"], input=text, text=True, capture_output=True, check=False)
    assert r.returncode == 0, r.stderr


def test_hook_install_and_detection(cfg: Config, upstream: Upstream) -> None:
    assert not hook_ok(cfg, upstream.path)
    assert install_hook(cfg, upstream.path, "demo")
    hook = upstream.path / ".git" / "hooks" / "post-merge"
    assert hook.stat().st_mode & 0o111
    assert hook_ok(cfg, upstream.path)


def test_hooks_from_the_bash_release_still_count(cfg: Config, upstream: Upstream) -> None:
    hook = upstream.path / ".git" / "hooks" / "post-merge"
    hook.write_text(
        "#!/usr/bin/env bash\n"
        "top=$(git rev-parse --show-toplevel 2>/dev/null || pwd)\n"
        f'exec "{cfg.self_path}" _post-merge "$top" >>"{cfg.state_root}/hooks.log" 2>&1\n'
    )
    assert hook_ok(cfg, upstream.path)
