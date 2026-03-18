from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any


def score_distribution(conn: Any) -> list[dict[str, Any]]:
    """
    Return counts of profile_matches by score band.
    Bands match repo conventions: high>=0.75, medium>=0.50, low<0.50.
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT
              CASE
                WHEN score >= 0.75 THEN 'high'
                WHEN score >= 0.50 THEN 'medium'
                ELSE 'low'
              END AS band,
              COUNT(*) AS cnt
            FROM profile_matches
            GROUP BY 1
            ORDER BY 1
            """
        )
        rows = cur.fetchall()
    return [{"band": r[0], "count": int(r[1])} for r in rows]


def match_counts_by_profile(conn: Any, *, days: int = 14) -> list[dict[str, Any]]:
    since = datetime.now(timezone.utc) - timedelta(days=days)
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT
              p.name,
              COUNT(pm.*) AS matches_total,
              SUM(CASE WHEN pm.state = 'new' THEN 1 ELSE 0 END) AS matches_new,
              SUM(CASE WHEN pm.state = 'shortlisted' THEN 1 ELSE 0 END) AS matches_shortlisted,
              SUM(CASE WHEN pm.state = 'review_later' THEN 1 ELSE 0 END) AS matches_review_later,
              SUM(CASE WHEN pm.state = 'ignored' THEN 1 ELSE 0 END) AS matches_ignored,
              SUM(CASE WHEN pm.state = 'applied' THEN 1 ELSE 0 END) AS matches_applied
            FROM profiles p
            LEFT JOIN profile_matches pm ON pm.profile_id = p.id AND pm.created_at >= %s
            GROUP BY p.name
            ORDER BY p.name ASC
            """,
            (since,),
        )
        rows = cur.fetchall()
    out = []
    for r in rows:
        out.append(
            {
                "profile_name": r[0],
                "matches_total": int(r[1] or 0),
                "matches_new": int(r[2] or 0),
                "matches_shortlisted": int(r[3] or 0),
                "matches_review_later": int(r[4] or 0),
                "matches_ignored": int(r[5] or 0),
                "matches_applied": int(r[6] or 0),
            }
        )
    return out


def source_counts(conn: Any, *, days: int = 30) -> list[dict[str, Any]]:
    since = datetime.now(timezone.utc) - timedelta(days=days)
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT
              CASE
                WHEN vo.gmail_message_id IS NOT NULL THEN 'gmail'
                WHEN vo.feed_source_key LIKE 'monitor:%' THEN 'monitor'
                WHEN vo.feed_source_key LIKE 'connector:%' THEN 'connector'
                WHEN vo.feed_source_key IS NOT NULL THEN 'feed'
                ELSE 'unknown'
              END AS source_kind,
              COUNT(*) AS observations
            FROM vacancy_observations vo
            WHERE vo.created_at >= %s
            GROUP BY 1
            ORDER BY 1
            """,
            (since,),
        )
        rows = cur.fetchall()
    return [{"source_kind": r[0], "observations": int(r[1])} for r in rows]


def application_funnel(conn: Any, *, days: int = 90) -> dict[str, int]:
    since = datetime.now(timezone.utc) - timedelta(days=days)
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT
              COUNT(*) FILTER (WHERE status = 'applied') AS applied,
              COUNT(*) FILTER (WHERE status = 'hr_pinged') AS hr_pinged,
              COUNT(*) FILTER (WHERE status = 'interview_scheduled') AS interview_scheduled,
              COUNT(*) FILTER (WHERE status = 'offer') AS offer,
              COUNT(*) FILTER (WHERE status = 'accepted') AS accepted,
              COUNT(*) FILTER (WHERE status = 'declined') AS declined,
              COUNT(*) FILTER (WHERE status = 'rejected') AS rejected,
              COUNT(*) FILTER (WHERE status = 'ghosted') AS ghosted
            FROM applications
            WHERE applied_at >= %s
            """,
            (since,),
        )
        row = cur.fetchone() or (0, 0, 0, 0, 0, 0, 0, 0)
    keys = [
        "applied",
        "hr_pinged",
        "interview_scheduled",
        "offer",
        "accepted",
        "declined",
        "rejected",
        "ghosted",
    ]
    return {k: int(v or 0) for k, v in zip(keys, row)}


def recent_job_runs(conn: Any, *, limit: int = 25) -> list[dict[str, Any]]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT job_type, started_at, finished_at, status, summary
            FROM job_runs
            ORDER BY started_at DESC
            LIMIT %s
            """,
            (int(limit),),
        )
        rows = cur.fetchall()
    out: list[dict[str, Any]] = []
    for r in rows:
        out.append(
            {
                "job_type": r[0],
                "started_at": r[1],
                "finished_at": r[2],
                "status": r[3],
                "summary": r[4] or {},
            }
        )
    return out


def job_status_by_type(conn: Any, *, per_type: int = 5) -> dict[str, list[dict[str, Any]]]:
    # Simple approach: fetch last N overall, group in Python.
    rows = recent_job_runs(conn, limit=200)
    grouped: dict[str, list[dict[str, Any]]] = {}
    for r in rows:
        grouped.setdefault(r["job_type"], [])
        if len(grouped[r["job_type"]]) < per_type:
            grouped[r["job_type"]].append(r)
    return grouped


def list_profiles(conn: Any) -> list[dict[str, Any]]:
    with conn.cursor() as cur:
        cur.execute("SELECT id, name FROM profiles ORDER BY created_at ASC")
        rows = cur.fetchall()
    return [{"id": str(r[0]), "name": r[1]} for r in rows]


def queue_browser_items(
    conn: Any,
    *,
    profile_id: str | None = None,
    state: str | None = None,
    limit: int = 200,
) -> list[dict[str, Any]]:
    params: list[Any] = []
    where = ["pm.state NOT IN ('ignored', 'applied')"]
    if profile_id:
        where.append("pm.profile_id = %s")
        params.append(profile_id)
    if state:
        where.append("pm.state = %s")
        params.append(state)
    where_sql = " AND ".join(where)
    with conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT
              pm.id,
              pm.profile_id,
              p.name AS profile_name,
              pm.score,
              pm.state,
              pm.review_rank,
              pm.created_at,
              v.title,
              v.company,
              v.location,
              v.canonical_url
            FROM profile_matches pm
            JOIN profiles p ON p.id = pm.profile_id
            JOIN vacancies v ON v.id = pm.vacancy_id
            WHERE {where_sql}
            ORDER BY pm.review_rank ASC NULLS LAST, pm.created_at ASC
            LIMIT %s
            """,
            (*params, int(limit)),
        )
        rows = cur.fetchall()
    out: list[dict[str, Any]] = []
    for r in rows:
        out.append(
            {
                "profile_match_id": str(r[0]),
                "profile_id": str(r[1]),
                "profile_name": r[2],
                "score": float(r[3]) if r[3] is not None else None,
                "state": r[4],
                "review_rank": r[5],
                "created_at": r[6],
                "title": r[7],
                "company": r[8],
                "location": r[9],
                "url": r[10],
            }
        )
    return out


def get_profile(conn: Any, profile_id: str) -> dict[str, Any] | None:
    with conn.cursor() as cur:
        cur.execute("SELECT id, name, config, created_at FROM profiles WHERE id = %s", (profile_id,))
        row = cur.fetchone()
    if not row:
        return None
    return {"id": str(row[0]), "name": row[1], "config": row[2] or {}, "created_at": row[3]}

