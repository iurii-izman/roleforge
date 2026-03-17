"""Tests for monitor_poll job (TASK-087)."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from roleforge.jobs.monitor_poll import run_once


class TestMonitorPollJob(unittest.TestCase):
    @patch("roleforge.jobs.monitor_poll.connect_db")
    @patch("roleforge.jobs.monitor_poll.get_enabled_monitors")
    @patch("roleforge.jobs.monitor_poll.log_job_start")
    @patch("roleforge.jobs.monitor_poll.log_job_finish")
    def test_monitor_intake_disabled_returns_early(self, log_finish, log_start, get_monitors, connect_db) -> None:
        os.environ["MONITOR_INTAKE_ENABLED"] = "false"
        try:
            get_monitors.return_value = []
            conn = MagicMock()
            connect_db.return_value = conn
            log_start.return_value = "run-id"

            result = run_once()

            self.assertEqual(result["status"], "success")
            self.assertEqual(result["monitors_checked"], 0)
            self.assertEqual(result["entries_processed"], 0)
            log_finish.assert_called_once_with(conn, "run-id", "success", result)
        finally:
            os.environ.pop("MONITOR_INTAKE_ENABLED", None)

    @patch("roleforge.jobs.monitor_poll.persist_deduped")
    @patch("roleforge.jobs.monitor_poll.group_by_dedup_key")
    @patch("roleforge.jobs.monitor_poll.fetch_hh_candidates")
    @patch("roleforge.jobs.monitor_poll._seen_monitor_source_keys")
    @patch("roleforge.jobs.monitor_poll.get_enabled_monitors")
    @patch("roleforge.jobs.monitor_poll.log_job_start")
    @patch("roleforge.jobs.monitor_poll.log_job_finish")
    @patch("roleforge.jobs.monitor_poll.connect_db")
    def test_runs_enabled_monitors_and_logs_summary(
        self,
        connect_db,
        log_finish,
        log_start,
        get_monitors,
        seen_keys,
        fetch_candidates,
        group_by,
        persist_deduped,
    ) -> None:
        os.environ["MONITOR_INTAKE_ENABLED"] = "true"
        try:
            conn = MagicMock()
            connect_db.return_value = conn
            log_start.return_value = "run-id"
            get_monitors.return_value = [
                {
                    "id": "hh_python_remote",
                    "name": "HH.ru Python Remote",
                    "type": "hh_api",
                    "enabled": True,
                    "poll_interval_minutes": 60,
                    "params": {"text": "python backend", "per_page": 100},
                }
            ]
            seen_keys.return_value = set()
            fetch_candidates.return_value = [
                {
                    "canonical_url": "https://hh.ru/vacancy/123",
                    "company": "Acme",
                    "title": "Python Backend Engineer",
                    "location": "Remote",
                    "salary_raw": "100000–150000 RUR gross",
                    "parse_confidence": 1.0,
                    "fragment_key": "0",
                    "feed_source_key": "monitor:hh:123",
                    "raw_snippet": "Python Backend Engineer | Acme | Remote",
                }
            ]
            group_by.return_value = [
                (
                    {
                        "canonical_url": "https://hh.ru/vacancy/123",
                        "company": "Acme",
                        "title": "Python Backend Engineer",
                        "location": "Remote",
                        "salary_raw": "100000–150000 RUR gross",
                        "parse_confidence": 1.0,
                    },
                    [
                        {
                            "gmail_message_id": None,
                            "feed_source_key": "monitor:hh:123",
                            "fragment_key": "0",
                            "raw_snippet": "Python Backend Engineer | Acme | Remote",
                        }
                    ],
                )
            ]
            persist_deduped.return_value = ["vacancy-id-1"]

            result = run_once()

            self.assertEqual(result["status"], "success")
            self.assertEqual(result["monitors_checked"], 1)
            self.assertEqual(result["monitors_ran"], 1)
            self.assertEqual(result["entries_processed"], 1)
            self.assertEqual(result["vacancies_created"], 1)
            self.assertEqual(result["monitor_ids"], ["hh_python_remote"])
            self.assertEqual(result["monitor_results"][0]["monitor_id"], "hh_python_remote")
            log_finish.assert_called_once_with(conn, "run-id", "success", result)
        finally:
            os.environ.pop("MONITOR_INTAKE_ENABLED", None)
