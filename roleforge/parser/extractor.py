"""
Deterministic extraction of vacancy candidates from message body (TASK-017).

No LLM; pattern-based. See docs/specs/parser-behavior.md.
"""

from __future__ import annotations

import re
from typing import Any


# URL pattern; skip common non-job links
_URL_PATTERN = re.compile(
    r"https?://[^\s<>\"']+",
    re.IGNORECASE,
)
_SKIP_URL_KEYWORDS = ("unsubscribe", "track", "click", "open", "pixel", "img")

# Structured fields: "Company: X", "Title: Y", etc.
_RE_COMPANY = re.compile(r"(?:company|organization)\s*[:\-]\s*(.+?)(?=\n|$)", re.IGNORECASE | re.MULTILINE)
_RE_TITLE = re.compile(r"title\s*[:\-]\s*(.+?)(?=\n|$)", re.IGNORECASE | re.MULTILINE)
_RE_LOCATION = re.compile(r"location\s*[:\-]\s*(.+?)(?=\n|$)", re.IGNORECASE | re.MULTILINE)
_RE_SALARY = re.compile(r"salary\s*[:\-]\s*(.+?)(?=\n|$)", re.IGNORECASE | re.MULTILINE)
_NON_VACANCY_PATTERNS = (
    re.compile(r"просмотр\w*\s+ваше\s+резюме", re.IGNORECASE),
    re.compile(r"viewed\s+your\s+resume", re.IGNORECASE),
    re.compile(r"viewed\s+your\s+profile", re.IGNORECASE),
)


def _extract_urls(text: str) -> list[str]:
    urls = _URL_PATTERN.findall(text)
    out: list[str] = []
    for u in urls:
        u = u.rstrip(".,;)")
        lower = u.lower()
        if any(kw in lower for kw in _SKIP_URL_KEYWORDS):
            continue
        if u not in out:
            out.append(u)
    return out


def _extract_fields(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for pattern, key in [
        (_RE_COMPANY, "company"),
        (_RE_TITLE, "title"),
        (_RE_LOCATION, "location"),
        (_RE_SALARY, "salary_raw"),
    ]:
        m = pattern.search(text)
        if m:
            out[key] = m.group(1).strip()
    return out


def _confidence(url: bool, title: bool, company: bool) -> float:
    if url and title:
        return 0.9
    if url and company:
        return 0.85
    if title or company:
        return 0.6
    if url:
        return 0.5
    return 0.2


def _is_non_vacancy_notification(text: str, subject: str) -> bool:
    haystack = "\n".join(part for part in (subject, text) if part).strip()
    if not haystack:
        return False
    return any(pattern.search(haystack) for pattern in _NON_VACANCY_PATTERNS)


def extract_candidates(
    body_plain: str,
    body_html: str | None = None,
    subject: str = "",
    message_id: str = "",
) -> list[dict[str, Any]]:
    """
    Extract raw vacancy candidates from message body (deterministic).

    Returns list of dicts with: canonical_url, company, title, location, salary_raw,
    parse_confidence, fragment_key. Uses body_plain primarily; body_html can be used
    as fallback for URL extraction if plain is empty.
    """
    text = (body_plain or "").strip()
    if not text and body_html:
        # Minimal strip of tags for URL extraction
        text = re.sub(r"<[^>]+>", " ", body_html)
        text = re.sub(r"\s+", " ", text).strip()
    if not text and not subject:
        return []

    urls = _extract_urls(text)
    fields = _extract_fields(text)
    title_from_subject = (subject or "").strip() if subject else None
    if not fields.get("title") and title_from_subject:
        fields["title"] = title_from_subject

    if not urls and _is_non_vacancy_notification(text, subject):
        return []

    # Single-job: one or zero URLs
    if len(urls) <= 1:
        url = urls[0] if urls else None
        conf = _confidence(bool(url), bool(fields.get("title")), bool(fields.get("company")))
        return [
            {
                "canonical_url": url,
                "company": fields.get("company"),
                "title": fields.get("title"),
                "location": fields.get("location"),
                "salary_raw": fields.get("salary_raw"),
                "parse_confidence": round(conf, 4),
                "fragment_key": "0",
            }
        ]

    # Multi-job digest: one candidate per URL
    out: list[dict[str, Any]] = []
    for i, url in enumerate(urls):
        conf = _confidence(True, bool(fields.get("title") or i == 0 and title_from_subject), bool(fields.get("company")))
        out.append({
            "canonical_url": url,
            "company": fields.get("company"),
            "title": fields.get("title") or (title_from_subject if i == 0 else None),
            "location": fields.get("location"),
            "salary_raw": fields.get("salary_raw"),
            "parse_confidence": round(conf, 4),
            "fragment_key": str(i),
        })
    return out
