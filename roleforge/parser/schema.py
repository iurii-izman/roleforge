"""
Normalized vacancy schema and validation for parser output (TASK-018).

RawCandidate matches the parser output contract; validation rules for insert.
"""

from __future__ import annotations

from typing import Any


def _valid_confidence(v: Any) -> bool:
    if v is None:
        return True
    try:
        f = float(v)
        return 0 <= f <= 1
    except (TypeError, ValueError):
        return False


def _valid_url(v: Any) -> bool:
    if v is None or not v:
        return True
    s = str(v).strip()
    return s.startswith("http://") or s.startswith("https://")


def validate_candidate(candidate: dict[str, Any]) -> list[str]:
    """
    Validate a raw candidate dict. Returns list of error messages (empty if valid).

    Checks: parse_confidence in [0, 1]; canonical_url format if present.
    """
    errors: list[str] = []
    if "parse_confidence" in candidate and candidate["parse_confidence"] is not None:
        if not _valid_confidence(candidate["parse_confidence"]):
            errors.append("parse_confidence must be in [0, 1]")
    if "canonical_url" in candidate and candidate.get("canonical_url"):
        if not _valid_url(candidate["canonical_url"]):
            errors.append("canonical_url must be http(s) or empty")
    return errors


def RawCandidate(
    *,
    canonical_url: str | None = None,
    company: str | None = None,
    title: str | None = None,
    location: str | None = None,
    salary_raw: str | None = None,
    parse_confidence: float | None = None,
    fragment_key: str = "0",
) -> dict[str, Any]:
    """Build a raw candidate dict with the schema fields (for tests and callers)."""
    return {
        "canonical_url": canonical_url,
        "company": company,
        "title": title,
        "location": location,
        "salary_raw": salary_raw,
        "parse_confidence": parse_confidence,
        "fragment_key": fragment_key,
    }
