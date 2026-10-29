"""Settings, read once from the command line and the environment."""

import getpass
from collections.abc import Mapping
from dataclasses import dataclass, fields
from pathlib import Path

from .output import GateError

APPROVED_REF = "refs/heads/gate-approved"

# More findings than this in one candidate is a hard fail: the reviewer cannot
# give each one real attention, and a human should look instead.
MAX_FINDINGS = 40

NOTIFY_POLICIES = ("all", "ready", "none")

DEFAULT_TIMEOUT = 420
# 2 MiB of diff is roughly 600k-840k tokens, which leaves a 1M-token reviewer
# room for its prompt, findings and answer. Lower it for smaller models.
DEFAULT_MAX_PATCH = 2 * 1024 * 1024


@dataclass(frozen=True, slots=True)
class Overrides:
    """Settings given on the command line; None means the flag was not given.

    Each field is the flag `--<name>` (underscores become dashes) and overrides
    the variable `OMARCHY_PLUGIN_GATE_<NAME>`.
    """

    root: str | None = None
    state: str | None = None
    agent: str | None = None
    model: str | None = None
    notify: str | None = None
    timeout: str | None = None
    max_patch: str | None = None


def option_flag(field: str) -> str:
    return "--" + field.replace("_", "-")


def env_var(field: str) -> str:
    return "OMARCHY_PLUGIN_GATE_" + field.upper()


SETTING_FIELDS = tuple(f.name for f in fields(Overrides))


def _setting(overrides: Overrides, env: Mapping[str, str], field: str) -> tuple[str, str]:
    """The value of one setting and where it came from: the flag beats the
    environment, and an empty variable counts as unset."""
    value = getattr(overrides, field)
    if value is not None:
        return value, option_flag(field)
    return env.get(env_var(field), ""), env_var(field)


def _positive_int(raw: str, source: str, default: int, what: str) -> int:
    if not raw:
        return default
    try:
        value = int(raw, 10)
    except ValueError:
        value = 0
    if value <= 0:
        raise GateError(f"{source} must be a positive whole number of {what}, not '{raw}'")
    return value


def _current_user(env: Mapping[str, str]) -> str:
    if env.get("USER"):
        return env["USER"]
    try:
        return getpass.getuser()
    except OSError:
        return "unknown"


@dataclass(frozen=True, slots=True)
class Config:
    root: Path
    state_root: Path
    config_home: Path
    agent: str
    model: str
    notify_policy: str
    review_timeout: int
    max_patch_bytes: int
    self_path: Path
    user: str

    @property
    def installed_root(self) -> Path:
        return self.config_home / "omarchy" / "plugins"

    @property
    def agent_file(self) -> Path:
        return self.config_home / "opencode" / "agents" / f"{self.agent}.md"

    @property
    def agent_src(self) -> Path:
        return self.self_path.parent.parent / "agents" / "plugin-reviewer.md.in"

    @classmethod
    def from_env(
        cls, env: Mapping[str, str], self_path: Path, overrides: Overrides | None = None
    ) -> Config:
        over = overrides or Overrides()
        home = Path(env.get("HOME") or Path.home())
        state_home = Path(env.get("XDG_STATE_HOME") or home / ".local" / "state")
        config_home = Path(env.get("XDG_CONFIG_HOME") or home / ".config")
        root, _ = _setting(over, env, "root")
        state, _ = _setting(over, env, "state")
        agent, _ = _setting(over, env, "agent")
        model, _ = _setting(over, env, "model")
        notify, notify_source = _setting(over, env, "notify")
        notify = notify or "all"
        if notify not in NOTIFY_POLICIES:
            raise GateError(
                f"{notify_source} must be one of {', '.join(NOTIFY_POLICIES)}, not '{notify}'"
            )
        timeout, timeout_source = _setting(over, env, "timeout")
        max_patch, max_patch_source = _setting(over, env, "max_patch")
        return cls(
            root=Path(root) if root else home / "Work" / "omarchy-plugins",
            state_root=Path(state) if state else state_home / "omarchy-plugin-gate",
            config_home=config_home,
            agent=agent or "plugin-reviewer",
            model=model,
            notify_policy=notify,
            review_timeout=_positive_int(timeout, timeout_source, DEFAULT_TIMEOUT, "seconds"),
            max_patch_bytes=_positive_int(max_patch, max_patch_source, DEFAULT_MAX_PATCH, "bytes"),
            self_path=self_path,
            user=_current_user(env),
        )
