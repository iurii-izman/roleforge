"""Tests for admin_alert consecutive-failure check (TASK-103)."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from roleforge.admin_alert import (
    CONSECUTIVE_THRESHOLD,
    _count_consecutive_failures,
    check_and_alert_consecutive_failures,
)


class TestCountConsecutiveFailures(unittest.TestCase):
    def test_empty_runs_zero(self) -> None:
        mock_cur = MagicMock()
        mock_cur.fetchall.return_value = []
        mock_conn = MagicMock()
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cur)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        self.assertEqual(_count_consecutive_failures(mock_conn, "gmail_poll"), 0)

    def test_two_failures_returns_two(self) -> None:
        mock_cur = MagicMock()
        mock_cur.fetchall.return_value = [("failure",), ("failure",)]
        mock_conn = MagicMock()
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cur)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        self.assertEqual(_count_consecutive_failures(mock_conn, "digest"), 2)

    def test_success_breaks_streak(self) -> None:
        mock_cur = MagicMock()
        mock_cur.fetchall.return_value = [("failure",), ("success",)]
        mock_conn = MagicMock()
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cur)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        self.assertEqual(_count_consecutive_failures(mock_conn, "queue"), 1)


class TestCheckAndAlertConsecutiveFailures(unittest.TestCase):
    def test_no_alert_when_count_not_threshold(self) -> None:
        mock_conn = MagicMock()
        with patch("roleforge.admin_alert._count_consecutive_failures", return_value=2):
            with patch("roleforge.runtime.get_setting") as get_setting:
                check_and_alert_consecutive_failures(mock_conn, "gmail_poll", "run-1", {"message": "err"})
                get_setting.assert_not_called()

    def test_no_alert_when_admin_chat_missing(self) -> None:
        mock_conn = MagicMock()
        with patch("roleforge.admin_alert._count_consecutive_failures", return_value=CONSECUTIVE_THRESHOLD):
            with patch("roleforge.runtime.get_setting", return_value=None):
                with patch("roleforge.admin_alert.send_message") as send_message:
                    check_and_alert_consecutive_failures(mock_conn, "gmail_poll", "run-1", {})
                    send_message.assert_not_called()

    def test_alert_sent_when_exactly_three_failures_and_config_present(self) -> None:
        mock_conn = MagicMock()
        with patch("roleforge.admin_alert._count_consecutive_failures", return_value=CONSECUTIVE_THRESHOLD):
            with patch("roleforge.runtime.get_setting", side_effect=lambda k: "token" if k == "TELEGRAM_BOT_TOKEN" else "123" if k == "TELEGRAM_ADMIN_CHAT_ID" else None):
                with patch("roleforge.admin_alert.send_message", return_value={"ok": True}) as send_message:
                    with patch("roleforge.admin_alert.log_telegram_delivery") as log_delivery:
                        check_and_alert_consecutive_failures(mock_conn, "gmail_poll", "run-99", {"message": "auth failed"})
        send_message.assert_called_once()
        log_delivery.assert_called_once()
        self.assertEqual(log_delivery.call_args[0][1], "admin_alert")
