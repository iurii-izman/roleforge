"""
Deterministic inbox classifier for gmail_messages (TASK-075).

Classifies messages as vacancy_alert, employer_reply, or other using rule-first
signals: thread linkage to applications, intake label, subject, and sender domain.
No AI in this module; ambiguous cases leave classified_as NULL for optional
AI fallback (TASK-074 contract).
"""

from __future__ import annotations

import re
from typing import Any

# Classification result: one of schema-allowed values or None for ambiguous
CLASS_VACANCY_ALERT = "vacancy_alert"
CLASS_EMPLOYER_REPLY = "employer_reply"
CLASS_OTHER = "other"

CONFIDENCE_HIGH = "high"
CONFIDENCE_MEDIUM = "medium"
CONFIDENCE_LOW = "low"

# Employer-reply subject/body markers (case-insensitive)
EMPLOYER_REPLY_PATTERNS = re.compile(
    r"\b(Re:\s*|Fwd:\s*|interview|invite|invitation|thank you for applying|"
    r"we'd like to invite|we would like to invite|next step|next steps)\b",
    re.IGNORECASE,
)
# Vacancy/job-alert subject markers
VACANCY_ALERT_PATTERNS = re.compile(
    r"\b(new job match|position at|job alert|vacancy|opening at|role at)\b",
    re.IGNORECASE,
)
# Common no-reply / bulk sender domain substrings (heuristic; we only see domain part)
NO_REPLY_DOMAIN_PATTERN = re.compile(
    r"(no-?reply|mailer|noreply|notifications?)", re.IGNORECASE
)


def _subject_from_metadata(raw_metadata: Any) -> str:
    if not raw_metadata or not isinstance(raw_metadata, dict):
        return ""
    for h in raw_metadata.get("headers") or []:
        if (h.get("name") or "").lower() == "subject":
            return str(h.get("value") or "")
    return ""


def _from_domain_from_metadata(raw_metadata: Any) -> str:
    """Extract sender domain from From or Reply-To header."""
    if not raw_metadata or not isinstance(raw_metadata, dict):
        return ""
    value = ""
    for h in raw_metadata.get("headers") or []:
        name = (h.get("name") or "").lower()
        if name in ("from", "reply-to"):
            value = str(h.get("value") or "")
            if name == "from":
                break
    if not value:
        return ""
    # Simple email extraction: <email@domain.com> or "Name" <email@domain.com> or plain email@domain.com
    match = re.search(r"<?([a-zA-Z0-9_.+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})>?", value)
    if not match:
        return ""
    addr = match.group(1)
    try:
        return addr.split("@", 1)[1].lower()
    except IndexError:
        return ""


def get_application_thread_ids(conn: Any) -> set[str]:
    """Return set of gmail_thread_id values from employer_threads (threads linked to applications)."""
    thread_ids: set[str] = set()
    with conn.cursor() as cur:
        cur.execute(
            "SELECT gmail_thread_id FROM employer_threads WHERE gmail_thread_id IS NOT NULL"
        )
        for row in cur.fetchall():
            if row[0]:
                thread_ids.add(str(row[0]).strip())
    return thread_ids


def get_thread_message_count(conn: Any, thread_id: str) -> int:
    """Return number of gmail_messages rows with this threadId in raw_metadata."""
    if not thread_id:
        return 0
    with conn.cursor() as cur:
        cur.execute(
            "SELECT COUNT(*) FROM gmail_messages WHERE raw_metadata->>'threadId' = %s",
            (thread_id.strip(),),
        )
        row = cur.fetchone()
        return int(row[0]) if row else 0


def _has_intake_label(label_ids: list[str] | None, intake_label_ids: list[str]) -> bool:
    if not intake_label_ids or not label_ids:
        return False
    label_set = {str(x).strip() for x in label_ids}
    return bool(label_set & set(intake_label_ids))


def _looks_like_no_reply_domain(domain: str) -> bool:
    """Heuristic: domain or subdomain suggests bulk/no-reply sender."""
    if not domain:
        return False
    return bool(NO_REPLY_DOMAIN_PATTERN.search(domain))


def classify_message(
    message_row: dict[str, Any],
    conn: Any,
    intake_label_ids: list[str],
    application_thread_ids: set[str] | None = None,
) -> dict[str, Any]:
    """
    Classify a single message using deterministic rules only.

    message_row: dict with at least gmail_message_id, raw_metadata (threadId, labelIds, headers).
    conn: DB connection for employer_threads and gmail_messages count.
    intake_label_ids: list of Gmail label IDs that denote intake (vacancy) messages.
    application_thread_ids: if provided, used for rule 1; otherwise fetched from conn.

    Returns dict:
      - classified_as: 'vacancy_alert' | 'employer_reply' | 'other' | None (ambiguous)
      - confidence: 'high' | 'medium' | 'low'
      - metadata: optional extra (e.g. rule_used, ambiguous).
    """
    raw = message_row.get("raw_metadata") or {}
    if isinstance(raw, str):
        import json

        try:
            raw = json.loads(raw) if raw else {}
        except (json.JSONDecodeError, TypeError):
            raw = {}
    thread_id = (raw.get("threadId") or "").strip() or None
    label_ids = raw.get("labelIds")
    if not isinstance(label_ids, list):
        label_ids = []

    subject = _subject_from_metadata(raw)
    from_domain = _from_domain_from_metadata(raw)
    body_snippet = (message_row.get("body_plain") or "")[:500]

    if application_thread_ids is None:
        application_thread_ids = get_application_thread_ids(conn)

    # Rule 1: Thread linked to application -> employer_reply (high)
    if thread_id and thread_id in application_thread_ids:
        return {
            "classified_as": CLASS_EMPLOYER_REPLY,
            "confidence": CONFIDENCE_HIGH,
            "metadata": {"rule": "thread_linked"},
        }

    # Rule 2: Intake label and single-message thread -> vacancy_alert (high)
    if _has_intake_label(label_ids, intake_label_ids) and thread_id:
        count = get_thread_message_count(conn, thread_id)
        if count <= 1:
            return {
                "classified_as": CLASS_VACANCY_ALERT,
                "confidence": CONFIDENCE_HIGH,
                "metadata": {"rule": "intake_label_single_thread"},
            }

    # Rule 3: Subject/From heuristics (medium)
    subject_lower = subject.lower()
    combined = f"{subject} {body_snippet}".lower()
    employer_match = bool(EMPLOYER_REPLY_PATTERNS.search(subject)) or bool(
        EMPLOYER_REPLY_PATTERNS.search(combined[:500])
    )
    vacancy_match = bool(VACANCY_ALERT_PATTERNS.search(subject)) or bool(
        VACANCY_ALERT_PATTERNS.search(combined[:500])
    )

    if employer_match and not _looks_like_no_reply_domain(from_domain):
        return {
            "classified_as": CLASS_EMPLOYER_REPLY,
            "confidence": CONFIDENCE_MEDIUM,
            "metadata": {"rule": "subject_heuristic"},
        }
    if vacancy_match:
        return {
            "classified_as": CLASS_VACANCY_ALERT,
            "confidence": CONFIDENCE_MEDIUM,
            "metadata": {"rule": "subject_heuristic"},
        }

    # Conflicting or no clear signal -> ambiguous (do not set; leave for AI or manual)
    return {
        "classified_as": None,
        "confidence": CONFIDENCE_LOW,
        "metadata": {"ambiguous": True},
    }
