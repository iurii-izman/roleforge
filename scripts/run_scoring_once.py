#!/usr/bin/env python3
"""
Score all stored vacancies against available profiles and persist profile_matches.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from roleforge.review_ordering import update_review_ranks_for_profile
from roleforge.runtime import connect_db, load_jsonb
from roleforge.scoring import persist_matches, score_vacancy_for_profiles


def main() -> None:
    conn = connect_db()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, name, config FROM profiles ORDER BY created_at ASC")
            profiles = [
                {"id": row[0], "name": row[1], "config": load_jsonb(row[2])}
                for row in cur.fetchall()
            ]
            cur.execute(
                """
                SELECT id, canonical_url, company, title, location, salary_raw, parse_confidence
                FROM vacancies
                ORDER BY created_at ASC
                """
            )
            vacancies = [
                {
                    "id": row[0],
                    "canonical_url": row[1],
                    "company": row[2],
                    "title": row[3],
                    "location": row[4],
                    "salary_raw": row[5],
                    "parse_confidence": float(row[6]) if row[6] is not None else None,
                }
                for row in cur.fetchall()
            ]

        matches_written = 0
        for vacancy in vacancies:
            matches = score_vacancy_for_profiles(vacancy, profiles)
            if matches:
                matches_written += persist_matches(conn, str(vacancy["id"]), matches)

        ranks_updated = 0
        for profile in profiles:
            ranks_updated += update_review_ranks_for_profile(conn, profile["id"])
    finally:
        conn.close()

    print(
        json.dumps(
            {
                "profiles": len(profiles),
                "vacancies": len(vacancies),
                "matches_written": matches_written,
                "review_ranks_updated": ranks_updated,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
