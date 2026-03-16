"""
Global dedup across messages and digest fragments (TASK-020).

Groups raw candidates by canonical key (normalized URL/title/company); merges into
one vacancy per group with multiple vacancy_observations. Persistence: get-or-create
vacancy by canonical_url, then link observations.
"""

from __future__ import annotations

from typing import Any

from roleforge.normalize import dedup_key, normalize_company, normalize_location, normalize_title, normalize_url


def normalize_candidate(candidate: dict[str, Any]) -> dict[str, Any]:
    """Return a copy with canonical_url, title, company, location normalized."""
    out = dict(candidate)
    if out.get("canonical_url"):
        out["canonical_url"] = normalize_url(out["canonical_url"])
    if out.get("title") is not None:
        out["title"] = normalize_title(out["title"])
    if out.get("company") is not None:
        out["company"] = normalize_company(out["company"])
    if out.get("location") is not None:
        out["location"] = normalize_location(out["location"])
    return out


def group_by_dedup_key(
    candidates: list[dict[str, Any]],
    *,
    source_fields: tuple[str, ...] = ("gmail_message_id", "fragment_key", "raw_snippet"),
) -> list[tuple[dict[str, Any], list[dict[str, Any]]]]:
    """
    Normalize candidates and group by dedup key. Each group = one vacancy + N sources.

    Each candidate may include gmail_message_id, fragment_key, raw_snippet (for persistence).
    Returns list of (vacancy_dict, list of source_dict). vacancy_dict has schema fields
    (no fragment_key); source_dict has gmail_message_id, fragment_key, raw_snippet.
    """
    normalized = [normalize_candidate(c) for c in candidates]
    groups: dict[tuple[str, str, str], tuple[dict[str, Any], list[dict[str, Any]]]] = {}
    for c in normalized:
        key = dedup_key(c)
        vacancy_row = {
            "canonical_url": c.get("canonical_url"),
            "company": c.get("company"),
            "title": c.get("title"),
            "location": c.get("location"),
            "salary_raw": c.get("salary_raw"),
            "parse_confidence": c.get("parse_confidence"),
        }
        source = {
            "gmail_message_id": c.get("gmail_message_id"),
            "fragment_key": c.get("fragment_key", "0"),
            "raw_snippet": c.get("raw_snippet"),
        }
        if key not in groups:
            groups[key] = (vacancy_row, [])
        groups[key][1].append(source)
    return list(groups.values())


def persist_deduped(
    conn: Any,
    grouped: list[tuple[dict[str, Any], list[dict[str, Any]]]],
) -> list[Any]:
    """
    Persist grouped (vacancy, sources). For each group: get-or-create vacancy by
    canonical_url; insert vacancy_observations. Returns list of vacancy ids (UUID).
    """
    from uuid import UUID

    vacancy_ids: list[UUID] = []
    with conn.cursor() as cur:
        for vacancy_row, sources in grouped:
            canonical_url = vacancy_row.get("canonical_url")
            title = vacancy_row.get("title")
            company = vacancy_row.get("company")
            vacancy_id = None
            if canonical_url:
                cur.execute(
                    "SELECT id FROM vacancies WHERE canonical_url = %s ORDER BY created_at LIMIT 1",
                    (canonical_url,),
                )
                row = cur.fetchone()
                if row:
                    vacancy_id = row[0]
            elif title:
                cur.execute(
                    """
                    SELECT id
                    FROM vacancies
                    WHERE canonical_url IS NULL
                      AND title = %s
                      AND COALESCE(company, '') = COALESCE(%s, '')
                    ORDER BY created_at
                    LIMIT 1
                    """,
                    (title, company),
                )
                row = cur.fetchone()
                if row:
                    vacancy_id = row[0]
            if vacancy_id is None:
                cur.execute(
                    """
                    INSERT INTO vacancies (canonical_url, company, title, location, salary_raw, parse_confidence)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    RETURNING id
                    """,
                    (
                        vacancy_row.get("canonical_url"),
                        vacancy_row.get("company"),
                        vacancy_row.get("title"),
                        vacancy_row.get("location"),
                        vacancy_row.get("salary_raw"),
                        vacancy_row.get("parse_confidence"),
                    ),
                )
                vacancy_id = cur.fetchone()[0]
            vacancy_ids.append(vacancy_id)
            for src in sources:
                gmid = src.get("gmail_message_id")
                fk = src.get("fragment_key", "0")
                snippet = src.get("raw_snippet")
                if not gmid:
                    continue
                cur.execute(
                    """
                    INSERT INTO vacancy_observations (vacancy_id, gmail_message_id, fragment_key, raw_snippet)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (vacancy_id, gmail_message_id, fragment_key) DO NOTHING
                    """,
                    (vacancy_id, gmid, fk, snippet),
                )
    conn.commit()
    return vacancy_ids
