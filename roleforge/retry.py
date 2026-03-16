"""
Generic retry helper and Telegram/AI error classifiers (TASK-037).

Gmail-specific retry stays in roleforge.gmail_reader.retry. This module provides
a generic with_retry and predicates for Telegram Bot API and AI providers.
See docs/specs/retry-and-fallback-policy.md.
"""

from __future__ import annotations

import time
from typing import Any, Callable, TypeVar

T = TypeVar("T")


def with_retry(
    fn: Callable[[], T],
    *,
    is_transient: Callable[[BaseException], bool],
    is_permanent: Callable[[BaseException], bool],
    max_attempts: int = 3,
    backoff_base_sec: float = 1.0,
) -> T:
    """
    Call fn(); on transient errors retry with exponential backoff.
    If is_permanent(e) raise immediately. Otherwise if is_transient(e) retry.
    """
    last: BaseException | None = None
    for attempt in range(max_attempts):
        try:
            return fn()
        except BaseException as e:
            last = e
            if is_permanent(e):
                raise
            if not is_transient(e):
                raise
            if attempt == max_attempts - 1:
                raise
            time.sleep(backoff_base_sec * (2**attempt))
    if last is not None:
        raise last
    raise RuntimeError("with_retry: no result")


def _http_status(exc: BaseException) -> int | None:
    """Get HTTP status from exception if present."""
    status = getattr(exc, "status_code", None) or getattr(exc, "code", None)
    if status is not None:
        return int(status)
    resp = getattr(exc, "resp", None)
    if resp is not None:
        return getattr(resp, "status", None)
    return None


def is_transient_telegram(exc: BaseException) -> bool:
    """True for Telegram Bot API transient errors (5xx, 429, network)."""
    code = _http_status(exc)
    if code is not None:
        if code in (429, 500, 502, 503):
            return True
        if 400 <= code < 500:
            return False
    name = type(exc).__name__.lower()
    if "timeout" in name or "connection" in name or "network" in name:
        return True
    return False


def is_permanent_telegram(exc: BaseException) -> bool:
    """True for Telegram Bot API permanent errors (401, 403, 400 bad token)."""
    code = _http_status(exc)
    if code is not None and code in (400, 401, 403):
        return True
    msg = str(exc).lower()
    if "unauthorized" in msg or "forbidden" in msg or "blocked" in msg:
        return True
    return False


def is_transient_ai(exc: BaseException) -> bool:
    """True for AI API transient errors (429, 5xx, timeout)."""
    code = _http_status(exc)
    if code is not None and code in (429, 500, 502, 503):
        return True
    name = type(exc).__name__.lower()
    msg = str(exc).lower()
    if "timeout" in name or "rate" in msg or "overloaded" in msg:
        return True
    return False


def is_permanent_ai(exc: BaseException) -> bool:
    """True for AI API permanent errors (401, 403, invalid request)."""
    code = _http_status(exc)
    if code is not None and code in (400, 401, 403):
        return True
    msg = str(exc).lower()
    if "invalid" in msg and ("key" in msg or "api" in msg or "auth" in msg):
        return True
    return False
