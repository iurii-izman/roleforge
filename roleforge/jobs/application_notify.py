"""
Send low-noise Telegram notifications for application lifecycle updates (TASK-080).

Current scope (deterministic, auditable):
- employer thread linked to an application (first-time per employer_threads row)
- interview event created (first-time per interview_events row)

Idempotency is enforced by checking telegram_deliveries with delivery_type='application_update'
and payload keys ('employer_thread_id' or 'interview_event_id').

Digest-first philosophy: notifications are disabled by default and must be enabled explicitly.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from typing import Any

from roleforge.delivery_log import log_telegram_delivery
from roleforge.job_runs import log_job_finish, log_job_start
from roleforge.runtime import connect_db, get_setting, load_jsonb
from roleforge.telegram import send_message


JOB_TYPE = "application_notify"


def _enabled() -> bool:
    raw = (get_setting("APPLICATION_NOTIFY_ENABLED") or "").strip().lower()
    return raw in ("1", "true", "yes", "on")


def _chat_id() -> str | None:
    return get_setting("TELEGRAM_APPLICATION_CHAT_ID") or get_setting("TELEGRAM_CHAT_ID")


def _format_dt(dt: Any) -> str:
    if not dt:
        return "—"
    if isinstance(dt, datetime):
        aware = dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)
        return aware.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    return str(dt)


def _select_new_employer_thread_links(conn: Any, *, limit: int) -> list[dict[str, Any]]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                et.id,
                et.application_id,
                et.gmail_thread_id,
                et.company_domain,
                et.last_message_at,
                a.status,
                v.company,
                v.title
            FROM employer_threads et
            JOIN applications a ON a.id = et.application_id
            JOIN vacancies v ON v.id = a.vacancy_id
            WHERE NOT EXISTS (
                SELECT 1 FROM telegram_deliveries td
                WHERE td.delivery_type = 'application_update'
                  AND (td.payload->>'employer_thread_id') = et.id::text
            )
            ORDER BY et.created_at ASC
            LIMIT %s
            """,
            (int(limit),),
        )
        rows = cur.fetchall()
    out: list[dict[str, Any]] = []
    for r in rows:
        out.append(
            {
                "employer_thread_id": r[0],
                "application_id": r[1],
                "gmail_thread_id": r[2],
                "company_domain": r[3],
                "last_message_at": r[4],
                "application_status": r[5],
                "company": r[6],
                "title": r[7],
            }
        )
    return out


