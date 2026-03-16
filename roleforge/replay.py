"""
Replay entrypoints: reprocess gmail_messages without Gmail API (TASK-038).

Single message or date window: read from Postgres, run parser → normalize → dedup,
log job_runs. No scoring in this module (caller can run scoring separately).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from roleforge.dedup import group_by_dedup_key, persist_deduped
from roleforge.job_runs import log_job_finish, log_job_start
from roleforge.parser.extractor import extract_candidates


def _subject_from_metadata(raw_metadata: Any) -> str:
    if not raw_metadata or not isinstance(raw_metadata, dict):
        return ""
    headers = raw_metadata.get("headers") or []
    for h in headers:
        if (h.get("name") or "").lower() == "subject":
            return str(h.get("value") or "")
    return ""


def _message_to_candidates(row: dict[str, Any]) -> list[dict[str, Any]]:
    """Build candidates from gmail_messages row; add gmail_message_id and fragment_key."""
    gmid = row.get("gmail_message_id") or ""
    subject = _subject_from_metadata(row.get("raw_metadata"))
    body_plain = row.get("body_plain") or ""
    body_html = row.get("body_html")
    candidates = extract_candidates(body_plain, body_html, subject, gmid)
    for c in candidates:
        c["gmail_message_id"] = gmid
        if "fragment_key" not in c:
            c["fragment_key"] = "0"
        c.setdefault("raw_snippet", (body_plain or "")[:500])
    return candidates


def replay_one_message(conn: Any, gmail_message_id: str) -> dict[str, Any]:
    """
    Replay a single message: fetch from gmail_messages, parse, dedup, persist.

    Returns summary: messages_processed, vacancies_created, run_id (from job_runs).
    """
    run_id = log_job_start(conn, "replay")
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT gmail_message_id, raw_metadata, body_plain, body_html
                FROM gmail_messages WHERE gmail_message_id = %s
                """,
                (gmail_message_id,),
            )
            row = cur.fetchone()
        if not row:
            log_job_finish(conn, run_id, "failure", {"message": "message not found", "gmail_message_id": gmail_message_id})
            return {"messages_processed": 0, "vacancies_created": 0, "run_id": str(run_id), "status": "failure"}
        colnames = ["gmail_message_id", "raw_metadata", "body_plain", "body_html"]
        row_dict = dict(zip(colnames, row))
        candidates = _message_to_candidates(row_dict)
        if not candidates:
            log_job_finish(conn, run_id, "success", {"messages_processed": 1, "vacancies_created": 0})
            return {"messages_processed": 1, "vacancies_created": 0, "run_id": str(run_id)}
        grouped = group_by_dedup_key(candidates)
        vacancy_ids = persist_deduped(conn, grouped)
        log_job_finish(conn, run_id, "success", {"messages_processed": 1, "vacancies_created": len(vacancy_ids)})
        return {"messages_processed": 1, "vacancies_created": len(vacancy_ids), "run_id": str(run_id)}
    except Exception as e:
        log_job_finish(conn, run_id, "failure", {"message": str(e)})
        raise


def replay_date_window(
    conn: Any,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
) -> dict[str, Any]:
    """
    Replay all gmail_messages in the given received_at window (inclusive).

    start_date/end_date: timezone-aware or naive (treated as UTC). None = no bound.
    Returns summary: messages_processed, vacancies_created, run_id.
    """
    run_id = log_job_start(conn, "replay")
    try:
        with conn.cursor() as cur:
            q = """
                SELECT gmail_message_id, raw_metadata, body_plain, body_html
                FROM gmail_messages
                WHERE 1=1
            """
            params: list[Any] = []
            if start_date is not None:
                q += " AND received_at >= %s"
                params.append(start_date if start_date.tzinfo else start_date.replace(tzinfo=timezone.utc))
            if end_date is not None:
                q += " AND received_at <= %s"
                params.append(end_date if end_date.tzinfo else end_date.replace(tzinfo=timezone.utc))
            q += " ORDER BY received_at ASC NULLS LAST"
            cur.execute(q, params)
            rows = cur.fetchall()
        colnames = ["gmail_message_id", "raw_metadata", "body_plain", "body_html"]
        all_candidates: list[dict[str, Any]] = []
        for row in rows:
            row_dict = dict(zip(colnames, row))
            all_candidates.extend(_message_to_candidates(row_dict))
        if not all_candidates:
            log_job_finish(conn, run_id, "success", {"messages_processed": len(rows), "vacancies_created": 0})
            return {"messages_processed": len(rows), "vacancies_created": 0, "run_id": str(run_id)}
        grouped = group_by_dedup_key(all_candidates)
        vacancy_ids = persist_deduped(conn, grouped)
        log_job_finish(conn, run_id, "success", {"messages_processed": len(rows), "vacancies_created": len(vacancy_ids)})
        return {"messages_processed": len(rows), "vacancies_created": len(vacancy_ids), "run_id": str(run_id)}
    except Exception as e:
        log_job_finish(conn, run_id, "failure", {"message": str(e)})
        raise
