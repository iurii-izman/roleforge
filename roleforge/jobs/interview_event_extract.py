"""
Extract interview events from employer reply messages into interview_events (TASK-079).

Deterministic-first: meeting links + best-effort datetime extraction.
Idempotent: one insert per (application_id, gmail_message_id) via notes.source_gmail_message_id.
"""

from __future__ import annotations

import argparse
import json
from typing import Any

from roleforge.interview_event_extraction import extract_interview_event
from roleforge.job_runs import log_job_finish, log_job_start
from roleforge.runtime import connect_db, load_jsonb


JOB_TYPE = "interview_event_extract"


def _subject_from_raw_metadata(raw_metadata: Any) -> str:
    raw = load_jsonb(raw_metadata)
    for h in raw.get("headers") or []:
        if (h.get("name") or "").lower() == "subject":
            return str(h.get("value") or "")
    return ""


def _select_unprocessed_employer_replies(conn: Any, *, limit: int) -> list[dict[str, Any]]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                gm.gmail_message_id,
                gm.raw_metadata,
                gm.body_plain,
                gm.received_at,
                et.application_id
            FROM gmail_messages gm
            JOIN employer_threads et
              ON et.gmail_thread_id = gm.raw_metadata->>'threadId'
            WHERE gm.classified_as = 'employer_reply'
              AND gm.body_plain IS NOT NULL
              AND NOT EXISTS (
                SELECT 1 FROM interview_events ie
                WHERE ie.application_id = et.application_id
                  AND (ie.notes->>'source_gmail_message_id') = gm.gmail_message_id
              )
            ORDER BY gm.received_at ASC NULLS LAST
            LIMIT %s
            """,
            (int(limit),),
        )
        rows = cur.fetchall()
    out: list[dict[str, Any]] = []
    for row in rows:
        out.append(
            {
                "gmail_message_id": row[0],
                "raw_metadata": row[1],
                "body_plain": row[2],
                "received_at": row[3],
                "application_id": row[4],
            }
        )
    return out


def _insert_interview_event(
    conn: Any,
    *,
    application_id: str,
    gmail_message_id: str,
    event_type: str,
    scheduled_at: Any,
    notes: dict[str, Any],
) -> bool:
    notes = dict(notes or {})
    notes["source_gmail_message_id"] = str(gmail_message_id)
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO interview_events (application_id, event_type, scheduled_at, notes)
            VALUES (%s, %s, %s, %s::jsonb)
            """,
            (application_id, event_type, scheduled_at, json.dumps(notes)),
        )
    return True


def run_once(*, limit: int = 200) -> dict[str, Any]:
    conn = connect_db()
    run_id = log_job_start(conn, JOB_TYPE)
    try:
        messages = _select_unprocessed_employer_replies(conn, limit=limit)
        created = 0
        skipped_no_signal = 0
        for msg in messages:
            subject = _subject_from_raw_metadata(msg.get("raw_metadata"))
            candidate = extract_interview_event(subject, msg.get("body_plain") or "")
            if candidate is None:
                skipped_no_signal += 1
                continue
            _insert_interview_event(
                conn,
                application_id=str(msg["application_id"]),
                gmail_message_id=str(msg["gmail_message_id"]),
                event_type=candidate.event_type,
                scheduled_at=candidate.scheduled_at,
                notes=candidate.to_notes(),
            )
            created += 1
        conn.commit()
        summary: dict[str, Any] = {
            "run_id": str(run_id),
            "status": "success",
            "messages_considered": len(messages),
            "events_created": created,
            "messages_skipped_no_signal": skipped_no_signal,
            "limit": int(limit),
        }
        log_job_finish(conn, run_id, "success", summary)
        return summary
    except Exception as exc:
        summary = {"run_id": str(run_id), "status": "failure", "message": str(exc)}
        log_job_finish(conn, run_id, "failure", summary)
        raise
    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Extract interview events from employer replies into interview_events."
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=200,
        help="Max employer-reply messages to scan this run (default: 200).",
    )
    args = parser.parse_args()
    result = run_once(limit=args.limit)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()

