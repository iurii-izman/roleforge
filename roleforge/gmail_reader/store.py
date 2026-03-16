"""
Persist raw Gmail message metadata and body variants into Postgres (gmail_messages).

TASK-013: consumes gmail_reader output; idempotent by gmail_message_id.
"""

from __future__ import annotations

import base64
from datetime import datetime, timezone
from typing import Any

def _decode_body(data: str | None) -> str:
    if not data:
        return ""
    try:
        pad = 4 - len(data) % 4
        if pad != 4:
            data = data + ("=" * pad)
        return base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")
    except Exception:
        return ""


def _headers_dict(payload: dict[str, Any]) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for h in payload.get("headers") or []:
        out.append({"name": str(h.get("name", "")), "value": str(h.get("value", ""))})
    return out


def _extract_bodies(payload: dict[str, Any]) -> tuple[str, str]:
    """Extract body_plain and body_html from Gmail API payload (single or multipart)."""
    body_plain = ""
    body_html = ""
    parts = payload.get("parts")
    if parts:
        for part in parts:
            mime = (part.get("mimeType") or "").lower()
            body = part.get("body") or {}
            data = body.get("data")
            decoded = _decode_body(data) if data else ""
            if "text/html" in mime:
                body_html = decoded
            elif "text/plain" in mime:
                body_plain = decoded
        if not body_plain and not body_html and parts:
            first = parts[0]
            body = first.get("body") or {}
            data = body.get("data")
            if data:
                body_plain = _decode_body(data)
    else:
        body = payload.get("body") or {}
        data = body.get("data")
        if data:
            decoded = _decode_body(data)
            mime = (payload.get("mimeType") or "").lower()
            if "text/html" in mime:
                body_html = decoded
            else:
                body_plain = decoded
    return body_plain, body_html


def message_to_row(msg: dict[str, Any]) -> dict[str, Any]:
    """
    Convert a Gmail API message (full format) to a row for gmail_messages.

    Returns dict with: gmail_message_id, raw_metadata (JSON-serializable), body_html, body_plain, received_at.
    """
    gmail_message_id = str(msg.get("id", ""))
    payload = msg.get("payload") or {}
    headers = _headers_dict(payload)
    raw_metadata: dict[str, Any] = {
        "id": msg.get("id"),
        "threadId": msg.get("threadId"),
        "labelIds": msg.get("labelIds"),
        "snippet": msg.get("snippet"),
        "headers": headers,
        "sizeEstimate": msg.get("sizeEstimate"),
        "historyId": msg.get("historyId"),
    }
    body_plain, body_html = _extract_bodies(payload)
    received_at = None
    internal = msg.get("internalDate")
    if internal is not None:
        try:
            ms = int(internal)
            received_at = datetime.fromtimestamp(ms / 1000.0, tz=timezone.utc)
        except (TypeError, ValueError):
            pass
    return {
        "gmail_message_id": gmail_message_id,
        "raw_metadata": raw_metadata,
        "body_html": body_html or None,
        "body_plain": body_plain or None,
        "received_at": received_at,
    }


def persist_messages(conn: Any, messages: list[dict[str, Any]]) -> int:
    """
    Insert messages into gmail_messages. Idempotent: ON CONFLICT (gmail_message_id) DO NOTHING.

    conn: psycopg2 connection (or cursor connection).
    Returns number of rows actually inserted.
    """
    import json

    inserted = 0
    with conn.cursor() as cur:
        for msg in messages:
            row = message_to_row(msg)
            cur.execute(
                """
                INSERT INTO gmail_messages (gmail_message_id, raw_metadata, body_html, body_plain, received_at)
                VALUES (%s, %s::jsonb, %s, %s, %s)
                ON CONFLICT (gmail_message_id) DO NOTHING
                """,
                (
                    row["gmail_message_id"],
                    json.dumps(row["raw_metadata"]),
                    row["body_html"],
                    row["body_plain"],
                    row["received_at"],
                ),
            )
            inserted += cur.rowcount
    conn.commit()
    return inserted
