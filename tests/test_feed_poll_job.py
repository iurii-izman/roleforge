"""Tests for feed_poll job (TASK-047)."""

from __future__ import annotations

import os
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from roleforge.jobs.feed_poll import run_once


class TestFeedPollJob(unittest.TestCase):
    @patch("roleforge.jobs.feed_poll.connect_db")
    @patch("roleforge.jobs.feed_poll.get_enabled_feeds")
    @patch("roleforge.jobs.feed_poll.log_job_start")
    @patch("roleforge.jobs.feed_poll.log_job_finish")
    def test_no_enabled_feeds_returns_success_summary(
        self, log_finish, log_start, get_feeds, connect_db
    ) -> None:
        get_feeds.return_value = []
        conn = MagicMock()
        connect_db.return_value = conn
        log_start.return_value = "run-id"

        result = run_once()

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["feeds_checked"], 0)
        self.assertEqual(result["entries_processed"], 0)
        self.assertEqual(result["vacancies_created"], 0)
        log_finish.assert_called_once_with(conn, "run-id", "success", result)

    @patch("roleforge.jobs.feed_poll.connect_db")
    @patch("roleforge.jobs.feed_poll.get_enabled_feeds")
    @patch("roleforge.jobs.feed_poll.log_job_start")
    @patch("roleforge.jobs.feed_poll.log_job_finish")
    def test_feed_intake_disabled_returns_early(self, log_finish, log_start, get_feeds, connect_db) -> None:
        os.environ["FEED_INTAKE_ENABLED"] = "false"
        try:
            get_feeds.return_value = []
            conn = MagicMock()
            connect_db.return_value = conn
            log_start.return_value = "run-id"

            result = run_once()

            self.assertEqual(result["status"], "success")
            self.assertEqual(result["feeds_checked"], 0)
        finally:
            os.environ.pop("FEED_INTAKE_ENABLED", None)
