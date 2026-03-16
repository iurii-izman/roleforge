#!/usr/bin/env python3
"""
Create or update the default_mvp profile used by the MVP checks.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from roleforge.runtime import connect_db
from roleforge.scoring import DEFAULT_WEIGHTS


DEFAULT_PROFILE_NAME = "default_mvp"
DEFAULT_PROFILE_CONFIG = {
    "hard_filters": {},
    "weights": DEFAULT_WEIGHTS,
    "min_score": None,
}


def main() -> None:
    conn = connect_db()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id FROM profiles WHERE name = %s ORDER BY created_at LIMIT 1",
                (DEFAULT_PROFILE_NAME,),
            )
            existing = cur.fetchone()
            if existing:
                cur.execute(
                    "UPDATE profiles SET config = %s::jsonb WHERE name = %s",
                    (json.dumps(DEFAULT_PROFILE_CONFIG), DEFAULT_PROFILE_NAME),
                )
            else:
                cur.execute(
                    """
                    INSERT INTO profiles (name, config)
                    VALUES (%s, %s::jsonb)
                    """,
                    (DEFAULT_PROFILE_NAME, json.dumps(DEFAULT_PROFILE_CONFIG)),
                )
            cur.execute(
                "SELECT id, name, config FROM profiles WHERE name = %s ORDER BY created_at LIMIT 1",
                (DEFAULT_PROFILE_NAME,),
            )
            row = cur.fetchone()
        conn.commit()
    finally:
        conn.close()

    print(
        json.dumps(
            {
                "profile_id": str(row[0]),
                "name": row[1],
                "config": row[2],
            },
            indent=2,
            default=str,
        )
    )


if __name__ == "__main__":
    main()
