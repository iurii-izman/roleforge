"""
Run one Gmail polling cycle and persist new raw messages.
"""

from __future__ import annotations

import argparse
import json

from roleforge.gmail_reader import GmailReader, persist_messages
from roleforge.job_runs import log_job_finish, log_job_start
from roleforge.runtime import build_gmail_service, connect_db, get_setting


def run_once(*, label_name_or_id: str | None = None, max_per_page: int = 500) -> dict[str, int | str]:
    conn = connect_db()
    run_id = log_job_start(conn, "gmail_poll")
    try:
        reader = GmailReader(build_gmail_service())
        label_name_or_id = label_name_or_id or get_setting("GMAIL_INTAKE_LABEL")
        if not label_name_or_id:
            raise RuntimeError("Missing GMAIL_INTAKE_LABEL")
        label_id = reader.resolve_label_id(label_name_or_id) or label_name_or_id
        with conn.cursor() as cur:
            cur.execute("SELECT gmail_message_id FROM gmail_messages")
            seen_ids = {row[0] for row in cur.fetchall()}
        new_ids = reader.get_new_message_ids(label_id, seen_ids=seen_ids, max_per_page=max_per_page)
        messages = reader.fetch_messages(new_ids) if new_ids else []
        inserted = persist_messages(conn, messages) if messages else 0
        summary = {
            "run_id": str(run_id),
            "status": "success",
            "label": label_name_or_id,
            "label_id": label_id,
            "messages_fetched": len(messages),
            "messages_stored": inserted,
            "messages_skipped": max(0, len(new_ids) - inserted),
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
    parser = argparse.ArgumentParser(description="Run one Gmail poll and persist new messages.")
    parser.add_argument("--label", help="Gmail label name or ID. Falls back to GMAIL_INTAKE_LABEL.")
    parser.add_argument("--max-per-page", type=int, default=500)
    args = parser.parse_args()
    result = run_once(label_name_or_id=args.label, max_per_page=args.max_per_page)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
