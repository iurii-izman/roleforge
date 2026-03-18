"""
Tests for roleforge.inbox_classifier (TASK-075).

Deterministic rules only; no DB required for classification logic (mock conn for DB-dependent rules).
"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from roleforge.inbox_classifier import (
    CLASS_EMPLOYER_REPLY,
    CLASS_VACANCY_ALERT,
    classify_message,
    get_application_thread_ids,
    get_thread_message_count,
)


def _mock_conn():
    """Minimal mock connection (used when we patch get_application_thread_ids / get_thread_message_count)."""
    return MagicMock()


class TestClassifyMessage(unittest.TestCase):
    """Test classify_message with mocked DB helpers."""

    def test_rule1_thread_linked_to_application_returns_employer_reply(self) -> None:
        conn = _mock_conn()
        row = {
            "gmail_message_id": "msg-1",
            "raw_metadata": {
                "threadId": "thread-123",
                "labelIds": ["INBOX", "Label_456"],
                "headers": [{"name": "Subject", "value": "Re: Your application"}],
            },
        }
        result = classify_message(
            row, conn, intake_label_ids=["Label_456"], application_thread_ids={"thread-123"}
        )
        self.assertEqual(result["classified_as"], CLASS_EMPLOYER_REPLY)
        self.assertEqual(result["confidence"], "high")
        self.assertEqual(result["metadata"].get("rule"), "thread_linked")

    @patch("roleforge.inbox_classifier.get_thread_message_count")
    def test_rule2_intake_label_single_message_thread_returns_vacancy_alert(
        self, mock_count: MagicMock
    ) -> None:
        mock_count.return_value = 1
        conn = _mock_conn()
        row = {
            "gmail_message_id": "msg-1",
            "raw_metadata": {
                "threadId": "thread-solo",
                "labelIds": ["INBOX", "Label_Intake"],
                "headers": [{"name": "Subject", "value": "Weekly digest"}],
            },
        }
        result = classify_message(
            row, conn, intake_label_ids=["Label_Intake"], application_thread_ids=set()
        )
        self.assertEqual(result["classified_as"], CLASS_VACANCY_ALERT)
        self.assertEqual(result["confidence"], "high")
        mock_count.assert_called_once()

    def test_rule3_employer_reply_subject_returns_employer_reply_medium(self) -> None:
        conn = _mock_conn()
        row = {
            "gmail_message_id": "msg-1",
            "raw_metadata": {
                "threadId": "t1",
                "labelIds": [],
                "headers": [
                    {"name": "Subject", "value": "Re: Interview next week"},
                    {"name": "From", "value": "hr@company.com"},
                ],
            },
        }
        result = classify_message(
            row, conn, intake_label_ids=["Other"], application_thread_ids=set()
        )
        self.assertEqual(result["classified_as"], CLASS_EMPLOYER_REPLY)
        self.assertEqual(result["confidence"], "medium")

    def test_rule3_vacancy_alert_subject_returns_vacancy_alert_medium(self) -> None:
        conn = _mock_conn()
        row = {
            "gmail_message_id": "msg-1",
            "raw_metadata": {
                "threadId": "t1",
                "labelIds": [],
                "headers": [{"name": "Subject", "value": "New job match: Engineer at Acme"}],
            },
        }
        result = classify_message(
            row, conn, intake_label_ids=[], application_thread_ids=set()
        )
        self.assertEqual(result["classified_as"], CLASS_VACANCY_ALERT)
        self.assertEqual(result["confidence"], "medium")

    @patch("roleforge.inbox_classifier.get_thread_message_count")
    def test_ambiguous_returns_none_classified_as(self, mock_count: MagicMock) -> None:
        mock_count.return_value = 3
        conn = _mock_conn()
        row = {
            "gmail_message_id": "msg-1",
            "raw_metadata": {
                "threadId": "t1",
                "labelIds": ["INBOX"],
                "headers": [{"name": "Subject", "value": "Monthly newsletter"}],
            },
        }
        result = classify_message(
            row, conn, intake_label_ids=["Label_Intake"], application_thread_ids=set()
        )
        self.assertIsNone(result["classified_as"])
        self.assertTrue(result["metadata"].get("ambiguous"))


class TestGetApplicationThreadIds(unittest.TestCase):
    """Test get_application_thread_ids with mock cursor."""

    def test_returns_set_of_thread_ids(self) -> None:
        conn = MagicMock()
        cur = MagicMock()
        cur.fetchall.return_value = [("thread-a",), ("thread-b",)]
        conn.cursor.return_value.__enter__ = MagicMock(return_value=cur)
        conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        ids = get_application_thread_ids(conn)
        self.assertEqual(ids, {"thread-a", "thread-b"})

    def test_skips_none_and_empty(self) -> None:
        conn = MagicMock()
        cur = MagicMock()
        cur.fetchall.return_value = [("thread-a",), (None,), ("",)]
        conn.cursor.return_value.__enter__ = MagicMock(return_value=cur)
        conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        ids = get_application_thread_ids(conn)
        self.assertEqual(ids, {"thread-a"})


class TestGetThreadMessageCount(unittest.TestCase):
    """Test get_thread_message_count with mock cursor."""

    def test_returns_count(self) -> None:
        conn = MagicMock()
        cur = MagicMock()
        cur.fetchone.return_value = (3,)
        conn.cursor.return_value.__enter__ = MagicMock(return_value=cur)
        conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        n = get_thread_message_count(conn, "thread-1")
        self.assertEqual(n, 3)


if __name__ == "__main__":
    unittest.main()
