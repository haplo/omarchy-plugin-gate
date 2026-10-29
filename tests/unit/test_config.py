import tomllib
from pathlib import Path

import pytest

from omarchy_plugin_gate import __version__
from omarchy_plugin_gate.config import DEFAULT_MAX_PATCH, DEFAULT_TIMEOUT, Config
from omarchy_plugin_gate.output import GateError

SELF = Path("/repo/bin/omarchy-plugin-gate")


def test_defaults_follow_home_and_xdg() -> None:
    cfg = Config.from_env({"HOME": "/h", "USER": "me"}, SELF)
    assert cfg.root == Path("/h/Work/omarchy-plugins")
    assert cfg.state_root == Path("/h/.local/state/omarchy-plugin-gate")
    assert cfg.installed_root == Path("/h/.config/omarchy/plugins")
    assert cfg.agent_file == Path("/h/.config/opencode/agents/plugin-reviewer.md")
    assert cfg.agent_src == Path("/repo/agents/plugin-reviewer.md.in")
    assert cfg.review_timeout == DEFAULT_TIMEOUT
    assert cfg.max_patch_bytes == DEFAULT_MAX_PATCH
    assert cfg.notify_policy == "all"
    assert cfg.model == ""
    assert cfg.user == "me"


def test_xdg_dirs() -> None:
    cfg = Config.from_env({"HOME": "/h", "XDG_STATE_HOME": "/s", "XDG_CONFIG_HOME": "/c"}, SELF)
    assert cfg.state_root == Path("/s/omarchy-plugin-gate")
    assert cfg.installed_root == Path("/c/omarchy/plugins")


def test_legacy_aliases_and_precedence() -> None:
    env = {"HOME": "/h", "PLUGIN_GATE_ROOT": "/legacy", "PLUGIN_GATE_NOTIFY": "ready"}
    cfg = Config.from_env(env, SELF)
    assert cfg.root == Path("/legacy")
    assert cfg.notify_policy == "ready"
    cfg = Config.from_env({**env, "OMARCHY_PLUGIN_GATE_ROOT": "/new"}, SELF)
    assert cfg.root == Path("/new")


def test_empty_counts_as_unset() -> None:
    cfg = Config.from_env(
        {"HOME": "/h", "OMARCHY_PLUGIN_GATE_ROOT": "", "OMARCHY_PLUGIN_GATE_TIMEOUT": ""}, SELF
    )
    assert cfg.root == Path("/h/Work/omarchy-plugins")
    assert cfg.review_timeout == DEFAULT_TIMEOUT


@pytest.mark.parametrize("value", ["abc", "0", "-5", "7m", "1.5"])
def test_bad_numbers_are_rejected(value: str) -> None:
    with pytest.raises(GateError, match="OMARCHY_PLUGIN_GATE_TIMEOUT"):
        Config.from_env({"HOME": "/h", "OMARCHY_PLUGIN_GATE_TIMEOUT": value}, SELF)
    with pytest.raises(GateError, match="OMARCHY_PLUGIN_GATE_MAX_PATCH"):
        Config.from_env({"HOME": "/h", "OMARCHY_PLUGIN_GATE_MAX_PATCH": value}, SELF)


def test_bad_notify_policy_is_rejected() -> None:
    with pytest.raises(GateError, match="all, ready, none"):
        Config.from_env({"HOME": "/h", "OMARCHY_PLUGIN_GATE_NOTIFY": "sometimes"}, SELF)


def test_version_matches_pyproject() -> None:
    pyproject = Path(__file__).parents[2] / "pyproject.toml"
    assert tomllib.loads(pyproject.read_text())["project"]["version"] == __version__
