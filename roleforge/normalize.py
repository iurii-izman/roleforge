"""
Normalize URL, title, company, and location for dedup and scoring (TASK-019).

Strips tracking params; produces stable canonical forms for dedup keys.
"""

from __future__ import annotations

import re
import unicodedata
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse


# Query params to strip (tracking, analytics).
_STRIP_PARAMS = frozenset(
    k.lower()
    for k in (
        "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
        "fbclid", "gclid", "msclkid", "ref", "mc_cid", "mc_eid",
        "_ga", "utm_id", "utm_source_platform", "utm_creative_format",
    )
)


def normalize_url(url: str | None) -> str | None:
    """
    Return canonical URL: strip tracking params, sort remaining query, stable scheme/host/path.

    Returns None if input is empty or not http(s). Otherwise returns normalized string.
    """
    if not url or not isinstance(url, str):
        return None
    s = url.strip()
    if not s.lower().startswith(("http://", "https://")):
        return None
    try:
        parsed = urlparse(s)
        netloc = parsed.netloc.lower()
        path = parsed.path or "/"
        path = re.sub(r"/+", "/", path).rstrip("/") or "/"
        query = parse_qs(parsed.query, keep_blank_values=False)
        filtered = {k: v for k, v in query.items() if k.lower() not in _STRIP_PARAMS}
        new_query = urlencode(sorted(filtered.items()), doseq=True) if filtered else ""
        canonical = urlunparse((parsed.scheme.lower(), netloc, path, "", new_query, ""))
        return canonical
    except Exception:
        return s


def normalize_text(value: str | None) -> str | None:
    """
    Normalize title/company/location: trim, collapse whitespace, NFKC unicode.

    Returns None if input is empty. Used for display and for building dedup keys.
    """
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None
    s = unicodedata.normalize("NFKC", s)
    s = re.sub(r"\s+", " ", s)
    return s.strip() or None


def normalize_title(value: str | None) -> str | None:
    """Normalize job title (alias for normalize_text)."""
    return normalize_text(value)


def normalize_company(value: str | None) -> str | None:
    """Normalize company name (alias for normalize_text)."""
    return normalize_text(value)


def normalize_location(value: str | None) -> str | None:
    """Normalize location string (alias for normalize_text)."""
    return normalize_text(value)


def dedup_key(candidate: dict) -> tuple[str, str, str]:
    """
    Build a stable dedup key from a (possibly normalized) candidate.

    Returns (canonical_url or "", normalized_title or "", normalized_company or "").
    Prefer canonical_url for grouping; when empty, title+company can group.
    """
    url = candidate.get("canonical_url") or ""
    if isinstance(url, str) and url.strip():
        url = normalize_url(url) or url.strip()
    title = normalize_text(candidate.get("title")) or ""
    company = normalize_text(candidate.get("company")) or ""
    return (url, title, company)
