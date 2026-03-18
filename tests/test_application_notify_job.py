from __future__ import annotations

import unittest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from roleforge.jobs.application_notify import JOB_TYPE, run_once


class TestApplicationNotifyJob(unittest.TestCase):
    def test_disabled_by_default(self) -> None:
        mock_conn = MagicMock()
        with patch("roleforge.jobs.application_notify.connect_db", return_value=mock_conn), patch(
            "roleforge.jobs.application_notify.log_job_start", return_value="run-1"
        ), patch("roleforge.jobs.application_notify.log_job_finish") as log_finish, patch(
            "roleforge.jobs.application_notify.get_setting", return_value=None
        ):
            out = run_once()
        self.assertEqual(out["status"], "success")
        self.assertFalse(out["enabled"])
        log_finish.assert_called_once()

    def test_sends_thread_and_event_updates_when_enabled(self) -> None:
        mock_conn = MagicMock()
        t0 = datetime(2026, 3, 18, 12, 0, tzinfo=timezone.utc)

        thread_row = [
            ("et-1", "app-1", "t-1", "company.com", t0, "applied", "Acme", "Backend Engineer"),
        ]
        event_row = [
            ("ie-1", "app-1", "technical", t0, {"meeting_link": "https://meet.google.com/abc-defg-hij"}, "applied", "Acme", "Backend Engineer"),
        ]

        cur_threads = MagicMock()
        cur_threads.fetchall.return_value = thread_row
        cur_events = MagicMock()
        cur_events.fetchall.return_value = event_row

        # log_job_start/finish mocked, so only two DB selects + two log_telegram_delivery inserts.
        cur_insert_1 = MagicMock()
        cur_insert_2 = MagicMock()
        mock_conn.cursor.return_value.__enter__ = MagicMock(
            side_effect=[cur_threads, cur_events, cur_insert_1, cur_insert_2]
        )
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        def get_setting_side_effect(name: str, default: str | None = None) -> str | None:
            mapping = {
                "APPLICATION_NOTIFY_ENABLED": "true",
                "TELEGRAM_BOT_TOKEN": "token",
                "TELEGRAM_APPLICATION_CHAT_ID": "chat-1",
                "TELEGRAM_CHAT_ID": "chat-1",
            }
            return mapping.get(name, default)

        with patch("roleforge.jobs.application_notify.connect_db", return_value=mock_conn), patch(
            "roleforge.jobs.application_notify.log_job_start", return_value="run-1"
        ), patch("roleforge.jobs.application_notify.log_job_finish") as log_finish, patch(
            "roleforge.jobs.application_notify.get_setting", side_effect=get_setting_side_effect
        ), patch("roleforge.jobs.application_notify.send_message", return_value={"ok": True}) as send, patch(
            "roleforge.jobs.application_notify.log_telegram_delivery", return_value="td-1"
        ) as log_delivery:
            out = run_once(limit=10)

        self.assertEqual(out["status"], "success")
        self.assertTrue(out["enabled"])
        self.assertEqual(out["threads_eligible"], 1)
        self.assertEqual(out["interview_events_eligible"], 1)
        self.assertEqual(send.call_count, 2)
        self.assertEqual(log_delivery.call_count, 2)
        log_finish.assert_called_once()

    def test_failure_logs_finish(self) -> None:
        mock_conn = MagicMock()
        with patch("roleforge.jobs.application_notify.connect_db", return_value=mock_conn), patch(
            "roleforge.jobs.application_notify.log_job_start", return_value="run-1"
        ), patch("roleforge.jobs.application_notify.log_job_finish") as log_finish, patch(
            "roleforge.jobs.application_notify.get_setting", side_effect=lambda n, d=None: "true" if n == "APPLICATION_NOTIFY_ENABLED" else None
        ):
            with self.assertRaises(RuntimeError):
                run_once()
        log_finish.assert_called_once()
        self.assertEqual(log_finish.call_args[0][2], "failure")

