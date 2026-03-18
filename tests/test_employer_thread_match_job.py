"""
Tests for roleforge.jobs.employer_thread_match (TASK-077).
"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from roleforge.jobs.employer_thread_match import JOB_TYPE, run_once


class TestEmployerThreadMatchJob(unittest.TestCase):
    def test_run_once_success_logs_job_runs(self) -> None:
        mock_conn = MagicMock()
        summary = {
            "messages_processed": 2,
            "threads_linked": 1,
            "threads_skipped_already_linked": 0,
            "threads_unmatched": 1,
        }
        with patch("roleforge.jobs.employer_thread_match.connect_db", return_value=mock_conn), patch(
            "roleforge.jobs.employer_thread_match.log_job_start", return_value="run-1"
        ) as log_start, patch(
            "roleforge.jobs.employer_thread_match.log_job_finish"
        ) as log_finish, patch(
            "roleforge.jobs.employer_thread_match.run_matching", return_value=summary
        ):
            out = run_once()

        log_start.assert_called_once_with(mock_conn, JOB_TYPE)
        self.assertEqual(out["status"], "success")
        self.assertEqual(out["run_id"], "run-1")
        self.assertEqual(out["threads_linked"], 1)
        log_finish.assert_called_once()
        args = log_finish.call_args[0]
        self.assertEqual(args[2], "success")
        self.assertEqual(args[3]["threads_unmatched"], 1)

    def test_run_once_failure_logs_finish(self) -> None:
        mock_conn = MagicMock()
        with patch("roleforge.jobs.employer_thread_match.connect_db", return_value=mock_conn), patch(
            "roleforge.jobs.employer_thread_match.log_job_start", return_value="run-1"
        ), patch("roleforge.jobs.employer_thread_match.log_job_finish") as log_finish, patch(
            "roleforge.jobs.employer_thread_match.run_matching", side_effect=RuntimeError("boom")
        ):
            with self.assertRaises(RuntimeError):
                run_once()

        log_finish.assert_called_once()
        args = log_finish.call_args[0]
        self.assertEqual(args[2], "failure")
        self.assertIn("boom", args[3]["message"])

