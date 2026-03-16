"""
Log every Telegram send to telegram_deliveries for audit (TASK-030).

Review actions are already persisted in queue.apply_review_action (review_actions).
Call log_telegram_delivery after each digest or queue_card send.
"""

from __future__ import annotations

import json
from typing import Any


def log_telegram_delivery(
    conn: Any,
    delivery_type: str,
    payload: dict[str, Any] | None = None,
) -> Any:
    """
    Insert one row into telegram_deliveries. Call after sending a digest or queue card.

    delivery_type: 'digest' | 'queue_card'
    payload: optional JSON-serializable dict (e.g. profile_id, message_preview, recipient).
    Returns the inserted row id (UUID).
    """
    if delivery_type not in ("digest", "queue_card"):
        raise ValueError(f"delivery_type must be 'digest' or 'queue_card', got {delivery_type!r}")
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO telegram_deliveries (delivery_type, payload)
            VALUES (%s, %s::jsonb)
            RETURNING id
            """,
            (delivery_type, json.dumps(payload or {})),
        )
        row = cur.fetchone()
        conn.commit()
        return row[0]
