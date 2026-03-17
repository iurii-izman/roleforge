"""Tests for batch job (TASK-059)."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch
from uuid import uuid4

from roleforge.jobs.batch import (
    _format_batch_line,
    _format_batch_message,
    _get_eligible_batch_matches,
    run_once,
)


class TestFormatBatchLine(unittest.TestCase):
    def test_formats_title_company_score_and_url(self) -> None:
        vacancy = {"title": "Backend Engineer", "company": "Acme", "canonical_url": "https://example.com/job"}
        line = _format_batch_line(vacancy, 0.65)
        self.assertIn("Backend Engineer", line)
        self.assertIn("at Acme", line)
        self.assertIn("0.65", line)
        self.assertIn("https://example.com/job", line)

    def test_handles_missing_fields(self) -> None:
        line = _format_batch_line({}, None)
        self.assertIn("—", line)


class TestFormatBatchMessage(unittest.TestCase):
    def test_builds_message_with_profile_and_items(self) -> None:
        items = [
            {"vacancy": {"title": "A", "company": "C1", "canonical_url": ""}, "score": 0.6},
            {"vacancy": {"title": "B", "company": "C2"}, "score": 0.55},
        ]
        text = _format_batch_message("primary_search", items)
        self.assertIn("RoleForge batch", text)
        self.assertIn("Profile: primary_search", text)
        self.assertIn("A", text)
        self.assertIn("B", text)


class TestGetEligibleBatchMatches(unittest.TestCase):
    def test_returns_empty_when_no_rows(self) -> None:
        conn = MagicMock()
        cur = MagicMock()
        cur.fetchall.return_value = []
        conn.cursor.return_value.__enter__ = lambda self: cur
        conn.cursor.return_value.__exit__ = lambda *a: None
        self.assertEqual(_get_eligible_batch_matches(conn), [])

    def test_returns_candidates_in_batch_band(self) -> None:
        pm_id = uuid4()
        profile_id = uuid4()
        vacancy_id = uuid4()
        v_id = uuid4()
        conn = MagicMock()
        cur = MagicMock()
        cur.fetchall.return_value = [
            (pm_id, profile_id, vacancy_id, 0.65, "primary_search", v_id, "https://u", "Acme", "Engineer", "Remote"),
        ]
        conn.cursor.return_value.__enter__ = lambda self: cur
        conn.cursor.return_value.__exit__ = lambda *a: None
        result = _get_eligible_batch_matches(conn)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["profile_match_id"], pm_id)
        self.assertEqual(result[0]["score"], 0.65)
        self.assertEqual(result[0]["profile_name"], "primary_search")
        self.assertEqual(result[0]["vacancy"]["title"], "Engineer")


class TestBatchJobRunOnce(unittest.TestCase):
    @patch("roleforge.jobs.batch.log_telegram_delivery")
    @patch("roleforge.jobs.batch.send_message")
    @patch("roleforge.jobs.batch.get_setting")
    @patch("roleforge.jobs.batch._get_eligible_batch_matches")
    @patch("roleforge.jobs.batch.log_job_finish")
    @patch("roleforge.jobs.batch.log_job_start")
    @patch("roleforge.jobs.batch.connect_db")
    def test_dry_run_does_not_send(
        self, connect_db, log_start, log_finish, get_eligible, get_setting, send_message, log_delivery
    ) -> None:
        get_eligible.return_value = [
            {
                "profile_match_id": uuid4(),
                "profile_id": uuid4(),
                "vacancy_id": uuid4(),
                "score": 0.65,
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

    @patch("roleforge.jobs.batch._get_eligible_batch_matches")
    @patch("roleforge.jobs.batch.log_job_finish")
    @patch("roleforge.jobs.batch.log_job_start")
    @patch("roleforge.jobs.batch.connect_db")
    def test_no_eligible_completes_with_zero_sent(
        self, connect_db, log_start, log_finish, get_eligible
    ) -> None:
        get_eligible.return_value = []
        connect_db.return_value = MagicMock()
        log_start.return_value = uuid4()

        result = run_once(dry_run=False)

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["eligible_count"], 0)
        self.assertEqual(result["batches_sent"], 0)
        self.assertEqual(result["matches_sent"], 0)
        log_finish.assert_called_once()

    @patch("roleforge.jobs.batch.log_telegram_delivery")
    @patch("roleforge.jobs.batch.send_message")
    @patch("roleforge.jobs.batch.get_setting")
    @patch("roleforge.jobs.batch._get_eligible_batch_matches")
    @patch("roleforge.jobs.batch.log_job_finish")
    @patch("roleforge.jobs.batch.log_job_start")
    @patch("roleforge.jobs.batch.connect_db")
    def test_sends_one_batch_and_logs_per_match(
        self, connect_db, log_start, log_finish, get_eligible, get_setting, send_message, log_delivery
    ) -> None:
        pm_id = uuid4()
        get_eligible.return_value = [
            {
                "profile_match_id": pm_id,
                "profile_id": uuid4(),
                "vacancy_id": uuid4(),
                "score": 0.7,
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
        self.assertEqual(result["batches_sent"], 1)
        self.assertEqual(result["matches_sent"], 1)
        send_message.assert_called_once()
        log_delivery.assert_called_once()
        self.assertEqual(log_delivery.call_args[0][1], "batch")
        payload = log_delivery.call_args[0][2]
        self.assertEqual(payload["profile_match_id"], str(pm_id))
        log_finish.assert_called_once()
        summary = log_finish.call_args[0][3]
        self.assertEqual(summary.get("batches_sent"), 1)
        self.assertEqual(summary.get("matches_sent"), 1)
