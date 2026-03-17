"""Tests for delivery_log (TASK-030)."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from roleforge.delivery_log import log_telegram_delivery


class TestLogTelegramDelivery(unittest.TestCase):
    def test_inserts_digest_and_returns_id(self) -> None:
        conn = MagicMock()
        cur = MagicMock()
        cur.fetchone.return_value = ("uuid-123",)
        conn.cursor.return_value.__enter__ = lambda self: cur
        conn.cursor.return_value.__exit__ = lambda *a: None
        out = log_telegram_delivery(conn, "digest", {"profile_id": "p1"})
        self.assertEqual(out, "uuid-123")
        cur.execute.assert_called_once()
        self.assertIn("digest", cur.execute.call_args[0][1])
        conn.commit.assert_called_once()

    def test_queue_card_accepted(self) -> None:
        conn = MagicMock()
        cur = MagicMock()
        cur.fetchone.return_value = ("uuid-456",)
        conn.cursor.return_value.__enter__ = lambda self: cur
        conn.cursor.return_value.__exit__ = lambda *a: None
        log_telegram_delivery(conn, "queue_card", None)
        self.assertIn("queue_card", cur.execute.call_args[0][1])

    def test_alert_accepted(self) -> None:
        """TASK-058: vacancy threshold alert delivery_type."""
        conn = MagicMock()
        cur = MagicMock()
        cur.fetchone.return_value = ("uuid-alert",)
        conn.cursor.return_value.__enter__ = lambda self: cur
        conn.cursor.return_value.__exit__ = lambda *a: None
        log_telegram_delivery(conn, "alert", {"profile_id": "p1", "profile_match_id": "pm1"})
        self.assertIn("alert", cur.execute.call_args[0][1])

    def test_admin_alert_accepted(self) -> None:
        conn = MagicMock()
        cur = MagicMock()
        cur.fetchone.return_value = ("uuid-admin",)
        conn.cursor.return_value.__enter__ = lambda self: cur
        conn.cursor.return_value.__exit__ = lambda *a: None
        log_telegram_delivery(conn, "admin_alert", {"job_type": "gmail_poll", "run_id": "r1"})
        self.assertIn("admin_alert", cur.execute.call_args[0][1])

    def test_batch_accepted(self) -> None:
        """TASK-059: micro-batch delivery_type."""
        conn = MagicMock()
        cur = MagicMock()
        cur.fetchone.return_value = ("uuid-batch",)
        conn.cursor.return_value.__enter__ = lambda self: cur
        conn.cursor.return_value.__exit__ = lambda *a: None
        log_telegram_delivery(conn, "batch", {"profile_match_id": "pm1", "profile_id": "p1"})
        self.assertIn("batch", cur.execute.call_args[0][1])

    def test_invalid_delivery_type_raises(self) -> None:
        conn = MagicMock()
        with self.assertRaises(ValueError):
            log_telegram_delivery(conn, "invalid", {})
