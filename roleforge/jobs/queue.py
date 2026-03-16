"""
Preview or send the next queue card for one profile.
"""

from __future__ import annotations

import argparse
import json
from typing import Any

from roleforge.delivery_log import log_telegram_delivery
from roleforge.job_runs import log_job_finish, log_job_start
from roleforge.queue import format_queue_card, get_next_queue_match
from roleforge.runtime import connect_db, get_setting
from roleforge.telegram import send_message


def _resolve_profile_id(conn: Any, profile_name: str | None) -> tuple[Any, str]:
    with conn.cursor() as cur:
        if profile_name:
            cur.execute(
                "SELECT id, name FROM profiles WHERE name = %s ORDER BY created_at LIMIT 1",
                (profile_name,),
            )
        else:
            cur.execute("SELECT id, name FROM profiles ORDER BY created_at LIMIT 1")
        row = cur.fetchone()
    if not row:
        raise RuntimeError("No profiles found")
    return row[0], row[1]


def run_once(*, profile_name: str | None = None, dry_run: bool = False, chat_id: str | None = None) -> dict[str, Any]:
    conn = connect_db()
    run_id = log_job_start(conn, "queue")
    try:
        profile_id, resolved_profile_name = _resolve_profile_id(conn, profile_name)
        next_item = get_next_queue_match(conn, profile_id)
        if not next_item:
            summary = {
                "run_id": str(run_id),
                "status": "success",
                "profile_name": resolved_profile_name,
                "cards_sent": 0,
                "queue_empty": True,
            }
            log_job_finish(conn, run_id, "success", summary)
            return summary

        text = format_queue_card(
            next_item["match"],
            next_item["vacancy"],
            profile_name=resolved_profile_name,
        )
        summary: dict[str, Any] = {
            "run_id": str(run_id),
            "status": "success",
            "profile_name": resolved_profile_name,
            "cards_sent": 0,
            "queue_empty": False,
            "profile_match_id": str(next_item["match"]["id"]),
        }
        if dry_run:
            summary["dry_run"] = True
            summary["preview"] = text
        else:
            bot_token = get_setting("TELEGRAM_BOT_TOKEN")
            chat_id = chat_id or get_setting("TELEGRAM_CHAT_ID")
            if not bot_token:
                raise RuntimeError("Missing TELEGRAM_BOT_TOKEN")
            if not chat_id:
                raise RuntimeError("Missing TELEGRAM_CHAT_ID")
            response = send_message(bot_token, chat_id, text)
            log_telegram_delivery(
                conn,
                "queue_card",
                {
                    "chat_id": chat_id,
                    "profile_match_id": str(next_item["match"]["id"]),
                    "text_preview": text[:500],
                    "telegram_response": response,
                },
            )
            summary["cards_sent"] = 1
            summary["chat_id"] = chat_id
        log_job_finish(conn, run_id, "success", {k: v for k, v in summary.items() if k != "preview"})
        return summary
    except Exception as exc:
        summary = {"run_id": str(run_id), "status": "failure", "message": str(exc)}
        log_job_finish(conn, run_id, "failure", summary)
        raise
    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Preview or send the next queue card.")
    parser.add_argument("--profile-name", help="Profile name. Defaults to the first profile.")
    parser.add_argument("--dry-run", action="store_true", help="Print the next card without sending.")
    parser.add_argument("--chat-id", help="Override TELEGRAM_CHAT_ID.")
    args = parser.parse_args()
    result = run_once(profile_name=args.profile_name, dry_run=args.dry_run, chat_id=args.chat_id)
    if "preview" in result:
        print(result["preview"])
        print()
    print(json.dumps({k: v for k, v in result.items() if k != "preview"}, indent=2))


if __name__ == "__main__":
    main()
