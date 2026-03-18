"""
Tests for roleforge.employer_thread_matching (TASK-077).

Uses mocks for DB connection/cursors to avoid requiring a real Postgres instance.
"""

from __future__ import annotations

import json
import unittest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from roleforge import employer_thread_matching as etm


class TestThreadIdParsing(unittest.TestCase):
    def test_thread_id_from_dict_metadata(self) -> None:
        self.assertEqual(
            etm._thread_id_from_message({"raw_metadata": {"threadId": " t-1 "}}),
            "t-1",
        )

    def test_thread_id_from_json_string_metadata(self) -> None:
        raw = json.dumps({"threadId": "t-2"})
        self.assertEqual(etm._thread_id_from_message({"raw_metadata": raw}), "t-2")

    def test_thread_id_missing_returns_none(self) -> None:
        self.assertIsNone(etm._thread_id_from_message({"raw_metadata": {}}))
        self.assertIsNone(etm._thread_id_from_message({"raw_metadata": ""}))


class TestRunMatching(unittest.TestCase):
    def test_run_matching_counts_linked_skipped_unmatched(self) -> None:
        # Three messages:
        # - t_link: not linked yet, application exists -> ensure called -> linked
        # - t_skip: already linked -> skipped + last_message_at update
        # - t_unmatched: no application -> unmatched
        t0 = datetime(2026, 3, 18, 12, 0, tzinfo=timezone.utc)
        rows = [
            ("m1", {"threadId": "t_link", "headers": []}, t0),
            ("m2", {"threadId": "t_skip", "headers": []}, t0),
            ("m3", {"threadId": "t_unmatched", "headers": []}, t0),
        ]

        select_cur = MagicMock()
        select_cur.fetchall.return_value = rows

        update_cur = MagicMock()

        conn = MagicMock()
        # First cursor context manager -> SELECT; second -> UPDATE (for skipped thread)
        conn.cursor.return_value.__enter__ = MagicMock(side_effect=[select_cur, update_cur])
        conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        def already_linked_side_effect(_conn: object, thread_id: str) -> bool:
            return thread_id == "t_skip"

        def app_for_thread_side_effect(_conn: object, thread_id: str) -> str | None:
            if thread_id == "t_link":
                return "app-1"
            return None

        with patch.object(etm, "_thread_already_linked", side_effect=already_linked_side_effect), patch.object(
            etm, "_application_id_for_thread", side_effect=app_for_thread_side_effect
        ), patch.object(etm, "ensure_employer_thread_for_message", return_value="t_link") as ensure:
            summary = etm.run_matching(conn)

        self.assertEqual(summary["messages_processed"], 3)
        self.assertEqual(summary["threads_linked"], 1)
        self.assertEqual(summary["threads_skipped_already_linked"], 1)
        self.assertEqual(summary["threads_unmatched"], 1)

        ensure.assert_called_once()
        self.assertEqual(ensure.call_args[0][1]["gmail_message_id"], "m1")

        # Skipped thread with received_at should trigger last_message_at update.
        self.assertEqual(update_cur.execute.call_count, 1)
        sql = update_cur.execute.call_args[0][0]
        params = update_cur.execute.call_args[0][1]
        self.assertIn("UPDATE employer_threads", sql)
        self.assertEqual(params[1], "t_skip")

