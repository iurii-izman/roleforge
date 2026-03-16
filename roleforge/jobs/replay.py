"""
CLI wrappers around replay helpers.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone

from roleforge.replay import replay_date_window, replay_one_message
from roleforge.runtime import connect_db


def _parse_date(value: str) -> datetime:
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def main() -> None:
    parser = argparse.ArgumentParser(description="Replay one message or a received_at window.")
    parser.add_argument("--gmail-message-id", help="Replay exactly one stored Gmail message.")
    parser.add_argument("--start-date", help="Inclusive ISO datetime/date for received_at lower bound.")
    parser.add_argument("--end-date", help="Inclusive ISO datetime/date for received_at upper bound.")
    args = parser.parse_args()

    if not args.gmail_message_id and not args.start_date and not args.end_date:
        parser.error("Provide --gmail-message-id or a date window.")

    conn = connect_db()
    try:
        if args.gmail_message_id:
            result = replay_one_message(conn, args.gmail_message_id)
        else:
            start_date = _parse_date(args.start_date) if args.start_date else None
            end_date = _parse_date(args.end_date) if args.end_date else None
            result = replay_date_window(conn, start_date=start_date, end_date=end_date)
        print(json.dumps(result, indent=2))
    finally:
        conn.close()


if __name__ == "__main__":
    main()
