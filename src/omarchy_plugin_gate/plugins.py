"""The plugin map: clones under the gate root and their installed copies."""

import json
import os
from pathlib import Path
from typing import Any

from .config import Config
from .output import GateError


def parse_manifest(data: bytes | None) -> dict[str, Any] | None:
    """A manifest object, or None when it is missing, not JSON, or not an object."""
    if data is None:
        return None
    try:
        value = json.loads(data)
    except ValueError:
        return None
    return value if isinstance(value, dict) else None


def read_manifest(path: Path) -> dict[str, Any] | None:
    try:
        return parse_manifest(path.read_bytes())
    except OSError:
        return None


def manifest_id_of(manifest: dict[str, Any] | None) -> str:
    value = manifest.get("id") if manifest else None
    return value if isinstance(value, str) else ""


def plugin_names(cfg: Config) -> list[str]:
    try:
        entries = sorted(cfg.root.iterdir())
    except OSError:
        return []
    return [
        p.name
        for p in entries
        if not p.name.startswith(".") and p.is_dir() and (p / "manifest.json").is_file()
    ]


def clone_dir(cfg: Config, name: str) -> Path:
    return cfg.root / name


def manifest_id(cfg: Config, name: str) -> str:
    return manifest_id_of(read_manifest(clone_dir(cfg, name) / "manifest.json"))


def installed_dir(cfg: Config, name: str) -> Path | None:
    pid = manifest_id(cfg, name)
    return cfg.installed_root / pid if pid else None


def selected_names(cfg: Config, want: str) -> list[str]:
    """All plugins, or the ones whose directory name or manifest id is `want`."""
    names = plugin_names(cfg)
    if not want:
        return names
    found = [n for n in names if want in (n, manifest_id(cfg, n))]
    if not found:
        raise GateError(f"no plugin named '{want}' under {cfg.root}")
    return found


def same_path(a: str | Path, b: str | Path, base: Path | None = None) -> bool:
    """Do two paths name the same file? A relative `a` is taken from `base`."""
    if not a or not b:
        return False
    pa = Path(a)
    if not pa.is_absolute():
        if base is None or "://" in str(a):
            return False
        pa = base / pa
    return os.path.realpath(pa) == os.path.realpath(b)


def plugin_for_dir(cfg: Config, directory: Path) -> str | None:
    """The plugin a clone or installed copy belongs to."""
    names = plugin_names(cfg)
    for name in names:
        if same_path(clone_dir(cfg, name), directory):
            return name
    pid = manifest_id_of(read_manifest(directory / "manifest.json"))
    if not pid:
        return None
    for name in names:
        if manifest_id(cfg, name) == pid:
            return name
    return None
