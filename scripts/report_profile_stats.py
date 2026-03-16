#!/usr/bin/env python3
"""
Minimal operator-facing analytics for profile matches and review outcomes (v2).

Answers questions like:
- How many new matches were created per profile in a time window?
- How many items ended up shortlisted / ignored / review_later / applied?
- How many high-score matches (score >= 0.75) exist per profile?

This script intentionally stays simple: it prints a JSON summary to stdout and
does not introduce any dashboard or external dependencies.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from roleforge.runtime import connect_db  # type: ignore


def _parse_since(days: int | None, since_str: str | None) -> datetime | None:
    if since_str:
        return datetime.fromisoformat(since_str).replace(tzinfo=timezone.utc)
    if days is not None:
        return datetime.now(timezone.utc) - timedelta(days=days)
    return None


def _summarize_rows(
    rows: list[tuple[Any, ...]],
    *,
    since: datetime | None = None,
) -> dict[str, Any]:
    """
    rows: profile_name, state, score, created_at
    If since is set, new_in_window = matches with created_at >= since.
    """
    by_profile: dict[str, Any] = {}
    for profile_name, state, score, created_at in rows:
        name = str(profile_name)
        s = float(score) if score is not None else 0.0
        prof = by_profile.setdefault(
            name,
            {
                "matches_total": 0,
                "state_counts": {},
                "high_score_matches": 0,
                "new_in_window": 0,
                "high_score_applied": 0,
            },
        )
        prof["matches_total"] += 1
        prof["state_counts"][state] = prof["state_counts"].get(state, 0) + 1
        if s >= 0.75:
            prof["high_score_matches"] += 1
        if since and created_at:
            _at = created_at.replace(tzinfo=timezone.utc) if getattr(created_at, "tzinfo", None) is None else created_at
            if _at >= since:
                prof["new_in_window"] += 1
        if s >= 0.75 and state == "applied":
            prof["high_score_applied"] += 1
    return by_profile


def main() -> None:
    parser = argparse.ArgumentParser(description="Report basic per-profile analytics.")
    parser.add_argument(
        "--days",
        type=int,
        help="Look back this many days from now (UTC).",
    )
    parser.add_argument(
        "--since",
        help="ISO date/time (UTC) lower bound, e.g. 2026-03-15T00:00:00.",
    )
    args = parser.parse_args()

    since = _parse_since(args.days, args.since)

    conn = connect_db()
    try:
        with conn.cursor() as cur:
            if since is not None:
                cur.execute(
                    """
                    SELECT p.name, pm.state, pm.score, pm.created_at
                    FROM profile_matches pm
                    JOIN profiles p ON p.id = pm.profile_id
                    WHERE pm.created_at >= %s
                    """,
                    (since,),
                )
            else:
                cur.execute(
                    """
                    SELECT p.name, pm.state, pm.score, pm.created_at
                    FROM profile_matches pm
                    JOIN profiles p ON p.id = pm.profile_id
                    """
                )
            rows = cur.fetchall()
    finally:
        conn.close()

    summary = {
        "since": since.isoformat() if since is not None else None,
        "profiles": _summarize_rows(rows, since=since),
    }
    print(json.dumps(summary, indent=2, default=str))


if __name__ == "__main__":
    main()
