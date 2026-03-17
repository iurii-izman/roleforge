"""Tests for alert job (TASK-057)."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch
from uuid import uuid4

from roleforge.jobs.alert import (
    _format_alert_message,
    _get_eligible_alert_matches,
    run_once,
)


class TestFormatAlertMessage(unittest.TestCase):
    def test_formats_title_company_score_profile_and_url(self) -> None:
        vacancy = {"title": "Backend Engineer", "company": "Acme", "canonical_url": "https://example.com/job"}
        text = _format_alert_message(vacancy, 0.85, "primary_search")
        self.assertIn("RoleForge alert", text)
        self.assertIn("Backend Engineer", text)
        self.assertIn("at Acme", text)
        self.assertIn("Score: 0.85", text)
        self.assertIn("Profile: primary_search", text)
        self.assertIn("https://example.com/job", text)

    def test_handles_missing_fields(self) -> None:
        text = _format_alert_message({}, None, "default_mvp")
        self.assertIn("—", text)
        self.assertIn("Profile: default_mvp", text)


class TestGetEligibleAlertMatches(unittest.TestCase):
    def test_returns_empty_when_no_rows(self) -> None:
        conn = MagicMock()
        cur = MagicMock()
        cur.fetchall.return_value = []
        conn.cursor.return_value.__enter__ = lambda self: cur
        conn.cursor.return_value.__exit__ = lambda *a: None
        self.assertEqual(_get_eligible_alert_matches(conn), [])

    def test_returns_one_candidate_structure(self) -> None:
        pm_id = uuid4()
        profile_id = uuid4()
        vacancy_id = uuid4()
        v_id = uuid4()
        conn = MagicMock()
        cur = MagicMock()
        cur.fetchall.return_value = [
            (pm_id, profile_id, vacancy_id, 0.82, "primary_search", v_id, "https://u", "Acme", "Engineer", "Remote"),
        ]
        conn.cursor.return_value.__enter__ = lambda self: cur
        conn.cursor.return_value.__exit__ = lambda *a: None
        result = _get_eligible_alert_matches(conn)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["profile_match_id"], pm_id)
        self.assertEqual(result[0]["profile_id"], profile_id)
        self.assertEqual(result[0]["score"], 0.82)
        self.assertEqual(result[0]["profile_name"], "primary_search")
        self.assertEqual(result[0]["vacancy"]["title"], "Engineer")
        self.assertEqual(result[0]["vacancy"]["company"], "Acme")


class TestAlertJobRunOnce(unittest.TestCase):
    @patch("roleforge.jobs.alert.log_telegram_delivery")
    @patch("roleforge.jobs.alert.send_message")
    @patch("roleforge.jobs.alert.get_setting")
    @patch("roleforge.jobs.alert._get_eligible_alert_matches")
    @patch("roleforge.jobs.alert.log_job_finish")
    @patch("roleforge.jobs.alert.log_job_start")
    @patch("roleforge.jobs.alert.connect_db")
    def test_dry_run_does_not_send(
        self, connect_db, log_start, log_finish, get_eligible, get_setting, send_message, log_delivery
    ) -> None:
        pm_id = uuid4()
        get_eligible.return_value = [
            {
                "profile_match_id": pm_id,
                "profile_id": uuid4(),
                "vacancy_id": uuid4(),
                "score": 0.85,
                "profile_name": "p",
                "vacancy": {"title": "T", "company": "C", "canonical_url": ""},
            },
        ]
        connect_db.return_value = MagicMock()
        log_start.return_value = uuid4()

        result = run_once(dry_run=True)

        self.assertTrue(result.get("dry_run"))
        self.assertEqual(result["eligible_count"], 1)
        self.assertIn("preview", result)
        send_message.assert_not_called()
        log_delivery.assert_not_called()
        log_finish.assert_called_once()
        self.assertEqual(log_finish.call_args[0][2], "success")

    @patch("roleforge.jobs.alert._get_eligible_alert_matches")
    @patch("roleforge.jobs.alert.log_job_finish")
    @patch("roleforge.jobs.alert.log_job_start")
    @patch("roleforge.jobs.alert.connect_db")
    def test_no_eligible_completes_with_zero_sent(
        self, connect_db, log_start, log_finish, get_eligible
    ) -> None:
        get_eligible.return_value = []
        connect_db.return_value = MagicMock()
        log_start.return_value = uuid4()

        result = run_once(dry_run=False)

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["eligible_count"], 0)
        self.assertEqual(result["alerts_sent"], 0)
        log_finish.assert_called_once_with(
            connect_db.return_value, log_start.return_value, "success", result
        )

    @patch("roleforge.jobs.alert.log_telegram_delivery")
    @patch("roleforge.jobs.alert.send_message")
    @patch("roleforge.jobs.alert.get_setting")
    @patch("roleforge.jobs.alert._get_eligible_alert_matches")
    @patch("roleforge.jobs.alert.log_job_finish")
    @patch("roleforge.jobs.alert.log_job_start")
    @patch("roleforge.jobs.alert.connect_db")
    def test_sends_one_and_logs_delivery(
        self, connect_db, log_start, log_finish, get_eligible, get_setting, send_message, log_delivery
    ) -> None:
        pm_id = uuid4()
        get_eligible.return_value = [
            {
                "profile_match_id": pm_id,
                "profile_id": uuid4(),
                "vacancy_id": uuid4(),
                "score": 0.88,
                "profile_name": "primary_search",
                "vacancy": {"title": "Backend", "company": "Acme", "canonical_url": "https://x"},
            },
        ]
        connect_db.return_value = MagicMock()
        log_start.return_value = uuid4()
        get_setting.side_effect = lambda k: "token" if k == "TELEGRAM_BOT_TOKEN" else "chat-123" if k == "TELEGRAM_CHAT_ID" else None
        send_message.return_value = {"ok": True}

        result = run_once(dry_run=False)

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["alerts_sent"], 1)
        send_message.assert_called_once()
        log_delivery.assert_called_once()
        self.assertEqual(log_delivery.call_args[0][1], "alert")
        payload = log_delivery.call_args[0][2]
        self.assertEqual(payload["profile_match_id"], str(pm_id))
        self.assertIn("text_preview", payload)
        log_finish.assert_called_once()
        summary = log_finish.call_args[0][3]
        self.assertEqual(summary.get("alerts_sent"), 1)
