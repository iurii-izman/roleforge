from __future__ import annotations

import unittest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from roleforge.jobs.interview_event_extract import JOB_TYPE, run_once


class TestInterviewEventExtractJob(unittest.TestCase):
    def test_run_once_success_logs_job_runs(self) -> None:
        mock_conn = MagicMock()

        # One employer-reply message linked via employer_threads.
        t0 = datetime(2026, 3, 18, 12, 0, tzinfo=timezone.utc)
        rows = [
            ("m1", {"threadId": "t-1", "headers": [{"name": "Subject", "value": "Interview invite"}]}, "Please join https://meet.google.com/abc-defg-hij", t0, "app-1"),
        ]
        select_cur = MagicMock()
        select_cur.fetchall.return_value = rows

        insert_cur = MagicMock()
        mock_conn.cursor.return_value.__enter__ = MagicMock(side_effect=[select_cur, insert_cur])
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        with patch("roleforge.jobs.interview_event_extract.connect_db", return_value=mock_conn), patch(
            "roleforge.jobs.interview_event_extract.log_job_start", return_value="run-1"
        ) as log_start, patch(
            "roleforge.jobs.interview_event_extract.log_job_finish"
        ) as log_finish:
            out = run_once(limit=10)

        log_start.assert_called_once_with(mock_conn, JOB_TYPE)
        self.assertEqual(out["status"], "success")
        self.assertEqual(out["run_id"], "run-1")
        self.assertEqual(out["messages_considered"], 1)
        self.assertEqual(out["events_created"], 1)
        log_finish.assert_called_once()
        args = log_finish.call_args[0]
        self.assertEqual(args[2], "success")
        self.assertEqual(args[3]["events_created"], 1)

        self.assertEqual(insert_cur.execute.call_count, 1)

    def test_run_once_failure_logs_finish(self) -> None:
        mock_conn = MagicMock()
        with patch("roleforge.jobs.interview_event_extract.connect_db", return_value=mock_conn), patch(
            "roleforge.jobs.interview_event_extract.log_job_start", return_value="run-1"
        ), patch("roleforge.jobs.interview_event_extract.log_job_finish") as log_finish, patch(
            "roleforge.jobs.interview_event_extract._select_unprocessed_employer_replies", side_effect=RuntimeError("boom")
        ):
            with self.assertRaises(RuntimeError):
                run_once()

        log_finish.assert_called_once()
        args = log_finish.call_args[0]
        self.assertEqual(args[2], "failure")
        self.assertIn("boom", args[3]["message"])

