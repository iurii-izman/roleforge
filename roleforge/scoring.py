"""
Shared scoring engine: score each vacancy against each profile (TASK-024).

One formula; per-profile weights and hard filters from profiles.config.
Persists profile_matches. See docs/specs/profile-schema.md and scoring-spec.md.
"""

from __future__ import annotations

from typing import Any


DEFAULT_WEIGHTS = {
    "title_match": 1.0,
    "company_match": 0.8,
    "location_match": 0.6,
    "keyword_bonus": 0.5,
}


def _get_config(config: dict[str, Any], key: str, default: Any = None) -> Any:
    return config.get(key) if config else default


def apply_hard_filters(profile_config: dict[str, Any], vacancy: dict[str, Any]) -> bool:
    """
    Return True if vacancy passes all hard filters for this profile.
    """
    hard = _get_config(profile_config, "hard_filters") or {}
    locations = hard.get("locations") or []
    if locations and vacancy.get("location"):
        loc = (vacancy.get("location") or "").strip().lower()
        if loc and not any(loc in (s or "").lower() for s in locations):
            return False
    exclude_companies = hard.get("exclude_companies") or []
    company = (vacancy.get("company") or "").strip().lower()
    if company and any(ex.lower() in company for ex in exclude_companies):
        return False
    exclude_titles = hard.get("exclude_titles") or []
    title = (vacancy.get("title") or "").strip().lower()
    if title and any(ex.lower() in title for ex in exclude_titles):
        return False
    min_conf = hard.get("min_parse_confidence")
    if min_conf is not None and vacancy.get("parse_confidence") is not None:
        if float(vacancy["parse_confidence"]) < float(min_conf):
            return False
    return True


def _dimension_title_match(vacancy: dict[str, Any], _profile: dict) -> float:
    """MVP: 0.5 if title present, else 0."""
    return 0.5 if (vacancy.get("title") or "").strip() else 0.0


def _dimension_company_match(vacancy: dict[str, Any], _profile: dict) -> float:
    """MVP: 0.5 if company present, else 0."""
    return 0.5 if (vacancy.get("company") or "").strip() else 0.0


def _dimension_location_match(vacancy: dict[str, Any], profile_config: dict[str, Any]) -> float:
    """1.0 if vacancy location in profile preferred locations, else 0."""
    locations = (_get_config(profile_config, "hard_filters") or {}).get("locations") or []
    loc = (vacancy.get("location") or "").strip().lower()
    if not loc:
        return 0.0
    if not locations:
        return 0.5
    return 1.0 if any(loc in (s or "").lower() for s in locations) else 0.0


def _dimension_keyword_bonus(_vacancy: dict[str, Any], _profile: dict) -> float:
    """MVP: 0."""
    return 0.0


def compute_score(
    profile_config: dict[str, Any],
    vacancy: dict[str, Any],
) -> tuple[float, dict[str, Any]]:
    """
    Compute score and explainability for one (profile, vacancy).
    Assumes hard filters already passed. Returns (score, explainability_dict).
    """
    weights = _get_config(profile_config, "weights") or DEFAULT_WEIGHTS
    dims = {
        "title_match": _dimension_title_match(vacancy, profile_config),
        "company_match": _dimension_company_match(vacancy, profile_config),
        "location_match": _dimension_location_match(vacancy, profile_config),
        "keyword_bonus": _dimension_keyword_bonus(vacancy, profile_config),
    }
    total = 0.0
    weight_sum = 0.0
    for k, w in weights.items():
        if k in dims and w is not None:
            total += float(w) * dims[k]
            weight_sum += float(w)
    score = total / weight_sum if weight_sum else 0.0
    score = max(0.0, min(1.0, round(score, 4)))
    positive_factors = [k for k, v in dims.items() if v is not None and float(v) > 0.2]
    negative_factors = [k for k, v in dims.items() if v is not None and float(v) == 0.0]
    explainability = {
        "dimensions": dims,
        "passed_filters": True,
        "score": score,
        "positive_factors": positive_factors,
        "negative_factors": negative_factors,
    }
    return score, explainability


def score_vacancy_for_profiles(
    vacancy: dict[str, Any],
    profiles: list[dict[str, Any]],
) -> list[tuple[Any, float, dict[str, Any]]]:
    """
    Score one vacancy against each profile. Returns list of (profile_id, score, explainability).
    Only includes profiles for which hard filters passed.
    """
    out: list[tuple[Any, float, dict[str, Any]]] = []
    for p in profiles:
        profile_id = p.get("id")
        if profile_id is None:
            continue
        config = p.get("config") or {}
        if not apply_hard_filters(config, vacancy):
            continue
        score, expl = compute_score(config, vacancy)
        out.append((profile_id, score, expl))
    return out


def persist_matches(
    conn: Any,
    vacancy_id: str,
    matches: list[tuple[str, float, dict[str, Any]]],
    *,
    review_rank_start: int = 0,
) -> int:
    """
    Insert or update profile_matches for one vacancy. Each match is (profile_id, score, explainability).
    review_rank: assign vacancy_id order + rank offset. Returns number of rows upserted.
    """
    import json
    from uuid import UUID

    count = 0
    with conn.cursor() as cur:
        for rank, (profile_id, score, explainability) in enumerate(matches):
            cur.execute(
                """
                INSERT INTO profile_matches (profile_id, vacancy_id, score, state, explainability, review_rank)
                VALUES (%s, %s, %s, 'new', %s::jsonb, %s)
                ON CONFLICT (profile_id, vacancy_id) DO UPDATE SET
                    score = EXCLUDED.score,
                    explainability = EXCLUDED.explainability,
                    review_rank = EXCLUDED.review_rank,
                    updated_at = now()
                """,
                (profile_id, vacancy_id, score, json.dumps(explainability), review_rank_start + rank),
            )
            count += 1
    conn.commit()
    return count
