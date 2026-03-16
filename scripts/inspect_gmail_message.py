#!/usr/bin/env python3
"""
Inspect one stored Gmail message and run deterministic candidate extraction on it.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from roleforge.parser.extractor import extract_candidates
from roleforge.replay import _subject_from_metadata
from roleforge.runtime import connect_db, load_jsonb


def main() -> None:
    parser = argparse.ArgumentParser(description="Inspect one stored Gmail message and extracted candidates.")
    parser.add_argument("gmail_message_id")
    parser.add_argument("--body-preview-chars", type=int, default=600)
    args = parser.parse_args()

    conn = connect_db()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT gmail_message_id, raw_metadata, body_plain, body_html, received_at
                FROM gmail_messages
                WHERE gmail_message_id = %s
                """,
                (args.gmail_message_id,),
            )
            row = cur.fetchone()
    finally:
        conn.close()

    if not row:
        raise SystemExit(f"gmail_message_id not found: {args.gmail_message_id}")

    raw_metadata = load_jsonb(row[1])
    subject = _subject_from_metadata(raw_metadata)
    body_plain = row[2] or ""
    body_html = row[3]
    candidates = extract_candidates(body_plain, body_html, subject, row[0])

    print(
        json.dumps(
            {
                "gmail_message_id": row[0],
                "received_at": row[4].isoformat() if row[4] else None,
                "subject": subject,
                "body_plain_preview": body_plain[: args.body_preview_chars],
                "body_html_present": bool(body_html),
                "candidate_count": len(candidates),
                "candidates": candidates,
            },
            indent=2,
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
