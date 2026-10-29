"""Settings, read once from the environment."""

import getpass
from collections.abc import Mapping
from dataclasses import dataclass
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


def _first(env: Mapping[str, str], *names: str) -> str:
    """The first non-empty variable, like ${A:-${B:-}} in a shell."""
    for name in names:
        value = env.get(name, "")
        if value:
            return value
    return ""


def _positive_int(env: Mapping[str, str], name: str, default: int, what: str) -> int:
    raw = env.get(name, "")
    if not raw:
        return default
    try:
        value = int(raw, 10)
    except ValueError:
        value = 0
    if value <= 0:
        raise GateError(f"{name} must be a positive whole number of {what}, not '{raw}'")
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
    def from_env(cls, env: Mapping[str, str], self_path: Path) -> Config:
        home = Path(env.get("HOME") or Path.home())
        state_home = Path(_first(env, "XDG_STATE_HOME") or home / ".local" / "state")
        config_home = Path(_first(env, "XDG_CONFIG_HOME") or home / ".config")
        root = _first(env, "OMARCHY_PLUGIN_GATE_ROOT", "PLUGIN_GATE_ROOT")
        state = _first(env, "OMARCHY_PLUGIN_GATE_STATE")
        notify = _first(env, "OMARCHY_PLUGIN_GATE_NOTIFY", "PLUGIN_GATE_NOTIFY") or "all"
        if notify not in NOTIFY_POLICIES:
            raise GateError(
                f"OMARCHY_PLUGIN_GATE_NOTIFY must be one of {', '.join(NOTIFY_POLICIES)}, "
                f"not '{notify}'"
            )
        return cls(
            root=Path(root) if root else home / "Work" / "omarchy-plugins",
            state_root=Path(state) if state else state_home / "omarchy-plugin-gate",
            config_home=config_home,
            agent=_first(env, "OMARCHY_PLUGIN_GATE_AGENT") or "plugin-reviewer",
            model=_first(env, "OMARCHY_PLUGIN_GATE_MODEL"),
            notify_policy=notify,
            review_timeout=_positive_int(
                env, "OMARCHY_PLUGIN_GATE_TIMEOUT", DEFAULT_TIMEOUT, "seconds"
            ),
            max_patch_bytes=_positive_int(
                env, "OMARCHY_PLUGIN_GATE_MAX_PATCH", DEFAULT_MAX_PATCH, "bytes"
            ),
            self_path=self_path,
            user=_current_user(env),
        )
