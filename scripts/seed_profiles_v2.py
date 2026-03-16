#!/usr/bin/env python3
"""
Seed or update a small set of v2 profiles on top of the MVP default.

This script keeps the existing `default_mvp` profile and adds a couple of
concrete, but still conservative, presets:

- primary_search: main profile for the current search intent
- stretch_geo: same intent, but looser geography / remote preference

All profiles reuse the existing profiles.config JSONB shape:
- hard_filters: locations, exclude_titles, exclude_companies, min_parse_confidence
- weights: per-dimension weights for the shared scoring engine
- min_score: optional per-profile floor for queue/digest inclusion

No schema changes are introduced; this is a pure data/seed helper.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from roleforge.runtime import connect_db  # type: ignore
from roleforge.scoring import DEFAULT_WEIGHTS  # type: ignore


def _profile_row(name: str, config: dict[str, Any]) -> dict[str, Any]:
    return {"name": name, "config": config}


def _build_profiles() -> list[dict[str, Any]]:
    """
    Define a minimal, opinionated profile set that is still safe to adjust.

    These presets are intentionally generic; the operator is expected to
    tweak locations, excluded titles/companies, and min_score thresholds
    to match a real search.
    """
    default_mvp = _profile_row(
        "default_mvp",
        {
            "hard_filters": {},
            "weights": DEFAULT_WEIGHTS,
            "min_score": None,
        },
    )

    primary_search = _profile_row(
        "primary_search",
        {
            "intent": "Primary search: remote-first, EU-friendly.",
            "hard_filters": {
                "locations": ["remote", "europe", "eu", "europe/remote"],
                "exclude_titles": ["intern", "junior"],
                "exclude_companies": [],
                "min_parse_confidence": 0.4,
            },
            "weights": DEFAULT_WEIGHTS,
            "min_score": 0.5,
        },
    )

    stretch_geo = _profile_row(
        "stretch_geo",
        {
            "intent": "Stretch geography: remote + Americas / global.",
            "hard_filters": {
                "locations": ["remote", "us", "americas", "global", "worldwide"],
                "exclude_titles": ["intern"],
                "exclude_companies": [],
                "min_parse_confidence": 0.3,
            },
            "weights": DEFAULT_WEIGHTS,
            "min_score": 0.35,
        },
    )

    return [default_mvp, primary_search, stretch_geo]


def main() -> None:
    profiles = _build_profiles()
    conn = connect_db()
    try:
        with conn.cursor() as cur:
            for p in profiles:
                name = p["name"]
                config = p["config"]
                cur.execute(
                    "SELECT id FROM profiles WHERE name = %s ORDER BY created_at LIMIT 1",
                    (name,),
                )
                existing = cur.fetchone()
                if existing:
                    cur.execute(
                        "UPDATE profiles SET config = %s::jsonb WHERE name = %s",
                        (json.dumps(config), name),
                    )
                else:
                    cur.execute(
                        "INSERT INTO profiles (name, config) VALUES (%s, %s::jsonb)",
                        (name, json.dumps(config)),
                    )
            cur.execute(
                "SELECT id, name, config FROM profiles WHERE name = ANY(%s) ORDER BY created_at ASC",
                ([p["name"] for p in profiles],),
            )
            rows = cur.fetchall()
        conn.commit()
    finally:
        conn.close()

    summary = [
        {"profile_id": str(row[0]), "name": row[1], "config": row[2]} for row in rows
    ]
    print(json.dumps(summary, indent=2, default=str))


if __name__ == "__main__":
    main()

