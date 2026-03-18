"""
Interview event extraction (TASK-079).

Deterministic-first extraction of interview-related signals from employer reply messages.
Writes are handled by the job layer; this module focuses on parsing and producing bounded,
auditable artifacts.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any


_MEETING_LINK_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\bhttps?://(?:meet\.google\.com/[a-z0-9-]+)\b", re.IGNORECASE),
    re.compile(r"\bhttps?://(?:teams\.microsoft\.com/l/meetup-join/[^\s>]+)\b", re.IGNORECASE),
    re.compile(r"\bhttps?://(?:zoom\.us/j/\d+)(?:\?[^\s>]+)?\b", re.IGNORECASE),
    re.compile(r"\bhttps?://(?:[^/\s>]+\.)?(?:webex\.com/meet/[^\s>]+)\b", re.IGNORECASE),
    re.compile(r"\bhttps?://(?:calendar\.google\.com/calendar/[^\s>]+)\b", re.IGNORECASE),
]

_INTERVIEW_SIGNAL_RE = re.compile(
    r"\b("
    r"interview|interviewing|invite|invitation|schedule|scheduled|reschedule|"
    r"calendar|meeting|meet\s+with|call|phone\s+screen|screening|technical\s+screen|"
    r"assessment|take[- ]home|coding\s+challenge|panel|onsite|offer"
    r")\b",
    re.IGNORECASE,
)

_EVENT_TYPE_RULES: list[tuple[str, re.Pattern[str]]] = [
    ("offer", re.compile(r"\boffer\b", re.IGNORECASE)),
    ("assessment", re.compile(r"\b(assessment|take[- ]home|coding\s+challenge|homework)\b", re.IGNORECASE)),
    ("panel", re.compile(r"\b(panel|onsite)\b", re.IGNORECASE)),
    ("technical", re.compile(r"\b(technical|coding|pairing|system\s+design)\b", re.IGNORECASE)),
    ("reference", re.compile(r"\b(reference|referee)\b", re.IGNORECASE)),
    ("hr_call", re.compile(r"\b(hr|recruiter|screen|intro|phone\s+screen|call)\b", re.IGNORECASE)),
]

_ISO_DATETIME_RE = re.compile(
    r"\b(20\d{2}-\d{2}-\d{2})"
    r"(?:[ T](\d{2}:\d{2})(?::\d{2})?)?"
    r"(?:\s*(Z|[+-]\d{2}:?\d{2}))?\b"
)
_DMY_DATE_RE = re.compile(r"\b(\d{1,2})[/.](\d{1,2})[/.](20\d{2})\b")
_TIME_RE = re.compile(r"\b(\d{1,2}):(\d{2})\s*(AM|PM)?\b", re.IGNORECASE)
_MONTH_NAME_RE = re.compile(
    r"\b("
    r"jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|"
    r"jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?"
    r")\s+(\d{1,2})(?:st|nd|rd|th)?"
    r"(?:,)?\s+(20\d{2})\b",
    re.IGNORECASE,
)
_MONTHS: dict[str, int] = {
    "jan": 1,
    "january": 1,
    "feb": 2,
    "february": 2,
    "mar": 3,
    "march": 3,
    "apr": 4,
    "april": 4,
    "may": 5,
    "jun": 6,
    "june": 6,
    "jul": 7,
    "july": 7,
    "aug": 8,
    "august": 8,
    "sep": 9,
    "september": 9,
    "oct": 10,
    "october": 10,
    "nov": 11,
    "november": 11,
    "dec": 12,
    "december": 12,
}

_TZ_HINTS: dict[str, timezone] = {
    "utc": timezone.utc,
    "gmt": timezone.utc,
}


@dataclass(frozen=True)
class InterviewEventCandidate:
    event_type: str
    scheduled_at: datetime | None
    meeting_link: str | None
    date_text: str | None
    signal_text: str

    def to_notes(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "signal_text": self.signal_text[:500],
        }
        if self.meeting_link:
            out["meeting_link"] = self.meeting_link[:500]
        if self.date_text:
            out["date_text"] = self.date_text[:200]
        return out


def has_interview_signal(subject: str, body_plain: str) -> bool:
    text = f"{subject}\n{body_plain}".strip()
    if not text:
        return False
    return _INTERVIEW_SIGNAL_RE.search(text) is not None or bool(find_meeting_links(text))


def find_meeting_links(text: str) -> list[str]:
    links: list[str] = []
    for pat in _MEETING_LINK_PATTERNS:
        for m in pat.finditer(text or ""):
            url = m.group(0).rstrip(").,;>")
            if url and url not in links:
                links.append(url)
    return links[:3]


def _pick_event_type(subject: str, body_plain: str) -> str:
    text = f"{subject}\n{body_plain}"
    for event_type, pat in _EVENT_TYPE_RULES:
        if pat.search(text):
            return event_type
    return "other"


def _parse_time_near(text: str, start_idx: int) -> tuple[int, int, int] | None:
    window = text[start_idx : min(len(text), start_idx + 120)]
    m = _TIME_RE.search(window)
    if not m:
        return None
    hour = int(m.group(1))
    minute = int(m.group(2))
    ampm = (m.group(3) or "").lower()
    if ampm == "pm" and hour < 12:
        hour += 12
    if ampm == "am" and hour == 12:
        hour = 0
    if 0 <= hour <= 23 and 0 <= minute <= 59:
        return hour, minute, 0
    return None


def _timezone_hint(text: str) -> timezone:
    lowered = (text or "").lower()
    for k, tz in _TZ_HINTS.items():
        if re.search(rf"\b{k}\b", lowered):
            return tz
    return timezone.utc


def _parse_iso_datetime(text: str) -> tuple[datetime | None, str | None]:
    m = _ISO_DATETIME_RE.search(text or "")
    if not m:
        return None, None
    date_s = m.group(1)
    time_s = m.group(2)
    tz_s = m.group(3)
    if time_s:
        iso = f"{date_s}T{time_s}"
    else:
        iso = f"{date_s}T00:00"
    if tz_s:
        tz_norm = tz_s.replace("Z", "+00:00")
        if len(tz_norm) == 5 and tz_norm[3] != ":":
            tz_norm = tz_norm[:3] + ":" + tz_norm[3:]
        iso = iso + tz_norm
    try:
        dt = datetime.fromisoformat(iso)
    except ValueError:
        return None, m.group(0)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=_timezone_hint(text))
    return dt, m.group(0)


def _parse_dmy_datetime(text: str) -> tuple[datetime | None, str | None]:
    m = _DMY_DATE_RE.search(text or "")
    if not m:
        return None, None
    day = int(m.group(1))
    month = int(m.group(2))
    year = int(m.group(3))
    time_parts = _parse_time_near(text, m.start())
    hour, minute, second = time_parts or (0, 0, 0)
    try:
        dt = datetime(year, month, day, hour, minute, second, tzinfo=_timezone_hint(text))
    except ValueError:
        return None, m.group(0)
    return dt, m.group(0)


def _parse_month_name_datetime(text: str) -> tuple[datetime | None, str | None]:
    m = _MONTH_NAME_RE.search(text or "")
    if not m:
        return None, None
    month_name = (m.group(1) or "").lower()
    month = _MONTHS.get(month_name[:3], _MONTHS.get(month_name, 0))
    day = int(m.group(2))
    year = int(m.group(3))
    time_parts = _parse_time_near(text, m.start())
    hour, minute, second = time_parts or (0, 0, 0)
    if month <= 0:
        return None, m.group(0)
    try:
        dt = datetime(year, month, day, hour, minute, second, tzinfo=_timezone_hint(text))
    except ValueError:
        return None, m.group(0)
    return dt, m.group(0)


def extract_interview_event(subject: str, body_plain: str) -> InterviewEventCandidate | None:
    """
    Extract one bounded interview event candidate from a message.

    Deterministic-only: extracts meeting links and one best-effort scheduled_at candidate.
    If no interview signal exists, returns None.
    """
    subject = (subject or "").strip()
    body_plain = (body_plain or "").strip()
    if not has_interview_signal(subject, body_plain):
        return None

    text = f"{subject}\n{body_plain}"
    event_type = _pick_event_type(subject, body_plain)
    links = find_meeting_links(text)
    scheduled_at: datetime | None = None
    date_text: str | None = None
    for parser in (_parse_iso_datetime, _parse_month_name_datetime, _parse_dmy_datetime):
        scheduled_at, date_text = parser(text)
        if scheduled_at is not None:
            break

    # Always return a candidate when the signal exists, even if scheduled_at is unknown yet.
    signal = _INTERVIEW_SIGNAL_RE.search(text)
    signal_text = signal.group(0) if signal else ("meeting_link" if links else "signal")
    return InterviewEventCandidate(
        event_type=event_type,
        scheduled_at=scheduled_at,
        meeting_link=links[0] if links else None,
        date_text=date_text,
        signal_text=signal_text,
    )

