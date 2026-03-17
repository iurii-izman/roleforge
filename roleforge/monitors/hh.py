"""
HH.ru monitor adapter (TASK-086, EPIC-18).

Public vacancy search is used for personal market monitoring. The adapter emits
candidates in the same normalized shape as Gmail and feeds, with source keys in
vacancy_observations.feed_source_key using the convention monitor:hh:{vacancy_id}.
"""

from __future__ import annotations

import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

HH_VACANCIES_URL = "https://api.hh.ru/vacancies"
USER_AGENT = "RoleForge/1.0 personal job search"
DEFAULT_PER_PAGE = 100
DEFAULT_MAX_PAGES = 5
REQUEST_TIMEOUT_SEC = 20

_ALLOWED_QUERY_KEYS = {
    "text",
    "area",
    "schedule",
    "employment",
    "experience",
    "order_by",
    "search_field",
    "professional_role",
    "only_with_salary",
    "date_from",
}


def _format_salary(salary: dict[str, Any] | None) -> str | None:
    if not salary:
        return None
    parts: list[str] = []
    lower = salary.get("from")
    upper = salary.get("to")
    currency = salary.get("currency")
    gross = salary.get("gross")
    if lower is not None and upper is not None:
        parts.append(f"{lower}–{upper}")
    elif lower is not None:
        parts.append(f"from {lower}")
    elif upper is not None:
        parts.append(f"up to {upper}")
    if currency:
        parts.append(str(currency))
    if gross is True:
        parts.append("gross")
    elif gross is False:
        parts.append("net")
    return " ".join(parts) if parts else None


def _build_query(params: dict[str, Any], *, page: int, per_page: int, date_from: str | None) -> dict[str, Any]:
    query: dict[str, Any] = {}
    for key in _ALLOWED_QUERY_KEYS:
        value = params.get(key)
        if value in (None, ""):
            continue
        query[key] = value
    if date_from not in (None, ""):
        query["date_from"] = date_from
    query["page"] = page
    query["per_page"] = per_page
    return query


def _fetch_json(url: str) -> dict[str, Any]:
    request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    with urlopen(request, timeout=REQUEST_TIMEOUT_SEC) as response:
        raw = response.read().decode("utf-8")
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise ValueError("HH.ru API returned a non-object response")
    return payload


def _vacancy_to_candidate(vacancy: dict[str, Any], monitor_id: str) -> dict[str, Any]:
    vacancy_id = str(vacancy.get("id") or "").strip()
    employer = vacancy.get("employer") or {}
    area = vacancy.get("area") or {}
    salary = _format_salary(vacancy.get("salary"))
    title = vacancy.get("name")
    company = employer.get("name")
    location = area.get("name")
    canonical_url = vacancy.get("alternate_url") or vacancy.get("url")
    raw_snippet = " | ".join(
        part for part in [title, company, location, salary, vacancy.get("published_at")] if part
    )
    return {
        "canonical_url": canonical_url,
        "company": company,
        "title": title,
        "location": location,
        "salary_raw": salary,
        "parse_confidence": 1.0,
        "fragment_key": "0",
        "feed_source_key": f"monitor:hh:{vacancy_id or monitor_id}",
        "raw_snippet": raw_snippet[:500],
    }


def fetch_candidates(
    monitor_id: str,
    params: dict[str, Any],
    seen_source_keys: set[str],
    *,
    date_from: str | None = None,
) -> list[dict[str, Any]]:
    """
    Return HH.ru vacancy candidates in the shared normalized shape.

    The adapter uses the public vacancy search endpoint and a bounded number of
    pages. The caller can pass a date_from window; if absent, the registry params
    may already contain one.
    """
    per_page = params.get("per_page", DEFAULT_PER_PAGE)
    try:
        per_page = int(per_page)
    except (TypeError, ValueError):
        per_page = DEFAULT_PER_PAGE
    per_page = max(1, min(per_page, 100))

    max_pages = params.get("max_pages", DEFAULT_MAX_PAGES)
    try:
        max_pages = int(max_pages)
    except (TypeError, ValueError):
        max_pages = DEFAULT_MAX_PAGES
    max_pages = max(1, min(max_pages, 10))

    page = params.get("page", 0)
    try:
        page = int(page)
    except (TypeError, ValueError):
        page = 0
    page = max(0, page)

    query_date_from = date_from if date_from not in (None, "") else params.get("date_from")
    candidates: list[dict[str, Any]] = []

    for _ in range(max_pages):
        query = _build_query(params, page=page, per_page=per_page, date_from=query_date_from)
        url = f"{HH_VACANCIES_URL}?{urlencode(query)}"
        payload = _fetch_json(url)
        items = payload.get("items") or []
        if not isinstance(items, list):
            raise ValueError("HH.ru API response missing items list")
        for vacancy in items:
            if not isinstance(vacancy, dict):
                continue
            candidate = _vacancy_to_candidate(vacancy, monitor_id)
            source_key = candidate.get("feed_source_key") or ""
            if source_key in seen_source_keys:
                continue
            candidates.append(candidate)
        pages = payload.get("pages")
        if isinstance(pages, int) and page + 1 >= pages:
            break
        if len(items) < per_page:
            break
        page += 1

    return candidates
