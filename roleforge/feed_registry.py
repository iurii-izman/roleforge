"""
Feed registry and kill-switch (TASK-046, EPIC-11).

File-driven registry: config/feeds.yaml. No DB table.
Global kill-switch: env FEED_INTAKE_ENABLED (default false).
Per-feed: enabled flag in registry.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from roleforge.runtime import REPO_ROOT


def _default_registry_path() -> Path:
    return REPO_ROOT / "config" / "feeds.yaml"


def is_feed_intake_enabled() -> bool:
    """
    Global kill-switch. When false, feed_poll job should no-op.
    Env FEED_INTAKE_ENABLED: true/1/yes => enabled; anything else => disabled.
    """
    v = os.environ.get("FEED_INTAKE_ENABLED", "").strip().lower()
    return v in ("1", "true", "yes")


def load_registry(path: Path | None = None) -> list[dict[str, Any]]:
    """
    Load feed list from YAML. Returns only enabled feeds with id, name, url, type.

    path: defaults to config/feeds.yaml under repo root.
    Each entry: id (str), name (str), url (str), type (rss|atom), enabled (bool).
    """
    p = path or _default_registry_path()
    if not p.exists():
        return []
    import yaml

    raw = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    feeds = raw.get("feeds") or []
    out: list[dict[str, Any]] = []
    for f in feeds:
        if not isinstance(f, dict):
            continue
        if not f.get("enabled", True):
            continue
        fid = f.get("id") or f.get("url", "")
        if not fid:
            continue
        url = f.get("url", "").strip()
        if not url:
            continue
        t = (f.get("type") or "rss").strip().lower()
        if t not in ("atom", "rss"):
            t = "rss"
        out.append({
            "id": str(fid),
            "name": str(f.get("name") or fid),
            "url": url,
            "type": t,
        })
    return out


def get_enabled_feeds(path: Path | None = None) -> list[dict[str, Any]]:
    """
    If global kill-switch is off, return []. Otherwise return enabled feeds from registry.
    """
    if not is_feed_intake_enabled():
        return []
    return load_registry(path=path)
