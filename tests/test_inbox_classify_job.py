"""
Tests for roleforge.jobs.inbox_classify (TASK-076).

Mocks DB connection and classifier; verifies job selects unclassified messages,
calls classifier, updates classified_as when result is non-null, and logs job_runs.
"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from roleforge.jobs.inbox_classify import (
    JOB_TYPE,
    _resolve_intake_label_ids,
    run_once,
)


class TestResolveIntakeLabelIds(unittest.TestCase):
    """Test intake label ID resolution (override, env, GMAIL_INTAKE_LABEL)."""

    def test_override_returns_override(self) -> None:
        self.assertEqual(
            _resolve_intake_label_ids(intake_label_ids_override=["L1", "L2"]),
            ["L1", "L2"],
        )

    def test_override_strips_and_filters_empty(self) -> None:
        self.assertEqual(
            _resolve_intake_label_ids(intake_label_ids_override=["  A  ", "", " B "]),
            ["A", "B"],
        )

    @patch("roleforge.jobs.inbox_classify.get_setting")
    def test_gmail_intake_label_ids_env(self, get_setting: MagicMock) -> None:
        get_setting.side_effect = lambda k: {"GMAIL_INTAKE_LABEL_IDS": "Id1,Id2"}.get(k)
        self.assertEqual(_resolve_intake_label_ids(), ["Id1", "Id2"])

    @patch("roleforge.jobs.inbox_classify.get_setting")
    def test_gmail_intake_label_fallback(self, get_setting: MagicMock) -> None:
        get_setting.side_effect = lambda k: {"GMAIL_INTAKE_LABEL": "Label_123"}.get(k)
        with patch("roleforge.jobs.inbox_classify.GmailReader", None):
            self.assertEqual(_resolve_intake_label_ids(), ["Label_123"])

    @patch("roleforge.jobs.inbox_classify.get_setting")
    def test_empty_when_no_config(self, get_setting: MagicMock) -> None:
        get_setting.return_value = None
        self.assertEqual(_resolve_intake_label_ids(), [])


class TestInboxClassifyJob(unittest.TestCase):
    """Test run_once: SELECT unclassified, classify, UPDATE when non-null."""

    def test_run_once_no_messages_success(self) -> None:
        mock_cur = MagicMock()
        mock_cur.fetchall.return_value = []
        mock_cur.rowcount = 0
        mock_conn = MagicMock()
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cur)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        with patch("roleforge.jobs.inbox_classify.connect_db", return_value=mock_conn), \
             patch("roleforge.jobs.inbox_classify.log_job_start", return_value="run-1"), \
             patch("roleforge.jobs.inbox_classify.log_job_finish") as log_finish:
            result = run_once(intake_label_ids=[])

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["messages_processed"], 0)
        self.assertEqual(result["classified_count"], 0)
        log_finish.assert_called_once()
        args = log_finish.call_args[0]
        self.assertEqual(args[2], "success")
        self.assertEqual(args[3]["messages_processed"], 0)

    def test_run_once_classifies_and_updates(self) -> None:
        row1 = ("msg-1", {"threadId": "t1", "labelIds": [], "headers": []}, "body one")
        row2 = ("msg-2", {"threadId": "t2", "labelIds": [], "headers": []}, "body two")
        select_cursor = MagicMock()
        select_cursor.execute = MagicMock()
        select_cursor.fetchall.return_value = [row1, row2]
        select_cursor.rowcount = 0
        update_cursor1 = MagicMock()
        update_cursor1.execute = MagicMock()
        update_cursor1.rowcount = 1
        update_cursor2 = MagicMock()
        update_cursor2.execute = MagicMock()
        update_cursor2.rowcount = 1

        mock_conn = MagicMock()
        mock_conn.cursor.return_value.__enter__ = MagicMock(
            side_effect=[select_cursor, update_cursor1, update_cursor2]
        )
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        def classify_side_effect(msg_row: dict, conn: object, intake_ids: list) -> dict:
            # First message -> employer_reply, second -> vacancy_alert
            if msg_row.get("gmail_message_id") == "msg-1":
                return {"classified_as": "employer_reply", "confidence": "high", "metadata": {}}
            return {"classified_as": "vacancy_alert", "confidence": "medium", "metadata": {}}

        with patch("roleforge.jobs.inbox_classify.connect_db", return_value=mock_conn), \
             patch("roleforge.jobs.inbox_classify.log_job_start", return_value="run-1"), \
             patch("roleforge.jobs.inbox_classify.log_job_finish") as log_finish, \
             patch("roleforge.jobs.inbox_classify.classify_message", side_effect=classify_side_effect):
            result = run_once(intake_label_ids=["Label_X"])

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["messages_processed"], 2)
        self.assertEqual(result["classified_count"], 2)
        self.assertEqual(result["intake_label_ids_count"], 1)
        log_finish.assert_called_once()
        args = log_finish.call_args[0]
        self.assertEqual(args[2], "success")
        self.assertEqual(args[3]["classified_count"], 2)
        # UPDATE was called with classified_as and gmail_message_id
        self.assertEqual(update_cursor1.execute.call_count, 1)
        args1 = update_cursor1.execute.call_args[0]
        self.assertIn("UPDATE gmail_messages", args1[0])
        self.assertEqual(args1[1], ("employer_reply", "msg-1"))
        self.assertEqual(update_cursor2.execute.call_args[0][1], ("vacancy_alert", "msg-2"))

    def test_run_once_ambiguous_not_updated(self) -> None:
        row1 = ("msg-amb", {"threadId": "t1", "labelIds": [], "headers": []}, "body")
        select_cursor = MagicMock()
        select_cursor.fetchall.return_value = [row1]

        mock_conn = MagicMock()
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=select_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        with patch("roleforge.jobs.inbox_classify.connect_db", return_value=mock_conn), \
             patch("roleforge.jobs.inbox_classify.log_job_start", return_value="run-1"), \
             patch("roleforge.jobs.inbox_classify.log_job_finish") as log_finish, \
             patch("roleforge.jobs.inbox_classify.classify_message", return_value={
                 "classified_as": None, "confidence": "low", "metadata": {"ambiguous": True}
             }):
            result = run_once(intake_label_ids=[])

        self.assertEqual(result["messages_processed"], 1)
        self.assertEqual(result["classified_count"], 0)
        # No UPDATE when classified_as is None (ambiguous); cursor only used for SELECT
        self.assertEqual(mock_conn.cursor.call_count, 1)

    def test_run_once_failure_logs_finish(self) -> None:
        mock_cur = MagicMock()
        mock_cur.fetchall.side_effect = RuntimeError("DB error")
        mock_conn = MagicMock()
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cur)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        with patch("roleforge.jobs.inbox_classify.connect_db", return_value=mock_conn), \
             patch("roleforge.jobs.inbox_classify.log_job_start", return_value="run-1"), \
             patch("roleforge.jobs.inbox_classify.log_job_finish") as log_finish:
            with self.assertRaises(RuntimeError):
                run_once(intake_label_ids=[])

        log_finish.assert_called_once()
        args = log_finish.call_args[0]
        self.assertEqual(args[2], "failure")
        self.assertIn("DB error", args[3]["message"])
