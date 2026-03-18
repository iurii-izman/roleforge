from __future__ import annotations

# mypy: ignore-errors

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from roleforge.runtime import REPO_ROOT


@dataclass(frozen=True)
class RegistryEditResult:
    ok: bool
    message: str


def _feeds_path() -> Path:
    return REPO_ROOT / "config" / "feeds.yaml"


def _monitors_path() -> Path:
    return REPO_ROOT / "config" / "monitors.yaml"


def _read_yaml(path: Path) -> dict[str, Any]:
    import yaml

    if not path.exists():
        return {}
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        return {}
    return raw


def _write_yaml(path: Path, data: dict[str, Any]) -> None:
    import yaml

    text = yaml.safe_dump(data, sort_keys=False, allow_unicode=True)
    path.write_text(text, encoding="utf-8")


def list_feeds() -> list[dict[str, Any]]:
    raw = _read_yaml(_feeds_path())
    feeds = raw.get("feeds") or []
    out: list[dict[str, Any]] = []
    for f in feeds:
        if not isinstance(f, dict):
            continue
        out.append(
            {
                "id": str(f.get("id") or ""),
                "name": str(f.get("name") or f.get("id") or ""),
                "url": str(f.get("url") or ""),
                "type": str(f.get("type") or "rss"),
                "enabled": bool(f.get("enabled", True)),
            }
        )
    return out


def toggle_feed(feed_id: str, *, enabled: bool) -> RegistryEditResult:
    if not feed_id.strip():
        return RegistryEditResult(False, "missing feed_id")
    path = _feeds_path()
    raw = _read_yaml(path)
    feeds = raw.get("feeds")
    if not isinstance(feeds, list):
        feeds = []
    found = False
    for f in feeds:
        if isinstance(f, dict) and str(f.get("id") or "") == feed_id:
            f["enabled"] = bool(enabled)
            found = True
            break
    if not found:
        return RegistryEditResult(False, "feed not found")
    raw["feeds"] = feeds
    _write_yaml(path, raw)
    return RegistryEditResult(True, "ok")


def list_monitors() -> list[dict[str, Any]]:
    raw = _read_yaml(_monitors_path())
    monitors = raw.get("monitors") or []
    out: list[dict[str, Any]] = []
    for m in monitors:
        if not isinstance(m, dict):
            continue
        out.append(
            {
                "id": str(m.get("id") or ""),
                "name": str(m.get("name") or m.get("id") or ""),
                "type": str(m.get("type") or "hh_api"),
                "poll_interval_minutes": m.get("poll_interval_minutes"),
                "enabled": bool(m.get("enabled", True)),
            }
        )
    return out


def toggle_monitor(monitor_id: str, *, enabled: bool) -> RegistryEditResult:
    if not monitor_id.strip():
        return RegistryEditResult(False, "missing monitor_id")
    path = _monitors_path()
    raw = _read_yaml(path)
    monitors = raw.get("monitors")
    if not isinstance(monitors, list):
        monitors = []
    found = False
    for m in monitors:
        if isinstance(m, dict) and str(m.get("id") or "") == monitor_id:
            m["enabled"] = bool(enabled)
            found = True
            break
    if not found:
        return RegistryEditResult(False, "monitor not found")
    raw["monitors"] = monitors
    _write_yaml(path, raw)
    return RegistryEditResult(True, "ok")

