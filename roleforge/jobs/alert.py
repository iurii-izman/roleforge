"""
Send near-real-time Telegram alerts for high-score profile matches (TASK-057).

Only matches that pass profile.config.delivery_mode (alert_enabled=true,
score >= immediate_threshold) and have not already been sent as an alert
are considered. Each send is logged to telegram_deliveries with delivery_type='alert'.
"""

from __future__ import annotations

import argparse
import json
from typing import Any

from roleforge.delivery_log import log_telegram_delivery
from roleforge.job_runs import log_job_finish, log_job_start
from roleforge.runtime import connect_db, get_setting
from roleforge.telegram import send_message


def _format_alert_message(
    vacancy: dict[str, Any],
    match_score: float | None,
    profile_name: str,
    *,
    max_title_len: int = 60,
    max_company_len: int = 30,
) -> str:
    """Format one alert line: title, company, score, profile, link."""
    title = (vacancy.get("title") or "—")[:max_title_len]
    company = (vacancy.get("company") or "—")[:max_company_len]
    score_s = f" Score: {match_score:.2f}" if match_score is not None else ""
    url = vacancy.get("canonical_url") or vacancy.get("url") or ""
    lines = [
        "RoleForge alert",
        "",
        title,
        f"at {company}{score_s}",
        f"Profile: {profile_name}",
    ]
    if url:
        lines.append(url)
    return "\n".join(lines)


def _get_eligible_alert_matches(conn: Any) -> list[dict[str, Any]]:
    """
    Return profile_matches that are eligible for an immediate alert:
    - profile has delivery_mode.alert_enabled = true
    - score >= delivery_mode.immediate_threshold (default 0.80)
    - no existing telegram_deliveries row with delivery_type='alert' for this profile_match_id
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                pm.id AS profile_match_id,
                pm.profile_id,
                pm.vacancy_id,
                pm.score,
                p.name AS profile_name,
                v.id AS v_id,
                v.canonical_url,
                v.company,
                v.title,
                v.location
            FROM profile_matches pm
            JOIN profiles p ON p.id = pm.profile_id
            JOIN vacancies v ON v.id = pm.vacancy_id
            WHERE (p.config->'delivery_mode'->>'alert_enabled')::text = 'true'
              AND pm.score >= COALESCE(
                  (p.config->'delivery_mode'->>'immediate_threshold')::numeric,
                  0.80
              )
              AND NOT EXISTS (
                  SELECT 1 FROM telegram_deliveries td
                  WHERE td.delivery_type = 'alert'
                    AND td.payload->>'profile_match_id' = pm.id::text
              )
            ORDER BY pm.created_at ASC
            """
        )
        rows = cur.fetchall()
    result = []
    for row in rows:
        result.append({
            "profile_match_id": row[0],
            "profile_id": row[1],
            "vacancy_id": row[2],
            "score": float(row[3]) if row[3] is not None else None,
            "profile_name": row[4],
            "vacancy": {
                "id": row[5],
                "canonical_url": row[6],
                "company": row[7],
                "title": row[8],
                "location": row[9],
            },
        })
    return result


def run_once(*, dry_run: bool = False, chat_id: str | None = None) -> dict[str, Any]:
    """
    Run the alert job once: find eligible matches, send one Telegram message per match,
    log each to telegram_deliveries, and write job_runs summary.
    """
    conn = connect_db()
    run_id = log_job_start(conn, "alert")
    try:
        candidates = _get_eligible_alert_matches(conn)
        summary: dict[str, Any] = {
            "run_id": str(run_id),
            "status": "success",
            "eligible_count": len(candidates),
            "alerts_sent": 0,
        }
        if dry_run:
            summary["dry_run"] = True
            if candidates:
                summary["preview_count"] = len(candidates)
                # One preview line per candidate (first one expanded)
                first = candidates[0]
                summary["preview"] = _format_alert_message(
                    first["vacancy"],
                    first["score"],
                    first["profile_name"],
                )
            log_job_finish(conn, run_id, "success", {k: v for k, v in summary.items() if k != "preview"})
            return summary

        if not candidates:
            log_job_finish(conn, run_id, "success", summary)
            return summary

        bot_token = get_setting("TELEGRAM_BOT_TOKEN")
        chat_id = chat_id or get_setting("TELEGRAM_CHAT_ID")
        if not bot_token:
            raise RuntimeError("Missing TELEGRAM_BOT_TOKEN")
        if not chat_id:
            raise RuntimeError("Missing TELEGRAM_CHAT_ID")

        sent = 0
        for item in candidates:
            text = _format_alert_message(
                item["vacancy"],
                item["score"],
                item["profile_name"],
            )
            response = send_message(bot_token, chat_id, text)
            log_telegram_delivery(
                conn,
                "alert",
                {
                    "profile_match_id": str(item["profile_match_id"]),
                    "profile_id": str(item["profile_id"]),
                    "vacancy_id": str(item["vacancy_id"]),
                    "chat_id": chat_id,
                    "text_preview": text[:500],
                    "telegram_response": response,
                },
            )
            sent += 1
        summary["alerts_sent"] = sent
        summary["chat_id"] = chat_id
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
        description="Send Telegram alerts for high-score matches (alert_enabled + score >= immediate_threshold)."
    )
    parser.add_argument("--dry-run", action="store_true", help="List eligible matches and preview first message without sending.")
    parser.add_argument("--chat-id", help="Override TELEGRAM_CHAT_ID for this run.")
    args = parser.parse_args()
    result = run_once(dry_run=args.dry_run, chat_id=args.chat_id)
    if "preview" in result:
        print(result["preview"])
        print()
    print(json.dumps({k: v for k, v in result.items() if k != "preview"}, indent=2))


if __name__ == "__main__":
    main()
