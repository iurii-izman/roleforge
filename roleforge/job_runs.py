"""
Job run logging: insert/update job_runs for gmail_poll, digest, queue, replay, feed_poll.

TASK-014 / TASK-036: run logging so operators see success/failure and summary.
"""

from __future__ import annotations

import json
from typing import Any
from uuid import UUID


def log_job_start(conn: Any, job_type: str) -> UUID:
    """
    Insert a running job into job_runs. Returns the run id.

    job_type: 'gmail_poll' | 'digest' | 'queue' | 'replay' | 'feed_poll'
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO job_runs (job_type, status)
            VALUES (%s, 'running')
            RETURNING id
            """,
            (job_type,),
        )
        row = cur.fetchone()
        conn.commit()
        return row[0]


def log_job_finish(
    conn: Any,
    run_id: UUID,
    status: str,
    summary: dict[str, Any] | None = None,
) -> None:
    """
    Mark a job run as finished (success or failure).

    status: 'success' | 'failure'
    summary: optional JSON-serializable dict (e.g. messages_seen, error_type, message).
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE job_runs
            SET finished_at = now(), status = %s, summary = %s::jsonb
            WHERE id = %s
            """,
            (status, json.dumps(summary or {}), run_id),
        )
        conn.commit()
