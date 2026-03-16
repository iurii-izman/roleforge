"""
Digest message formatter: compact summary grouped by profile (TASK-028).

Input: sections (per-profile counts and highlights). Output: text for Telegram.
See docs/specs/telegram-interaction.md.
"""

from __future__ import annotations

from typing import Any

# Max length for one Telegram message (leave margin).
TELEGRAM_MAX_TEXT = 4096


def format_digest(
    sections: list[dict[str, Any]],
    *,
    title: str = "RoleForge digest",
    max_highlights_per_profile: int = 5,
    queue_placeholder: str = "Open queue: /queue",
) -> str:
    """
    Build digest text. Each section: profile_name, total, new_count, shortlisted_count,
    review_later_count, highlights (list of {title, company, score}).
    Highlights only high-priority subset (top N by score already in list).
    """
    lines = [title, ""]
    for sec in sections:
        name = sec.get("profile_name") or "Profile"
        total = int(sec.get("total") or 0)
        new = int(sec.get("new_count") or 0)
        shortlisted = int(sec.get("shortlisted_count") or 0)
        later = int(sec.get("review_later_count") or 0)
        high = int(sec.get("high_count") or 0)
        medium = int(sec.get("medium_count") or 0)
        low = int(sec.get("low_count") or 0)
        lines.append(
            f"{name}: {total} total "
            f"(bands: {high} high, {medium} medium, {low} low; "
            f"states: {new} new, {shortlisted} shortlisted, {later} later)"
        )
        highlights = sec.get("highlights") or []
        for h in highlights[:max_highlights_per_profile]:
            title_v = (h.get("title") or "—")[:50]
            company = (h.get("company") or "—")[:30]
            score = h.get("score")
            score_s = f" {score:.2f}" if score is not None else ""
            lines.append(f"  • {title_v} at {company}{score_s}")
        if total > max_highlights_per_profile:
            lines.append(f"  … and {total - max_highlights_per_profile} more in queue.")
        lines.append("")
    lines.append(queue_placeholder)
    text = "\n".join(lines)
    if len(text) > TELEGRAM_MAX_TEXT:
        text = text[: TELEGRAM_MAX_TEXT - 20] + "\n… (truncated)"
    return text


def build_digest_sections_from_matches(
    matches_by_profile: dict[str, list[dict[str, Any]]],
    *,
    top_n: int = 5,
) -> list[dict[str, Any]]:
    """
    Group matches by profile and build sections for format_digest.
    matches_by_profile: profile_name -> list of match dicts with state, score, and vacancy (title, company).
    Each match: {state, score, vacancy: {title, company}} or {state, score, title, company}.
    """
    sections = []
    for profile_name, matches in matches_by_profile.items():
        new_count = sum(1 for m in matches if m.get("state") == "new")
        shortlisted_count = sum(1 for m in matches if m.get("state") == "shortlisted")
        review_later_count = sum(1 for m in matches if m.get("state") == "review_later")
        high_count = 0
        medium_count = 0
        low_count = 0
        for m in matches:
            score = m.get("score")
            s = float(score) if score is not None else 0.0
            if s >= 0.75:
                high_count += 1
            elif s >= 0.5:
                medium_count += 1
            else:
                low_count += 1
        sorted_matches = sorted(matches, key=lambda m: (-(float(m.get("score") or 0)), str(m.get("created_at") or "")))
        highlights = []
        for m in sorted_matches[:top_n]:
            v = m.get("vacancy") or m
            highlights.append({
                "title": v.get("title"),
                "company": v.get("company"),
                "score": m.get("score"),
            })
        sections.append(
            {
                "profile_name": profile_name,
                "total": len(matches),
                "new_count": new_count,
                "shortlisted_count": shortlisted_count,
                "review_later_count": review_later_count,
                "high_count": high_count,
                "medium_count": medium_count,
                "low_count": low_count,
                "highlights": highlights,
            }
        )
    return sections
