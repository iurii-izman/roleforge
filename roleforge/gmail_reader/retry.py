"""
Retry policy for Gmail API calls: transient errors retry with backoff; permanent fail fast.

TASK-014: policy and code hooks. See docs/specs/gmail-retry-policy.md.
"""

from __future__ import annotations

import time
from typing import Any, Callable, TypeVar

T = TypeVar("T")

# Gmail/Google API often use googleapiclient.errors.HttpError with .resp.status
# and generic Exception for connection/transport errors.
TRANSIENT_HTTP_CODES = (429, 500, 502, 503)
PERMANENT_HTTP_CODES = (400, 401, 403, 404)


def is_transient_error(exc: BaseException) -> bool:
    """True if the error is transient (rate limit, 5xx, connection)."""
    status = getattr(exc, "resp", None)
    if status is not None:
        code = getattr(status, "status", None)
        if code is not None and int(code) in TRANSIENT_HTTP_CODES:
            return True
    # Connection errors, timeouts, etc.
    name = type(exc).__name__.lower()
    if "timeout" in name or "connection" in name or "network" in name:
        return True
    return False


def is_permanent_auth_error(exc: BaseException) -> bool:
    """True if the error is permanent auth (401, 403, invalid_grant)."""
    status = getattr(exc, "resp", None)
    if status is not None:
        code = getattr(status, "status", None)
        if code is not None and int(code) in (401, 403):
            return True
    msg = str(exc).lower()
    if "invalid_grant" in msg or "invalid_credentials" in msg or "token" in msg and "revoked" in msg:
        return True
    return False


def with_retry(
    fn: Callable[[], T],
    max_attempts: int = 3,
    backoff_base_sec: float = 1.0,
) -> T:
    """
    Call fn(); on transient errors retry with exponential backoff.
    On permanent auth errors do not retry; raise immediately.
    """
    last: BaseException | None = None
    for attempt in range(max_attempts):
        try:
            return fn()
        except BaseException as e:
            last = e
            if is_permanent_auth_error(e):
                raise
            if not is_transient_error(e):
                raise
            if attempt == max_attempts - 1:
                raise
            time.sleep(backoff_base_sec * (2**attempt))
    if last is not None:
        raise last
    raise RuntimeError("with_retry: no result")
