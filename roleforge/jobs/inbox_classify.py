"""
Run inbox classifier on stored unclassified messages and set gmail_messages.classified_as (TASK-076).

Selects rows with classified_as IS NULL, calls roleforge.inbox_classifier.classify_message
for each, and updates classified_as when the result is non-null. Uses intake label IDs from
config/env for Rule 2 (intake label + single-message thread). Logs job_runs; ai_cost_usd
can be added to summary when AI fallback is implemented (TASK-074).
"""

from __future__ import annotations

import argparse
import json
from typing import Any

from roleforge.inbox_classifier import classify_message
from roleforge.job_runs import log_job_finish, log_job_start
from roleforge.runtime import build_gmail_service, connect_db, get_setting

try:
    from roleforge.gmail_reader import GmailReader
except ImportError:
    GmailReader = None  # type: ignore[misc, assignment]


JOB_TYPE = "inbox_classify"


def _resolve_intake_label_ids(intake_label_ids_override: list[str] | None = None) -> list[str]:
    """
    Resolve intake label IDs for the classifier (Rule 2).

    Precedence:
    1. intake_label_ids_override if provided (e.g. from CLI or tests).
    2. GMAIL_INTAKE_LABEL_IDS env (comma-separated) if set.
    3. GMAIL_INTAKE_LABEL: resolve via Gmail API if available, else use value as single ID.

    Returns list of label IDs (may be empty if no config).
    """
    if intake_label_ids_override is not None:
        return [x.strip() for x in intake_label_ids_override if x and x.strip()]

    ids_env = get_setting("GMAIL_INTAKE_LABEL_IDS")
    if ids_env:
        return [x.strip() for x in ids_env.split(",") if x.strip()]

    label_name_or_id = get_setting("GMAIL_INTAKE_LABEL")
    if not label_name_or_id or not label_name_or_id.strip():
        return []

    # Try to resolve name -> ID via Gmail API; on failure use as-is (deployment can set raw ID).
    if GmailReader is not None:
        try:
            service = build_gmail_service()
            reader = GmailReader(service)
            resolved = reader.resolve_label_id(label_name_or_id.strip())
            if resolved:
                return [resolved]
        except Exception:
            pass
    return [label_name_or_id.strip()]


def run_once(
    *,
    intake_label_ids: list[str] | None = None,
) -> dict[str, Any]:
    """
    Run the inbox classification job once: select unclassified messages,
    classify each, update classified_as where result is non-null.
    """
    conn = connect_db()
    run_id = log_job_start(conn, JOB_TYPE)
    try:
        resolved_ids = _resolve_intake_label_ids(intake_label_ids)
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT gmail_message_id, raw_metadata, body_plain
                FROM gmail_messages
                WHERE classified_as IS NULL
                """
            )
            rows = cur.fetchall()
        colnames = ["gmail_message_id", "raw_metadata", "body_plain"]
        updated = 0
        for row in rows:
            message_row = dict(zip(colnames, row))
            result = classify_message(message_row, conn, resolved_ids)
            if result.get("classified_as") is not None:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        UPDATE gmail_messages
                        SET classified_as = %s
                        WHERE gmail_message_id = %s AND classified_as IS NULL
                        """,
                        (result["classified_as"], message_row["gmail_message_id"]),
                    )
                    if cur.rowcount:
                        updated += 1
        conn.commit()
        summary: dict[str, Any] = {
            "run_id": str(run_id),
            "status": "success",
            "messages_processed": len(rows),
            "classified_count": updated,
            "intake_label_ids_count": len(resolved_ids),
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
        description="Classify stored Gmail messages (classified_as IS NULL) using deterministic inbox classifier."
    )
    parser.add_argument(
        "--intake-label-ids",
        help="Comma-separated Gmail label IDs for intake (overrides GMAIL_INTAKE_LABEL_IDS / GMAIL_INTAKE_LABEL).",
    )
    args = parser.parse_args()
    label_ids = None
    if args.intake_label_ids:
        label_ids = [x.strip() for x in args.intake_label_ids.split(",") if x.strip()]
    result = run_once(intake_label_ids=label_ids)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
