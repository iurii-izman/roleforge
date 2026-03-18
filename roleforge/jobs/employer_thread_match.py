"""
Run employer thread matching: link gmail_messages classified as employer_reply to applications (TASK-077).

Selects messages with classified_as = 'employer_reply', resolves thread_id and applications
(via vacancy_observations + applications), creates or updates employer_threads. Logs job_runs
with summary: messages_processed, threads_linked, threads_skipped_already_linked, threads_unmatched.
"""

from __future__ import annotations

import argparse
import json
from typing import Any

from roleforge.employer_thread_matching import run_matching
from roleforge.job_runs import log_job_finish, log_job_start
from roleforge.runtime import connect_db

JOB_TYPE = "employer_thread_match"


def run_once() -> dict[str, Any]:
    """Run employer thread matching once; return summary."""
    conn = connect_db()
    run_id = log_job_start(conn, JOB_TYPE)
    try:
        summary = run_matching(conn)
        summary["run_id"] = str(run_id)
        summary["status"] = "success"
        log_job_finish(conn, run_id, "success", summary)
        return summary
    except Exception as exc:
        out: dict[str, Any] = {
            "run_id": str(run_id),
            "status": "failure",
            "message": str(exc),
        }
        log_job_finish(conn, run_id, "failure", out)
        raise
    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Link employer-reply messages to applications via thread ID (employer_threads)."
    )
    parser.parse_args()
    result = run_once()
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
