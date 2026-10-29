"""Pattern matches for the structural checks. Findings, never verdicts."""

import re

# Paths a plugin has no business touching. Checked on every changed file, and on
# every file that gains the executable bit.
DENY_PATH = re.compile(
    r"(^|/)\.git/|(^|/)\.ssh/|(^|/)authorized_keys$|(^|/)sudoers$"
    r"|\.service$|\.timer$|\.socket$|\.path$|\.desktop$|\.pem$|\.key$|\.p12$"
    r"|(^|/)systemd/|(^|/)omarchy/hooks"
)

# Added lines that look like download-and-execute, encoded payloads piped into a
# shell, reverse shells, or privilege escalation via a pipe.
DANGER_LINE = re.compile(
    r"(curl|wget)[^|]*\|\s*(ba|z|da|k)?sh(\s|$)"
    r"|base64\s+(-d|--decode)[^|]*\|"
    r"|(nc|ncat)\s.*-[a-z]*e\s"
    r"|/dev/tcp/"
    r"|\|\s*(sudo|pkexec)\s",
    re.IGNORECASE,
)

# Exactly what the reviewer is good at; collected as hints, never auto-failed,
# because plenty of legitimate plugin code uses these.
HINT_RE = re.compile(
    r"curl|wget|eval|new Function|Function\(|subprocess|os\.system|os\.popen|child_process"
    r"|XMLHttpRequest|fetch\(|WebSocket|socket|base64|pkexec|sudo|systemctl|chmod|rm -rf"
    r"|/etc/|api[_ -]?key|token|secret|password|\.env\b|ssh|gpg|keyring"
)

ASSET_SUFFIXES = (
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
    ".ico",
    ".avif",
    ".bmp",
    ".woff",
    ".woff2",
    ".ttf",
)


def is_denied(path: str) -> bool:
    return DENY_PATH.search(path) is not None


def is_known_asset(path: str) -> bool:
    return path.lower().endswith(ASSET_SUFFIXES)


def escapes_plugin(entry_point: str) -> bool:
    return entry_point.startswith("/") or re.search(r"(^|/)\.\.(/|$)", entry_point) is not None
