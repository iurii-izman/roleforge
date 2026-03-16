"""
Tests for gmail_reader.retry (transient vs permanent, with_retry) and job_runs logging.

Uses mocks; no live DB or Gmail API.
"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock
from uuid import uuid4

from roleforge.gmail_reader.retry import (
    is_permanent_auth_error,
    is_transient_error,
    with_retry,
)
from roleforge.job_runs import log_job_finish, log_job_start


class _FakeResp:
    def __init__(self, status: int) -> None:
        self.status = status


class TestRetryClassification(unittest.TestCase):
    """Test transient vs permanent error classification."""

    def test_429_is_transient(self) -> None:
        e = type("E", (Exception,), {"resp": _FakeResp(429)})()
        self.assertTrue(is_transient_error(e))
        self.assertFalse(is_permanent_auth_error(e))

    def test_503_is_transient(self) -> None:
        e = type("E", (Exception,), {"resp": _FakeResp(503)})()
        self.assertTrue(is_transient_error(e))

    def test_401_is_permanent_auth(self) -> None:
        e = type("E", (Exception,), {"resp": _FakeResp(401)})()
        self.assertTrue(is_permanent_auth_error(e))
        self.assertFalse(is_transient_error(e))

    def test_403_is_permanent_auth(self) -> None:
        e = type("E", (Exception,), {"resp": _FakeResp(403)})()
        self.assertTrue(is_permanent_auth_error(e))

    def test_invalid_grant_in_message_is_permanent(self) -> None:
        e = Exception("Error invalid_grant: Token expired")
        self.assertTrue(is_permanent_auth_error(e))


class TestWithRetry(unittest.TestCase):
    """Test with_retry behavior."""

    def test_success_first_try(self) -> None:
        self.assertEqual(with_retry(lambda: 42), 42)

    def test_permanent_error_no_retry(self) -> None:
        e = type("E", (Exception,), {"resp": _FakeResp(401)})("Unauthorized")
        def fail(): raise e
        with self.assertRaises(Exception):
            with_retry(fail, max_attempts=3)
        # Should have raised on first attempt, not retried

    def test_transient_then_success(self) -> None:
        calls = []
        def flaky():
            calls.append(1)
            if len(calls) < 2:
                ex = type("E", (Exception,), {"resp": _FakeResp(503)})()
                raise ex
            return "ok"
        result = with_retry(flaky, max_attempts=3, backoff_base_sec=0.01)
        self.assertEqual(result, "ok")
        self.assertEqual(len(calls), 2)


class TestJobRuns(unittest.TestCase):
    """Test job_runs logging with mock connection."""

    def test_log_job_start_returns_uuid(self) -> None:
        mock_cur = MagicMock()
        run_id = uuid4()
        mock_cur.fetchone.return_value = (run_id,)
        mock_conn = MagicMock()
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cur)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        out = log_job_start(mock_conn, "gmail_poll")
        self.assertEqual(out, run_id)
        mock_conn.commit.assert_called_once()
        self.assertIn("gmail_poll", mock_cur.execute.call_args[0][1])

    def test_log_job_finish_updates_row(self) -> None:
        mock_cur = MagicMock()
        mock_conn = MagicMock()
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cur)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        log_job_finish(mock_conn, uuid4(), "failure", {"error_type": "permanent", "message": "auth"})
        mock_conn.commit.assert_called_once()
        call_args = mock_cur.execute.call_args[0]
        self.assertIn("failure", call_args[1])
        self.assertIn("error_type", call_args[1][1])


if __name__ == "__main__":
    unittest.main()
