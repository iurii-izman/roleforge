"""
Review queue: one card per profile_match, actions update state and review_actions (TASK-029).

Format queue cards; get next match by review_rank; apply Open, Shortlist, Later, Ignore, Applied, Next.
See docs/specs/telegram-interaction.md.
"""

from __future__ import annotations

from typing import Any

# Actions that change profile_matches.state
ACTION_TO_STATE = {
    "shortlist": "shortlisted",
    "review_later": "review_later",
    "ignore": "ignored",
    "applied": "applied",
}
VALID_ACTIONS = frozenset(("open", "shortlist", "review_later", "ignore", "applied", "next"))


def format_queue_card(
    match: dict[str, Any],
    vacancy: dict[str, Any],
    *,
    include_explainability: bool = True,
    max_title_len: int = 60,
    max_company_len: int = 30,
    profile_name: str | None = None,
) -> str:
    """
    Format one queue card: title, company, location, score, link, and optional context.

    match: profile_match row (score, explainability, id, optional queue_position/queue_total).
    vacancy: vacancy row (title, company, location, canonical_url or source url).
    """
    title = (vacancy.get("title") or "—")[:max_title_len]
    company = (vacancy.get("company") or "—")[:max_company_len]
    location = (vacancy.get("location") or "").strip() or None
    score = match.get("score")
    score_s = f" Score: {score:.2f}" if score is not None else ""
    queue_pos = match.get("queue_position")
    queue_total = match.get("queue_total")
    url = vacancy.get("canonical_url") or vacancy.get("url") or ""
    lines = [title, f"at {company}{score_s}"]
    if profile_name:
        lines.append(f"Profile: {profile_name}")
    if location:
        lines.append(location)
    if url:
        lines.append(url)
    if queue_pos is not None and queue_total:
        lines.append(f"Queue: {int(queue_pos)} of {int(queue_total)}")
    if include_explainability and match.get("explainability"):
        expl = match["explainability"]
        if isinstance(expl, dict):
            pos = expl.get("positive_factors") or []
            if pos:
                factor_labels = {
                    "title_match": "Title match",
                    "company_match": "Company match",
                    "location_match": "Location match",
                    "keyword_bonus": "Keyword bonus",
                }
                pretty = [
                    factor_labels.get(name, name) for name in pos[:3]
                ]
                lines.append(f"+ Why in queue: {', '.join(pretty)}")
    return "\n".join(lines)


def get_next_queue_match(conn: Any, profile_id: Any) -> dict[str, Any] | None:
    """
    Fetch the next profile_match for this profile (state not ignored/applied), ordered by review_rank asc.
    Returns dict with match row + vacancy row (keys: match, vacancy), or None if queue empty.
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                pm.id,
                pm.profile_id,
                pm.vacancy_id,
                pm.score,
                pm.state,
                pm.explainability,
                pm.review_rank,
                v.id AS v_id,
                v.canonical_url,
                v.company,
                v.title,
                v.location,
                row_number() OVER (
                    ORDER BY pm.review_rank ASC NULLS LAST, pm.created_at ASC
                ) AS queue_position,
                count(*) OVER () AS queue_total
            FROM profile_matches pm
            JOIN vacancies v ON v.id = pm.vacancy_id
            WHERE pm.profile_id = %s AND pm.state NOT IN ('ignored', 'applied')
            ORDER BY pm.review_rank ASC NULLS LAST, pm.created_at ASC
            LIMIT 1
            """,
            (profile_id,),
        )
        row = cur.fetchone()
    if not row:
        return None
    # Row: id, profile_id, vacancy_id, score, state, explainability, review_rank,
    #      v_id, canonical_url, company, title, location, queue_position, queue_total
    return {
        "match": {
            "id": row[0],
            "profile_id": row[1],
            "vacancy_id": row[2],
            "score": float(row[3]) if row[3] is not None else None,
            "state": row[4],
            "explainability": row[5],
            "review_rank": row[6],
            "queue_position": int(row[12]) if row[12] is not None else None,
            "queue_total": int(row[13]) if row[13] is not None else None,
        },
        "vacancy": {
            "id": row[7],
            "canonical_url": row[8],
            "company": row[9],
            "title": row[10],
            "location": row[11],
        },
    }


def get_next_queue_match_any_profile(conn: Any, profile_ids: list[Any]) -> dict[str, Any] | None:
    """
    Next match across given profiles: first by (profile order, review_rank). One card per profile_match.
    """
    for pid in profile_ids:
        out = get_next_queue_match(conn, pid)
        if out:
            return out
    return None


def apply_review_action(conn: Any, profile_match_id: Any, action: str) -> None:
    """
    Record action in review_actions and update profile_matches.state when action is shortlist/later/ignore/applied.
    'open' and 'next' only write review_actions; state unchanged.
    """
    if action not in VALID_ACTIONS:
        raise ValueError(f"Invalid action: {action}")
    new_state = ACTION_TO_STATE.get(action)
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO review_actions (profile_match_id, action) VALUES (%s, %s)",
            (profile_match_id, action),
        )
        if new_state:
            cur.execute(
                "UPDATE profile_matches SET state = %s, updated_at = now() WHERE id = %s",
                (new_state, profile_match_id),
            )
    conn.commit()
