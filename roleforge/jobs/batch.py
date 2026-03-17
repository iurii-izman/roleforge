"""
Micro-batch delivery job: send mid-band matches on a short cadence (TASK-059).

Only matches that pass profile.config.delivery_mode (batch_enabled=true,
batch_threshold <= score < immediate_threshold) and have not already been sent
as a batch are considered. One Telegram message per profile with eligible
matches; each send is logged to telegram_deliveries with delivery_type='batch'.
"""

from __future__ import annotations

import argparse
import json
from typing import Any

from roleforge.delivery_log import log_telegram_delivery
from roleforge.job_runs import log_job_finish, log_job_start
from roleforge.runtime import connect_db, get_setting
from roleforge.telegram import send_message

# Max items per batch message to keep size bounded (Telegram limit 4096).
MAX_ITEMS_PER_BATCH_MESSAGE = 15


def _format_batch_line(
    vacancy: dict[str, Any],
    match_score: float | None,
    *,
    max_title_len: int = 50,
    max_company_len: int = 25,
) -> str:
    """Format one batch line: title, company, score, link."""
    title = (vacancy.get("title") or "—")[:max_title_len]
    company = (vacancy.get("company") or "—")[:max_company_len]
    score_s = f" {match_score:.2f}" if match_score is not None else ""
    url = vacancy.get("canonical_url") or vacancy.get("url") or ""
    line = f"• {title} at {company}{score_s}"
    if url:
        line += f"\n  {url}"
    return line


def _format_batch_message(
    profile_name: str,
    items: list[dict[str, Any]],
    *,
    max_items: int = MAX_ITEMS_PER_BATCH_MESSAGE,
) -> str:
    """Build one batch message for a profile: title + list of items."""
    lines = ["RoleForge batch", "", f"Profile: {profile_name}", ""]
    for item in items[:max_items]:
        lines.append(
            _format_batch_line(
                item["vacancy"],
                item.get("score"),
            )
        )
    if len(items) > max_items:
        lines.append(f"… and {len(items) - max_items} more in queue.")
    return "\n".join(lines)


def _get_eligible_batch_matches(conn: Any) -> list[dict[str, Any]]:
    """
    Return profile_matches eligible for batch delivery:
    - profile has delivery_mode.batch_enabled = true
    - score >= batch_threshold and score < immediate_threshold
    - no existing telegram_deliveries row with delivery_type='batch' for this profile_match_id
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
            WHERE (p.config->'delivery_mode'->>'batch_enabled')::text = 'true'
              AND pm.score >= COALESCE(
                  (p.config->'delivery_mode'->>'batch_threshold')::numeric,
                  0.55
              )
              AND pm.score < COALESCE(
                  (p.config->'delivery_mode'->>'immediate_threshold')::numeric,
                  0.80
              )
              AND NOT EXISTS (
                  SELECT 1 FROM telegram_deliveries td
                  WHERE td.delivery_type = 'batch'
                    AND td.payload->>'profile_match_id' = pm.id::text
              )
            ORDER BY p.id, pm.score DESC, pm.created_at ASC
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
    Run the batch job once: find eligible matches, group by profile,
    send one Telegram message per profile, log each match to telegram_deliveries,
    and write job_runs summary.
    """
    conn = connect_db()
    run_id = log_job_start(conn, "batch")
    try:
        candidates = _get_eligible_batch_matches(conn)
        summary: dict[str, Any] = {
            "run_id": str(run_id),
            "status": "success",
            "eligible_count": len(candidates),
            "batches_sent": 0,
            "matches_sent": 0,
        }
        # Group by profile (used for both dry-run preview and live send)
        by_profile: dict[str, list[dict[str, Any]]] = {}
        for c in candidates:
            name = c["profile_name"]
            by_profile.setdefault(name, []).append(c)

        if dry_run:
            summary["dry_run"] = True
            if by_profile:
                first_profile = next(iter(by_profile))
                items = by_profile[first_profile]
                summary["preview"] = _format_batch_message(first_profile, items)
                summary["preview_count"] = len(candidates)
                summary["profiles_with_eligible"] = len(by_profile)
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

        batches_sent = 0
        matches_sent = 0
        for profile_name, items in by_profile.items():
            text = _format_batch_message(profile_name, items)
            response = send_message(bot_token, chat_id, text)
            # Log one delivery per match so we never resend the same match (idempotency)
            for item in items:
                log_telegram_delivery(
                    conn,
                    "batch",
                    {
                        "profile_match_id": str(item["profile_match_id"]),
                        "profile_id": str(item["profile_id"]),
                        "vacancy_id": str(item["vacancy_id"]),
                        "chat_id": chat_id,
                        "text_preview": text[:500],
                        "telegram_response": response,
                    },
                )
                matches_sent += 1
            batches_sent += 1

        summary["batches_sent"] = batches_sent
        summary["matches_sent"] = matches_sent
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
        description="Send Telegram micro-batch for mid-band matches (batch_enabled, batch_threshold <= score < immediate_threshold)."
    )
    parser.add_argument("--dry-run", action="store_true", help="List eligible matches and preview first profile batch without sending.")
    parser.add_argument("--chat-id", help="Override TELEGRAM_CHAT_ID for this run.")
    args = parser.parse_args()
    result = run_once(dry_run=args.dry_run, chat_id=args.chat_id)
    if "preview" in result:
        print(result["preview"])
        print()
    print(json.dumps({k: v for k, v in result.items() if k != "preview"}, indent=2))


if __name__ == "__main__":
    main()
