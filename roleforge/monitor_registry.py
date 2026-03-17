"""
Monitor registry and kill-switch (TASK-085, EPIC-18).

File-driven registry: config/monitors.yaml. No DB table.
Global kill-switch: env MONITOR_INTAKE_ENABLED (default false).
Per-monitor: enabled flag in registry.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from roleforge.runtime import REPO_ROOT


def _default_registry_path() -> Path:
    return REPO_ROOT / "config" / "monitors.yaml"


def is_monitor_intake_enabled() -> bool:
    """True when the global monitor kill-switch is enabled."""
    value = os.environ.get("MONITOR_INTAKE_ENABLED", "").strip().lower()
    return value in ("1", "true", "yes")


def _normalize_monitor_type(value: Any) -> str:
    kind = str(value or "hh_api").strip().lower()
    if kind in ("hh", "headhunter", "hh_api"):
        return "hh_api"
    return kind


def load_registry(path: Path | None = None) -> list[dict[str, Any]]:
    """Load monitor list from YAML and return enabled monitors only."""
    p = path or _default_registry_path()
    if not p.exists():
        return []
    import yaml

    raw = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    monitors = raw.get("monitors") or []
    out: list[dict[str, Any]] = []
    for monitor in monitors:
        if not isinstance(monitor, dict):
            continue
        if not monitor.get("enabled", True):
            continue
        monitor_id = monitor.get("id") or monitor.get("name")
        if not monitor_id:
            continue
        monitor_type = _normalize_monitor_type(monitor.get("type"))
        if monitor_type != "hh_api":
            continue
        params = monitor.get("params") or {}
        if not isinstance(params, dict):
            params = {}
        poll_interval = monitor.get("poll_interval_minutes")
        try:
            poll_interval = int(poll_interval) if poll_interval not in (None, "") else None
        except (TypeError, ValueError):
            poll_interval = None
        out.append(
            {
                "id": str(monitor_id),
                "name": str(monitor.get("name") or monitor_id),
                "type": monitor_type,
                "enabled": True,
                "poll_interval_minutes": poll_interval,
                "params": params,
            }
        )
    return out


def get_enabled_monitors(path: Path | None = None) -> list[dict[str, Any]]:
    """Return enabled monitors only when the global kill-switch is on."""
    if not is_monitor_intake_enabled():
        return []
    return load_registry(path=path)
