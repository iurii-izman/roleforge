"""Tests for structured_log (TASK-102)."""

from __future__ import annotations

import json
import unittest
from io import StringIO
from unittest.mock import patch

from roleforge.structured_log import (
    _sanitize_summary,
    log_job_finish_structured,
    log_job_start_structured,
    log_struct,
)


class TestSanitizeSummary(unittest.TestCase):
    def test_empty_returns_empty(self) -> None:
        self.assertEqual(_sanitize_summary(None), {})
        self.assertEqual(_sanitize_summary({}), {})

    def test_drops_telegram_response_and_preview(self) -> None:
        s = {"message": "ok", "telegram_response": {"ok": True}, "preview": "long text"}
        out = _sanitize_summary(s)
        self.assertEqual(out, {"message": "ok"})

    def test_keeps_normal_keys(self) -> None:
        s = {"run_id": "r1", "status": "failure", "message": "auth failed"}
        self.assertEqual(_sanitize_summary(s), s)


class TestLogStruct(unittest.TestCase):
    def test_emits_valid_json_line(self) -> None:
        buf = StringIO()
        with patch("roleforge.structured_log.sys.stdout", buf):
            log_struct("info", "job_start", "started", job_type="gmail_poll", run_id="r1")
        line = buf.getvalue()
        self.assertTrue(line.endswith("\n"))
        obj = json.loads(line.strip())
        self.assertEqual(obj["level"], "info")
        self.assertEqual(obj["event"], "job_start")
        self.assertEqual(obj["job_type"], "gmail_poll")
        self.assertEqual(obj["run_id"], "r1")
        self.assertIn("ts", obj)


class TestLogJobStartStructured(unittest.TestCase):
    def test_includes_job_type_and_run_id(self) -> None:
        buf = StringIO()
        with patch("roleforge.structured_log.sys.stdout", buf):
            log_job_start_structured("digest", "run-123")
        obj = json.loads(buf.getvalue().strip())
        self.assertEqual(obj["event"], "job_start")
        self.assertEqual(obj["job_type"], "digest")
        self.assertEqual(obj["run_id"], "run-123")


class TestLogJobFinishStructured(unittest.TestCase):
    def test_success_level_info(self) -> None:
        buf = StringIO()
        with patch("roleforge.structured_log.sys.stdout", buf):
            log_job_finish_structured("queue", "run-456", "success", {"cards_sent": 1})
        obj = json.loads(buf.getvalue().strip())
        self.assertEqual(obj["level"], "info")
        self.assertEqual(obj["status"], "success")
        self.assertIn("summary", obj)

    def test_failure_level_error(self) -> None:
        buf = StringIO()
        with patch("roleforge.structured_log.sys.stdout", buf):
            log_job_finish_structured("gmail_poll", "run-789", "failure", {"message": "auth"})
        obj = json.loads(buf.getvalue().strip())
        self.assertEqual(obj["level"], "error")
        self.assertEqual(obj["status"], "failure")
