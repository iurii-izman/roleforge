"""
Application state transitions for v5 lifecycle (TASK-078).

State machine aligned with schema/004_application_lifecycle.sql and
docs/specs/v5-application-lifecycle.md. Transitions are explicit and auditable;
invalid jumps are rejected. Intended to be called from Telegram action handlers
(e.g. callback_query or webhook) when the operator confirms a status change.
"""

from __future__ import annotations

from typing import Any

# All statuses from applications.status CHECK constraint
APPLICATION_STATUSES = frozenset({
    "applied",
    "hr_pinged",
    "interview_scheduled",
    "offer",
    "rejected",
    "ghosted",
    "accepted",
    "declined",
})

# Terminal: no transitions out
TERMINAL_STATUSES = frozenset({"rejected", "ghosted", "accepted", "declined"})

# Canonical progression order (non-terminal); used to allow "skip ahead" when operator confirms
_PROGRESSIVE_ORDER = ("applied", "hr_pinged", "interview_scheduled", "offer")


def _progressive_rank(status: str) -> int:
    """Return order index for progressive statuses; terminal statuses are after offer."""
    try:
        return _PROGRESSIVE_ORDER.index(status)
    except ValueError:
        return len(_PROGRESSIVE_ORDER)  # terminal


def is_allowed_transition(from_status: str, to_status: str) -> bool:
    """
    Return True if transitioning from from_status to to_status is allowed.

    Rules (from v5 spec):
    - Terminal statuses (rejected, ghosted, accepted, declined) have no outgoing transitions.
    - accepted and declined are only valid from offer.
    - Otherwise, any non-terminal can move to any later progressive state or to rejected/ghosted.
    """
    if from_status not in APPLICATION_STATUSES or to_status not in APPLICATION_STATUSES:
        return False
    if from_status == to_status:
        return False
    if from_status in TERMINAL_STATUSES:
        return False
    if to_status in ("accepted", "declined"):
        return from_status == "offer"
    if to_status in ("rejected", "ghosted"):
        return True
    # Progressive: allow same or later stage (skip ahead allowed)
    return _progressive_rank(to_status) >= _progressive_rank(from_status)


def get_current_status(conn: Any, application_id: Any) -> str | None:
    """Return current applications.status for the given id, or None if not found."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT status FROM applications WHERE id = %s",
            (application_id,),
        )
        row = cur.fetchone()
    return str(row[0]) if row and row[0] else None


def apply_application_transition(conn: Any, application_id: Any, new_status: str) -> None:
    """
    Transition application to new_status if allowed. Updates applications.updated_at.
    Raises ValueError for unknown status, missing application, or invalid transition.
    """
    if new_status not in APPLICATION_STATUSES:
        raise ValueError(f"Invalid status: {new_status}")
    current = get_current_status(conn, application_id)
    if current is None:
        raise ValueError(f"Application not found: {application_id}")
    if not is_allowed_transition(current, new_status):
        raise ValueError(
            f"Invalid transition: {current!r} -> {new_status!r}"
        )
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE applications
            SET status = %s, updated_at = now()
            WHERE id = %s
            """,
            (new_status, application_id),
        )
    conn.commit()
