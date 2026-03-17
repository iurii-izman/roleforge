"""
Consecutive-failure admin alert (TASK-103).

When a job type has exactly 3 consecutive failures, send one Telegram message
to the admin chat. No alert for 1–2 failures; one alert per streak when count hits 3.
"""

from __future__ import annotations

from typing import Any

from roleforge.delivery_log import log_telegram_delivery
from roleforge.telegram import send_message


CONSECUTIVE_THRESHOLD = 3


def _count_consecutive_failures(conn: Any, job_type: str) -> int:
    """Return number of most recent runs that are failures (from newest backwards)."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT status FROM job_runs
            WHERE job_type = %s AND finished_at IS NOT NULL
            ORDER BY started_at DESC
            LIMIT 20
            """,
            (job_type,),
        )
        rows = cur.fetchall()
    count = 0
    for (status,) in rows:
        if status != "failure":
            break
        count += 1
    return count


def check_and_alert_consecutive_failures(
    conn: Any,
    job_type: str,
    run_id: str,
    summary: dict[str, Any] | None = None,
) -> None:
    """
    If this job_type has exactly CONSECUTIVE_THRESHOLD consecutive failures,
    send one Telegram message to TELEGRAM_ADMIN_CHAT_ID and log to telegram_deliveries.

    Call after log_job_finish(..., 'failure', ...). If admin chat or bot token
    is not configured, no-op.
    """
    count = _count_consecutive_failures(conn, job_type)
    if count != CONSECUTIVE_THRESHOLD:
        return

    from roleforge.runtime import get_setting

    bot_token = get_setting("TELEGRAM_BOT_TOKEN")
    admin_chat_id = get_setting("TELEGRAM_ADMIN_CHAT_ID")
    if not bot_token or not admin_chat_id:
        return

    message = summary.get("message", "no message") if summary else "no message"
    text = (
        f"RoleForge admin alert: {job_type} has {count} consecutive failures.\n"
        f"run_id={run_id}\n"
        f"message={message[:500]}"
    )
    try:
        response = send_message(bot_token, admin_chat_id, text)
        log_telegram_delivery(
            conn,
            "admin_alert",
            {
                "job_type": job_type,
                "run_id": run_id,
                "consecutive_failures": count,
                "message_preview": message[:200],
                "telegram_response": response,
            },
        )
    except Exception:
        pass  # Do not raise; job already failed, alert is best-effort
