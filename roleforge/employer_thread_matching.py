"""
Employer thread matching: link gmail_messages classified as employer_reply to applications (TASK-077).

For each message with classified_as = 'employer_reply', finds the Gmail thread_id, then
resolves applications whose vacancy was observed from a message in that thread (via
vacancy_observations). Creates or updates employer_threads rows so that one thread is
linked to one application (earliest applied_at when multiple applications match).
Idempotent: threads already present in employer_threads are skipped or updated (last_message_at).
"""

from __future__ import annotations

import json
import re
from typing import Any

# Extract From/Reply-To domain from raw_metadata headers (no dependency on inbox_classifier)
def _from_domain_from_metadata(raw_metadata: Any) -> str:
    if not raw_metadata or not isinstance(raw_metadata, dict):
        return ""
    value = ""
    for h in raw_metadata.get("headers") or []:
        name = (h.get("name") or "").lower()
        if name in ("from", "reply-to"):
            value = str(h.get("value") or "")
            if name == "from":
                break
    if not value:
        return ""
    match = re.search(r"<?([a-zA-Z0-9_.+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})>?", value)
    if not match:
        return ""
    addr = match.group(1)
    try:
        return addr.split("@", 1)[1].lower()
    except IndexError:
        return ""


def _thread_id_from_message(message_row: dict[str, Any]) -> str | None:
    raw = message_row.get("raw_metadata") or {}
    if isinstance(raw, str):
        import json
        try:
            raw = json.loads(raw) if raw else {}
        except (json.JSONDecodeError, TypeError):
            raw = {}
    tid = (raw.get("threadId") or "").strip()
    return tid or None


def _application_id_for_thread(conn: Any, gmail_thread_id: str) -> str | None:
    """
    Return one application_id to link to this thread, or None.

    Finds vacancy_ids observed from any message in this thread (vacancy_observations
    join gmail_messages on threadId). Then selects one application for those vacancies:
    the one with earliest applied_at (deterministic; employer_threads has UNIQUE(gmail_thread_id)).
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT DISTINCT a.id
            FROM applications a
            JOIN vacancy_observations vo ON vo.vacancy_id = a.vacancy_id AND vo.gmail_message_id IS NOT NULL
            JOIN gmail_messages gm ON gm.gmail_message_id = vo.gmail_message_id
               AND gm.raw_metadata->>'threadId' = %s
            ORDER BY a.applied_at ASC
            LIMIT 1
            """,
            (gmail_thread_id.strip(),),
        )
        row = cur.fetchone()
        return str(row[0]) if row and row[0] else None


def _thread_already_linked(conn: Any, gmail_thread_id: str) -> bool:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT 1 FROM employer_threads WHERE gmail_thread_id = %s",
            (gmail_thread_id.strip(),),
        )
        return cur.fetchone() is not None


def ensure_employer_thread_for_message(
    conn: Any,
    message_row: dict[str, Any],
    *,
    received_at: Any = None,
) -> str | None:
    """
    If the message is employer_reply and has a thread_id, ensure employer_threads has a row.

    message_row: dict with gmail_message_id, raw_metadata (threadId, headers), and optionally received_at.
    received_at: optional override for last_message_at (e.g. from DB received_at).

    Returns the gmail_thread_id if a row was created or updated, else None (skipped or no thread/application).
    """
    thread_id = _thread_id_from_message(message_row)
    if not thread_id:
        return None

    application_id = _application_id_for_thread(conn, thread_id)
    if not application_id:
        return None

    raw = message_row.get("raw_metadata") or {}
    if isinstance(raw, str):
        import json
        try:
            raw = json.loads(raw) if raw else {}
        except (json.JSONDecodeError, TypeError):
            raw = {}
    company_domain = _from_domain_from_metadata(raw)
    last_ts = received_at or message_row.get("received_at")
    classification = {
        "source": "employer_reply_message",
        "gmail_message_id": message_row.get("gmail_message_id"),
    }

    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO employer_threads (
                application_id, gmail_thread_id, company_domain, last_message_at, classification
            )
            VALUES (%s, %s, %s, %s, %s::jsonb)
            ON CONFLICT (gmail_thread_id) DO UPDATE SET
                last_message_at = COALESCE(
                    GREATEST(employer_threads.last_message_at, EXCLUDED.last_message_at),
                    EXCLUDED.last_message_at,
                    employer_threads.last_message_at
                ),
                company_domain = COALESCE(employer_threads.company_domain, EXCLUDED.company_domain)
            """,
            (application_id, thread_id, company_domain or None, last_ts, json.dumps(classification)),
        )
    conn.commit()
    return thread_id


def run_matching(conn: Any) -> dict[str, Any]:
    """
    Process all gmail_messages with classified_as = 'employer_reply': link threads to applications.

    Returns summary: messages_processed, threads_linked (new or updated), threads_skipped (already linked),
    threads_unmatched (no application for thread).
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT gmail_message_id, raw_metadata, received_at
            FROM gmail_messages
            WHERE classified_as = 'employer_reply'
            ORDER BY received_at ASC NULLS LAST
            """
        )
        rows = cur.fetchall()
    colnames = ["gmail_message_id", "raw_metadata", "received_at"]
    messages = [dict(zip(colnames, row)) for row in rows]

    linked: set[str] = set()
    skipped: set[str] = set()
    unmatched: set[str] = set()

    for msg in messages:
        thread_id = _thread_id_from_message(msg)
        if not thread_id:
            continue
        if _thread_already_linked(conn, thread_id):
            skipped.add(thread_id)
            # Refresh last_message_at when this employer_reply is newer
            received_at = msg.get("received_at")
            if received_at is not None:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        UPDATE employer_threads
                        SET last_message_at = %s
                        WHERE gmail_thread_id = %s
                          AND (last_message_at IS NULL OR last_message_at < %s)
                        """,
                        (received_at, thread_id, received_at),
                    )
                conn.commit()
            continue
        app_id = _application_id_for_thread(conn, thread_id)
        if not app_id:
            unmatched.add(thread_id)
            continue
        ensure_employer_thread_for_message(conn, msg, received_at=msg.get("received_at"))
        linked.add(thread_id)

    return {
        "messages_processed": len(messages),
        "threads_linked": len(linked),
        "threads_skipped_already_linked": len(skipped),
        "threads_unmatched": len(unmatched),
    }
