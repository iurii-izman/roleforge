"""
Review ordering: deterministic review_rank by score and created_at (TASK-025).

Makes profile matches sortable; review_rank is persisted so queue can show cards in order.
"""

from __future__ import annotations

from typing import Any


def assign_review_ranks(
    matches: list[dict[str, Any]],
    *,
    score_key: str = "score",
    created_at_key: str = "created_at",
    id_key: str = "id",
) -> list[tuple[Any, int]]:
    """
    Sort matches by score descending, then created_at ascending. Assign review_rank 0, 1, 2, ...
    Returns list of (match_id, review_rank). Lower rank = higher in queue.
    """
    def sort_key(m: dict[str, Any]) -> tuple[float, str]:
        sc = m.get(score_key)
        score = -float(sc) if sc is not None else 0.0
        created = m.get(created_at_key) or ""
        return (score, str(created))

    sorted_matches = sorted(matches, key=sort_key)
    return [(m.get(id_key), rank) for rank, m in enumerate(sorted_matches)]


def update_review_ranks_for_profile(conn: Any, profile_id: Any) -> int:
    """
    Fetch all profile_matches for profile (state not in ignored, applied), assign review_rank
    by score desc and created_at asc, update DB. Returns number of rows updated.
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, score, created_at FROM profile_matches
            WHERE profile_id = %s AND state NOT IN ('ignored', 'applied')
            ORDER BY score DESC NULLS LAST, created_at ASC
            """,
            (profile_id,),
        )
        rows = cur.fetchall()
    if not rows:
        return 0
    with conn.cursor() as cur:
        for rank, (match_id, _score, _created_at) in enumerate(rows):
            cur.execute(
                "UPDATE profile_matches SET review_rank = %s, updated_at = now() WHERE id = %s",
                (rank, match_id),
            )
    conn.commit()
    return len(rows)
