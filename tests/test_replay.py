"""Tests for replay entrypoints (TASK-038)."""

from __future__ import annotations

import unittest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from roleforge.replay import _subject_from_metadata, _message_to_candidates, replay_one_message, replay_date_window


class TestSubjectFromMetadata(unittest.TestCase):
    def test_extracts_subject(self) -> None:
        meta = {"headers": [{"name": "Subject", "value": "Job alert"}]}
        self.assertEqual(_subject_from_metadata(meta), "Job alert")

    def test_empty_for_no_headers(self) -> None:
        self.assertEqual(_subject_from_metadata({}), "")
        self.assertEqual(_subject_from_metadata(None), "")


class TestMessageToCandidates(unittest.TestCase):
    def test_adds_gmail_message_id_and_fragment_key(self) -> None:
        row = {
            "gmail_message_id": "msg1",
            "raw_metadata": {},
            "body_plain": "Title: Engineer\nhttps://example.com/job",
            "body_html": None,
        }
        candidates = _message_to_candidates(row)
        self.assertGreater(len(candidates), 0)
        for c in candidates:
            self.assertEqual(c["gmail_message_id"], "msg1")
            self.assertIn("fragment_key", c)


class TestReplayOneMessage(unittest.TestCase):
    @patch("roleforge.replay.log_job_start")
    @patch("roleforge.replay.log_job_finish")
    @patch("roleforge.replay.persist_deduped")
    @patch("roleforge.replay.group_by_dedup_key")
    def test_message_not_found_returns_failure(self, _g, _p, log_finish, log_start) -> None:
        log_start.return_value = "run-id"
        conn = MagicMock()
        cur = MagicMock()
        cur.fetchone.return_value = None
        conn.cursor.return_value.__enter__ = lambda self: cur
        conn.cursor.return_value.__exit__ = lambda *a: None
        out = replay_one_message(conn, "nonexistent")
        self.assertEqual(out["messages_processed"], 0)
        self.assertEqual(out["status"], "failure")
        log_finish.assert_called_once()

    @patch("roleforge.replay.log_job_start")
    @patch("roleforge.replay.log_job_finish")
    @patch("roleforge.replay.persist_deduped")
    @patch("roleforge.replay.group_by_dedup_key")
    def test_success_returns_summary(self, group_by, persist, log_finish, log_start) -> None:
        log_start.return_value = "run-id"
        group_by.return_value = [({"canonical_url": "https://x.com"}, [{"gmail_message_id": "m1", "fragment_key": "0"}])]
        persist.return_value = ["v1"]
        conn = MagicMock()
        cur = MagicMock()
        cur.fetchone.return_value = ("msg1", {}, "Body with https://job.com", None)
        cur.fetchall.return_value = []
        conn.cursor.return_value.__enter__ = lambda self: cur
        conn.cursor.return_value.__exit__ = lambda *a: None
        out = replay_one_message(conn, "msg1")
        self.assertEqual(out["messages_processed"], 1)
        self.assertEqual(out["vacancies_created"], 1)
        self.assertEqual(out["run_id"], "run-id")


class TestReplayDateWindow(unittest.TestCase):
    @patch("roleforge.replay.log_job_start")
    @patch("roleforge.replay.log_job_finish")
    @patch("roleforge.replay.persist_deduped")
    @patch("roleforge.replay.group_by_dedup_key")
    def test_empty_window_success(self, _g, _p, log_finish, log_start) -> None:
        log_start.return_value = "run-id"
        conn = MagicMock()
        cur = MagicMock()
        cur.fetchall.return_value = []
        conn.cursor.return_value.__enter__ = lambda self: cur
        conn.cursor.return_value.__exit__ = lambda *a: None
        out = replay_date_window(conn, start_date=datetime(2026, 1, 1, tzinfo=timezone.utc))
        self.assertEqual(out["messages_processed"], 0)
        self.assertEqual(out["vacancies_created"], 0)
        log_finish.assert_called_once()
