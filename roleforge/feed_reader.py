"""
Fetch RSS/Atom feeds and convert entries to vacancy candidate shape (TASK-047).

Reuses normalized schema: same candidate keys as parser output.
Entries get feed_source_key = "{feed_id}:{stable_entry_id}" for idempotency.
"""

from __future__ import annotations

import hashlib
import re
from typing import Any


def _stable_entry_id(entry: Any) -> str:
    """Prefer id, link, or title hash for idempotency."""
    eid = getattr(entry, "id", None) or getattr(entry, "guid", None)
    if eid:
        return str(eid).strip()
    link = getattr(entry, "link", None)
    if link:
        return str(link).strip()
    title = getattr(entry, "title", None) or ""
    return hashlib.sha256(str(title).encode("utf-8")).hexdigest()[:16]


def _first_link_from_content(entry: Any) -> str | None:
    """Extract first http(s) link from description/summary/content."""
    for attr in ("summary", "description", "content"):
        val = getattr(entry, attr, None)
        if not val:
            continue
        if hasattr(val, "value"):
            val = getattr(val, "value", val)
        text = str(val)
        m = re.search(r"https?://[^\s<>\"']+", text, re.IGNORECASE)
        if m:
            return m.group(0).rstrip(".,;)")
    return None


def entry_to_candidate(
    entry: Any,
    feed_id: str,
    feed_source_key: str,
) -> dict[str, Any]:
    """
    Map one feed entry to normalized candidate shape (canonical_url, title, company, etc.).

    Uses link as canonical_url; title from entry; optional company/location from content.
    """
    link = getattr(entry, "link", None) or _first_link_from_content(entry)
    title = getattr(entry, "title", None) or ""
    if isinstance(title, str):
        title = title.strip() or None
    else:
        title = None

    summary = getattr(entry, "summary", None) or getattr(entry, "description", None)
    if summary is not None and hasattr(summary, "value"):
        summary = getattr(summary, "value", summary)
    body = (summary or "").strip() if summary else ""

    company = None
    location = None
    if body:
        for pattern, key in [
            (re.compile(r"(?:company|organization)\s*[:\-]\s*(.+?)(?=\n|$)", re.IGNORECASE | re.MULTILINE), "company"),
            (re.compile(r"location\s*[:\-]\s*(.+?)(?=\n|$)", re.IGNORECASE | re.MULTILINE), "location"),
        ]:
            m = pattern.search(body)
            if m:
                if key == "company":
                    company = m.group(1).strip() or None
                else:
                    location = m.group(1).strip() or None

    parse_confidence = 0.6 if (link and title) else (0.5 if link else 0.3)
    return {
        "canonical_url": link.strip() if link else None,
        "title": title,
        "company": company,
        "location": location,
        "salary_raw": None,
        "parse_confidence": round(parse_confidence, 4),
        "fragment_key": "0",
        "feed_source_key": feed_source_key,
        "raw_snippet": (body or (title or ""))[:500],
    }


def fetch_feed(url: str) -> list[Any]:
    """
    Fetch feed and return list of entries (feedparser entries).
    """
    import feedparser  # type: ignore[import-untyped]

    parsed = feedparser.parse(url)
    return getattr(parsed, "entries", []) or []


def fetch_feed_candidates(
    feed_id: str,
    url: str,
    seen_source_keys: set[str],
) -> list[dict[str, Any]]:
    """
    Fetch feed, filter to new entries by seen_source_keys, convert to candidates.

    feed_source_key = "{feed_id}:{stable_entry_id}".
    """
    entries = fetch_feed(url)
    candidates: list[dict[str, Any]] = []
    for entry in entries:
        eid = _stable_entry_id(entry)
        source_key = f"{feed_id}:{eid}"
        if source_key in seen_source_keys:
            continue
        c = entry_to_candidate(entry, feed_id, source_key)
        candidates.append(c)
    return candidates
