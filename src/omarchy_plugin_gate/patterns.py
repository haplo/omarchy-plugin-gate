"""Pattern matches for the structural checks. Findings, never verdicts."""

import posixpath
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

# What each asset type's contents start with. A file with an asset suffix and
# other contents is not the image or font its name claims.
ASSET_MAGIC: dict[str, re.Pattern[bytes]] = {
    ".png": re.compile(rb"\x89PNG\r\n\x1a\n"),
    ".jpg": re.compile(rb"\xff\xd8\xff"),
    ".jpeg": re.compile(rb"\xff\xd8\xff"),
    ".gif": re.compile(rb"GIF8[79]a"),
    ".webp": re.compile(rb"RIFF.{4}WEBP", re.DOTALL),
    ".ico": re.compile(rb"\x00\x00\x01\x00"),
    ".avif": re.compile(rb".{4}ftypavi[fs]", re.DOTALL),
    ".bmp": re.compile(rb"BM"),
    ".woff": re.compile(rb"wOFF"),
    ".woff2": re.compile(rb"wOF2"),
    ".ttf": re.compile(rb"\x00\x01\x00\x00|true|OTTO"),
}
ASSET_SUFFIXES = tuple(ASSET_MAGIC)

# Files something loads or runs as code or configuration. Binary to git, such a
# file reaches the reviewer as "Binary files differ" and nothing else.
CODE_SUFFIXES = (
    ".qml",
    ".js",
    ".mjs",
    ".cjs",
    ".ts",
    ".sh",
    ".bash",
    ".zsh",
    ".fish",
    ".py",
    ".pl",
    ".rb",
    ".lua",
    ".json",
    ".toml",
    ".ini",
    ".conf",
    ".desktop",
    ".service",
    ".timer",
    ".socket",
    ".path",
)
CODE_NAMES = ("qmldir",)

# Native code Qt or a runtime can load (a qmldir `plugin` line, for one).
NATIVE_SUFFIX = re.compile(r"\.(so(\.[0-9]+)*|node|dll|dylib)$", re.IGNORECASE)


def is_denied(path: str) -> bool:
    return DENY_PATH.search(path) is not None


def is_known_asset(path: str) -> bool:
    return path.lower().endswith(ASSET_SUFFIXES)


def asset_matches(path: str, head: bytes) -> bool:
    """Whether the start of an asset file is what its suffix says it is."""
    magic = ASSET_MAGIC.get(posixpath.splitext(path.lower())[1])
    return magic is not None and magic.match(head) is not None


def is_code_path(path: str) -> bool:
    lower = path.lower()
    return lower.endswith(CODE_SUFFIXES) or posixpath.basename(lower) in CODE_NAMES


def is_native_path(path: str) -> bool:
    return NATIVE_SUFFIX.search(path) is not None


def escapes_plugin(entry_point: str) -> bool:
    return entry_point.startswith("/") or re.search(r"(^|/)\.\.(/|$)", entry_point) is not None
