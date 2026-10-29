import tomllib
from pathlib import Path

import pytest

from omarchy_plugin_gate import __version__
from omarchy_plugin_gate.config import DEFAULT_MAX_PATCH, DEFAULT_TIMEOUT, Config, Overrides
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


def test_environment_settings() -> None:
    env = {
        "HOME": "/h",
        "OMARCHY_PLUGIN_GATE_ROOT": "/r",
        "OMARCHY_PLUGIN_GATE_STATE": "/s",
        "OMARCHY_PLUGIN_GATE_AGENT": "other-reviewer",
        "OMARCHY_PLUGIN_GATE_MODEL": "venice/m",
        "OMARCHY_PLUGIN_GATE_NOTIFY": "ready",
        "OMARCHY_PLUGIN_GATE_TIMEOUT": "60",
        "OMARCHY_PLUGIN_GATE_MAX_PATCH": "1000",
    }
    cfg = Config.from_env(env, SELF)
    assert (cfg.root, cfg.state_root) == (Path("/r"), Path("/s"))
    assert cfg.agent_file == Path("/h/.config/opencode/agents/other-reviewer.md")
    assert (cfg.model, cfg.notify_policy) == ("venice/m", "ready")
    assert (cfg.review_timeout, cfg.max_patch_bytes) == (60, 1000)


def test_overrides_beat_the_environment() -> None:
    env = {
        "HOME": "/h",
        "OMARCHY_PLUGIN_GATE_ROOT": "/env-root",
        "OMARCHY_PLUGIN_GATE_STATE": "/env-state",
        "OMARCHY_PLUGIN_GATE_AGENT": "env-agent",
        "OMARCHY_PLUGIN_GATE_MODEL": "env/model",
        "OMARCHY_PLUGIN_GATE_NOTIFY": "all",
        "OMARCHY_PLUGIN_GATE_TIMEOUT": "abc",
        "OMARCHY_PLUGIN_GATE_MAX_PATCH": "abc",
    }
    over = Overrides(
        root="/r",
        state="/s",
        agent="flag-agent",
        model="flag/model",
        notify="none",
        timeout="30",
        max_patch="500",
    )
    cfg = Config.from_env(env, SELF, over)
    assert (cfg.root, cfg.state_root) == (Path("/r"), Path("/s"))
    assert cfg.agent == "flag-agent"
    assert (cfg.model, cfg.notify_policy) == ("flag/model", "none")
    assert (cfg.review_timeout, cfg.max_patch_bytes) == (30, 500)


def test_unset_overrides_fall_back_to_the_environment() -> None:
    env = {"HOME": "/h", "OMARCHY_PLUGIN_GATE_ROOT": "/env-root"}
    cfg = Config.from_env(env, SELF, Overrides(model="flag/model"))
    assert cfg.root == Path("/env-root")
    assert cfg.model == "flag/model"


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


@pytest.mark.parametrize("value", ["abc", "0", "-5", "7m", "1.5"])
def test_bad_number_flags_name_the_flag(value: str) -> None:
    env = {"HOME": "/h", "OMARCHY_PLUGIN_GATE_TIMEOUT": "60"}
    with pytest.raises(GateError, match=r"^--timeout must"):
        Config.from_env(env, SELF, Overrides(timeout=value))
    with pytest.raises(GateError, match=r"^--max-patch must"):
        Config.from_env(env, SELF, Overrides(max_patch=value))


def test_bad_notify_policy_is_rejected() -> None:
    with pytest.raises(GateError, match="all, ready, none"):
        Config.from_env({"HOME": "/h", "OMARCHY_PLUGIN_GATE_NOTIFY": "sometimes"}, SELF)
    with pytest.raises(GateError, match=r"^--notify must be one of all, ready, none"):
        Config.from_env({"HOME": "/h"}, SELF, Overrides(notify="sometimes"))


def test_version_matches_pyproject() -> None:
    pyproject = Path(__file__).parents[2] / "pyproject.toml"
    assert tomllib.loads(pyproject.read_text())["project"]["version"] == __version__
