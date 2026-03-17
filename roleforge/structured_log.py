"""
JSON-structured logging to stdout for job runs (TASK-102).

One JSON object per line; no new dependencies. Safe to call from log_job_start
and log_job_finish so all jobs get structured logs without per-job changes.
Secrets must not appear in message or extra fields.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from typing import Any


def _sanitize_summary(summary: dict[str, Any] | None) -> dict[str, Any]:
    """Return a copy safe for logs: no tokens, URLs with credentials, or raw secrets."""
    if not summary:
        return {}
    out: dict[str, Any] = {}
    skip_keys = {"telegram_response", "preview", "text_preview"}
    for k, v in summary.items():
        if k in skip_keys:
            continue
        if isinstance(v, str) and any(x in k.lower() for x in ("token", "secret", "password", "key")):
            continue
        out[k] = v
    return out


def log_struct(level: str, event: str, message: str = "", **extra: Any) -> None:
    """
    Write one JSON line to stdout.

    level: 'info' | 'warning' | 'error'
    event: e.g. 'job_start', 'job_finish'
    message: short human-readable message
    extra: additional keys (must be JSON-serializable; no secrets).
    """
    payload: dict[str, Any] = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "level": level,
        "event": event,
        "message": message,
    }
    for k, v in extra.items():
        if v is not None:
            payload[k] = v
    try:
        line = json.dumps(payload, default=str) + "\n"
        sys.stdout.write(line)
        sys.stdout.flush()
    except (TypeError, ValueError):
        payload["message"] = message + " [log serialization error]"
        sys.stdout.write(json.dumps(payload, default=str) + "\n")
        sys.stdout.flush()


def log_job_start_structured(job_type: str, run_id: str) -> None:
    """Emit a structured log line for job start."""
    log_struct("info", "job_start", f"job started: {job_type}", job_type=job_type, run_id=run_id)


def log_job_finish_structured(
    job_type: str,
    run_id: str,
    status: str,
    summary: dict[str, Any] | None = None,
) -> None:
    """Emit a structured log line for job finish. Summary is sanitized."""
    msg = f"job finished: {job_type} status={status}"
    safe = _sanitize_summary(summary)
    log_struct("info" if status == "success" else "error", "job_finish", msg, job_type=job_type, run_id=run_id, status=status, summary=safe)
