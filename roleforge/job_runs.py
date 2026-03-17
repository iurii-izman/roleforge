"""
Job run logging: insert/update job_runs for gmail_poll, digest, queue, replay, feed_poll.

TASK-014 / TASK-036: run logging so operators see success/failure and summary.
TASK-102: structured JSON logs to stdout from start/finish.
"""

from __future__ import annotations

import json
from typing import Any
from uuid import UUID

from roleforge.admin_alert import check_and_alert_consecutive_failures
from roleforge.structured_log import log_job_finish_structured, log_job_start_structured


def log_job_start(conn: Any, job_type: str) -> UUID:
    """
    Insert a running job into job_runs. Returns the run id.

    job_type: 'gmail_poll' | 'digest' | 'queue' | 'replay' | 'feed_poll' | 'alert' | 'batch'
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
        run_id = row[0]
    log_job_start_structured(job_type, str(run_id))
    return run_id


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
    with conn.cursor() as cur:
        cur.execute("SELECT job_type FROM job_runs WHERE id = %s", (run_id,))
        row = cur.fetchone()
    job_type = row[0] if row else "unknown"
    log_job_finish_structured(job_type, str(run_id), status, summary)
    if status == "failure":
        check_and_alert_consecutive_failures(conn, job_type, str(run_id), summary)
