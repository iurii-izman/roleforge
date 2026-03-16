"""
Tests for gmail_reader.store: message_to_row and persist_messages.

Uses fixtures; persist_messages tested with mock connection (no real DB required).
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from roleforge.gmail_reader.store import message_to_row, persist_messages

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


def _load_fixture(name: str) -> dict:
    with open(FIXTURES_DIR / name, encoding="utf-8") as f:
        return json.load(f)


class TestMessageToRow(unittest.TestCase):
    """Test message_to_row parsing."""

    def test_extracts_gmail_message_id_and_metadata(self) -> None:
        msg = _load_fixture("gmail_message_full.json")
        row = message_to_row(msg)
        self.assertEqual(row["gmail_message_id"], "msg-001")
        self.assertIn("headers", row["raw_metadata"])
        self.assertEqual(row["raw_metadata"]["threadId"], "thread-1")
        self.assertEqual(row["raw_metadata"]["labelIds"], ["INBOX", "Label_123"])
        self.assertEqual(row["raw_metadata"]["snippet"], "Job alert: Senior Engineer at Acme")

    def test_decodes_body_plain_from_single_part(self) -> None:
        msg = _load_fixture("gmail_message_full.json")
        row = message_to_row(msg)
        self.assertIn("Hello Job alert body", row["body_plain"])
        self.assertIsNone(row["body_html"])

    def test_received_at_from_internal_date(self) -> None:
        msg = _load_fixture("gmail_message_full.json")
        row = message_to_row(msg)
        self.assertIsNotNone(row["received_at"])
        self.assertEqual(row["received_at"].year, 2024)  # 1710496800000 ms

    def test_multipart_html_and_plain(self) -> None:
        msg = {
            "id": "multi-1",
            "threadId": "t1",
            "labelIds": [],
            "internalDate": "1710496800000",
            "payload": {
                "headers": [],
                "parts": [
                    {"mimeType": "text/plain", "body": {"data": "SGVsbG8="}},
                    {"mimeType": "text/html", "body": {"data": "PGh0bWw+PC9odG1sPg=="}},
                ],
            },
        }
        row = message_to_row(msg)
        self.assertEqual(row["gmail_message_id"], "multi-1")
        self.assertEqual(row["body_plain"], "Hello")
        self.assertEqual(row["body_html"], "<html></html>")


class TestPersistMessages(unittest.TestCase):
    """Test persist_messages with mock connection."""

    def test_persist_messages_inserts_and_commits(self) -> None:
        msg = _load_fixture("gmail_message_full.json")
        mock_cur = MagicMock()
        mock_cur.rowcount = 1
        mock_conn = MagicMock()
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cur)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        n = persist_messages(mock_conn, [msg])
        self.assertEqual(n, 1)
        mock_conn.commit.assert_called_once()
        self.assertEqual(mock_cur.execute.call_count, 1)
        call_args = mock_cur.execute.call_args[0]
        self.assertIn("ON CONFLICT", call_args[0])
        self.assertEqual(call_args[1][0], "msg-001")

    def test_persist_messages_idempotent_do_nothing(self) -> None:
        msg = _load_fixture("gmail_message_full.json")
        mock_cur = MagicMock()
        mock_cur.rowcount = 0
        mock_conn = MagicMock()
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cur)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        n = persist_messages(mock_conn, [msg])
        self.assertEqual(n, 0)


if __name__ == "__main__":
    unittest.main()