def _select_new_interview_events(conn: Any, *, limit: int) -> list[dict[str, Any]]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                ie.id,
                ie.application_id,
                ie.event_type,
                ie.scheduled_at,
                ie.notes,
                a.status,
                v.company,
                v.title
            FROM interview_events ie
            JOIN applications a ON a.id = ie.application_id
            JOIN vacancies v ON v.id = a.vacancy_id
            WHERE NOT EXISTS (
                SELECT 1 FROM telegram_deliveries td
                WHERE td.delivery_type = 'application_update'
                  AND (td.payload->>'interview_event_id') = ie.id::text
            )
            ORDER BY ie.created_at ASC
            LIMIT %s
            """,
            (int(limit),),
        )
        rows = cur.fetchall()
    out: list[dict[str, Any]] = []
    for r in rows:
        out.append(
            {
                "interview_event_id": r[0],
                "application_id": r[1],
                "event_type": r[2],
                "scheduled_at": r[3],
                "notes": r[4],
                "application_status": r[5],
                "company": r[6],
                "title": r[7],
            }
        )
    return out


def _format_thread_message(item: dict[str, Any]) -> str:
    company = item.get("company") or "—"
    title = item.get("title") or "—"
    domain = item.get("company_domain") or "—"
    last_ts = _format_dt(item.get("last_message_at"))
    status = item.get("application_status") or "—"
    return "\n".join(
        [
            "RoleForge application update",
            "",
            "Employer reply detected (thread linked).",
            f"{title} @ {company}",
            f"Status: {status}",
            f"From domain: {domain}",
            f"Last message: {last_ts}",
        ]
    )


def _format_interview_event_message(item: dict[str, Any]) -> str:
    company = item.get("company") or "—"
    title = item.get("title") or "—"
    status = item.get("application_status") or "—"
    scheduled = _format_dt(item.get("scheduled_at"))
    notes = load_jsonb(item.get("notes"))
    meeting_link = (notes.get("meeting_link") or "").strip()
    lines = [
        "RoleForge application update",
        "",
        f"Interview event created: {item.get('event_type') or 'other'}",
        f"{title} @ {company}",
        f"Status: {status}",
        f"Scheduled: {scheduled}",
    ]
    if meeting_link:
        lines.append(f"Meeting link: {meeting_link}")
    return "\n".join(lines)


def run_once(*, limit: int = 20, dry_run: bool = False) -> dict[str, Any]:
    conn = connect_db()
    run_id = log_job_start(conn, JOB_TYPE)
    try:
        if not _enabled():
            summary: dict[str, Any] = {
                "run_id": str(run_id),
                "status": "success",
                "enabled": False,
                "updates_sent": 0,
            }
            log_job_finish(conn, run_id, "success", summary)
            return summary

        bot_token = get_setting("TELEGRAM_BOT_TOKEN")
        chat_id = _chat_id()
        if not bot_token:
            raise RuntimeError("Missing TELEGRAM_BOT_TOKEN")
        if not chat_id:
            raise RuntimeError("Missing TELEGRAM_CHAT_ID / TELEGRAM_APPLICATION_CHAT_ID")

        thread_updates = _select_new_employer_thread_links(conn, limit=limit)
        event_updates = _select_new_interview_events(conn, limit=limit)

        sent = 0
        preview: list[str] = []
        for item in thread_updates:
            text = _format_thread_message(item)
            if dry_run:
                preview.append(text)
                continue
            response = send_message(bot_token, chat_id, text)
            log_telegram_delivery(
                conn,
                "application_update",
                {
                    "application_id": str(item["application_id"]),
                    "employer_thread_id": str(item["employer_thread_id"]),
                    "chat_id": chat_id,
                    "text_preview": text[:500],
                    "telegram_response": response,
                },
            )
            sent += 1

        for item in event_updates:
            text = _format_interview_event_message(item)
            if dry_run:
                preview.append(text)
                continue
            response = send_message(bot_token, chat_id, text)
            log_telegram_delivery(
                conn,
                "application_update",
                {
                    "application_id": str(item["application_id"]),
                    "interview_event_id": str(item["interview_event_id"]),
                    "chat_id": chat_id,
                    "text_preview": text[:500],
                    "telegram_response": response,
                },
            )
            sent += 1

        summary = {
            "run_id": str(run_id),
            "status": "success",
            "enabled": True,
            "dry_run": bool(dry_run),
            "threads_eligible": len(thread_updates),
            "interview_events_eligible": len(event_updates),
            "updates_sent": sent if not dry_run else 0,
            "chat_id": chat_id,
        }
        if dry_run and preview:
            summary["preview_count"] = len(preview)
            summary["preview_first"] = preview[0][:1000]
        log_job_finish(conn, run_id, "success", {k: v for k, v in summary.items() if not k.startswith("preview_")})
        return summary
    except Exception as exc:
        summary = {"run_id": str(run_id), "status": "failure", "message": str(exc)}
        log_job_finish(conn, run_id, "failure", summary)
        raise
    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Send low-noise Telegram notifications for application updates (employer reply, interview event)."
    )
    parser.add_argument("--limit", type=int, default=20, help="Max updates per category to process.")
    parser.add_argument("--dry-run", action="store_true", help="Do not send; return preview.")
    args = parser.parse_args()
    result = run_once(limit=args.limit, dry_run=args.dry_run)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()

