"""
Build a digest from profile_matches and optionally send it to Telegram.
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from typing import Any

from roleforge.delivery_log import log_telegram_delivery
from roleforge.digest import build_digest_sections_from_matches, format_digest
from roleforge.job_runs import log_job_finish, log_job_start
from roleforge.runtime import connect_db, get_setting
from roleforge.telegram import send_message


def _rows_to_matches(rows: list[tuple[Any, ...]]) -> dict[str, list[dict[str, Any]]]:
    matches_by_profile: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for profile_name, state, score, created_at, title, company in rows:
        matches_by_profile[profile_name].append(
            {
                "state": state,
                "score": float(score) if score is not None else None,
                "created_at": created_at.isoformat() if created_at else None,
                "vacancy": {"title": title, "company": company},
            }
        )
    return dict(matches_by_profile)


def _build_digest_text(conn: Any, *, top_n: int = 5) -> tuple[str, int, int]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT p.name, pm.state, pm.score, pm.created_at, v.title, v.company
            FROM profile_matches pm
            JOIN profiles p ON p.id = pm.profile_id
            JOIN vacancies v ON v.id = pm.vacancy_id
            WHERE pm.state NOT IN ('ignored', 'applied')
            ORDER BY p.name ASC, pm.score DESC NULLS LAST, pm.created_at ASC
            """
        )
        rows = cur.fetchall()
    matches_by_profile = _rows_to_matches(rows)
    sections = build_digest_sections_from_matches(matches_by_profile, top_n=top_n)
    if not sections:
        return "RoleForge digest\n\nNo items in queue.\n\nOpen queue: /queue", 0, 0
    text = format_digest(sections, max_highlights_per_profile=top_n)
    return text, len(rows), len(sections)


def run_once(*, dry_run: bool = False, chat_id: str | None = None, top_n: int = 5) -> dict[str, Any]:
    conn = connect_db()
    run_id = log_job_start(conn, "digest")
    try:
        text, total_matches, profile_count = _build_digest_text(conn, top_n=top_n)
        summary: dict[str, Any] = {
            "run_id": str(run_id),
            "status": "success",
            "profiles": profile_count,
            "matches_in_digest": total_matches,
            "messages_sent": 0,
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
                "digest",
                {"chat_id": chat_id, "text_preview": text[:500], "telegram_response": response},
            )
            summary["messages_sent"] = 1
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
    parser = argparse.ArgumentParser(description="Build and optionally send the Telegram digest.")
    parser.add_argument("--dry-run", action="store_true", help="Print digest text without sending.")
    parser.add_argument("--chat-id", help="Override TELEGRAM_CHAT_ID for this run.")
    parser.add_argument("--top-n", type=int, default=5)
    args = parser.parse_args()
    result = run_once(dry_run=args.dry_run, chat_id=args.chat_id, top_n=args.top_n)
    if "preview" in result:
        print(result["preview"])
        print()
    print(json.dumps({k: v for k, v in result.items() if k != "preview"}, indent=2))


if __name__ == "__main__":
    main()
