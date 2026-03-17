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


def _normalize_text(value: str | None) -> str:
    if not value:
        return ""
    return value.strip().lower()


def _tokenize(value: str | None) -> set[str]:
    """
    Very small, dependency-free tokenizer: lowercase and split on whitespace
    and simple punctuation boundaries. Good enough for keyword overlap.
    """
    if not value:
        return set()
    text = _normalize_text(value)
    # Replace a few common punctuation separators with spaces
    for ch in [",", "/", "-", "|", "(", ")", "[", "]", ":", ";"]:
        text = text.replace(ch, " ")
    return {t for t in text.split() if t}


def apply_hard_filters(profile_config: dict[str, Any], vacancy: dict[str, Any]) -> bool:
    """
    Return True if vacancy passes all hard filters for this profile.
    """
    hard = _get_config(profile_config, "hard_filters") or {}
    locations = hard.get("locations") or []
    if locations and vacancy.get("location"):
        loc = _normalize_text(vacancy.get("location"))
        if loc and not any(loc in (s or "").lower() for s in locations):
            return False
    exclude_companies = hard.get("exclude_companies") or []
    company = _normalize_text(vacancy.get("company"))
    if company and any(ex.lower() in company for ex in exclude_companies):
        return False
    exclude_titles = hard.get("exclude_titles") or []
    title = _normalize_text(vacancy.get("title"))
    if title and any(ex.lower() in title for ex in exclude_titles):
        return False
    min_conf = hard.get("min_parse_confidence")
    if min_conf is not None and vacancy.get("parse_confidence") is not None:
        if float(vacancy["parse_confidence"]) < float(min_conf):
            return False
    return True


def _dimension_title_match(vacancy: dict[str, Any], profile_config: dict[str, Any]) -> float:
    """
    Real title match:
    - If profile provides keywords, compute normalized overlap between title tokens and keyword tokens.
    - If no keywords configured, fall back to neutral MVP behavior: 0.5 if title present, else 0.
    """
    title = vacancy.get("title") or ""
    title_tokens = _tokenize(title)
    keywords: list[str] = _get_config(profile_config, "keywords") or []

    if not keywords:
        return 0.5 if title_tokens else 0.0

    if not title_tokens:
        return 0.0

    hits = 0
    for kw in keywords:
        kw_tokens = _tokenize(kw)
        if not kw_tokens:
            continue
        if title_tokens.intersection(kw_tokens):
            hits += 1

    if hits == 0:
        return 0.0

    return max(0.0, min(1.0, hits / float(len(keywords))))


def _dimension_company_match(vacancy: dict[str, Any], profile_config: dict[str, Any]) -> float:
    """
    Company preference scoring:
    - If company is excluded via hard_filters, always 0.0.
    - If preferred_companies configured and vacancy company matches one of them → 1.0.
    - If preferred_companies is empty:
        - 0.5 if company present (neutral-but-positive signal),
        - 0.0 if company missing.
    """
    company = _normalize_text(vacancy.get("company"))
    if not company:
        return 0.0

    hard = _get_config(profile_config, "hard_filters") or {}
    exclude_companies = hard.get("exclude_companies") or []
    if any(ex.lower() in company for ex in exclude_companies):
        return 0.0

    preferred: list[str] = _get_config(profile_config, "preferred_companies") or []
    if preferred:
        if any(p.lower() in company for p in preferred):
            return 1.0
        # Explicit preferences exist but this company is not preferred → treat as neutral 0.0
        return 0.0

    # No explicit preferences → keep previous neutral behavior.
    return 0.5


def _dimension_location_match(vacancy: dict[str, Any], profile_config: dict[str, Any]) -> float:
    """1.0 if vacancy location in profile preferred locations, else 0."""
    locations = (_get_config(profile_config, "hard_filters") or {}).get("locations") or []
    loc = _normalize_text(vacancy.get("location"))
    if not loc:
        return 0.0
    if not locations:
        return 0.5
    return 1.0 if any(loc in (s or "").lower() for s in locations) else 0.0


def _dimension_keyword_bonus(vacancy: dict[str, Any], profile_config: dict[str, Any]) -> float:
    """
    Keyword bonus based on profile skills:
    - skills: list of strings in profile.config.skills
    - text surface: title + company + location + optional description/body if present
    Score is normalized hits/len(skills), capped to [0, 1].
    If no skills configured or no text, bonus is 0.0.
    """
    skills: list[str] = _get_config(profile_config, "skills") or []
    if not skills:
        return 0.0

    surface = " ".join(
        [
            vacancy.get("title") or "",
            vacancy.get("company") or "",
            vacancy.get("location") or "",
            vacancy.get("description") or "",
            vacancy.get("body") or "",
        ]
    )
    text = _normalize_text(surface)
    if not text:
        return 0.0

    hits = 0
    for skill in skills:
        skill_norm = _normalize_text(skill)
        if not skill_norm:
            continue
        if skill_norm in text:
            hits += 1

    if hits == 0:
        return 0.0

    return max(0.0, min(1.0, hits / float(len(skills))))


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
