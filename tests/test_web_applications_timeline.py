from __future__ import annotations

import unittest
from datetime import datetime, timezone
from unittest.mock import MagicMock


class TestApplicationsQueries(unittest.TestCase):
    def test_applications_overview_shapes_rows(self) -> None:
        from roleforge.web import queries

        conn = MagicMock()
        cur = MagicMock()
        conn.cursor.return_value.__enter__ = lambda self: cur
        conn.cursor.return_value.__exit__ = lambda *a: None

        now = datetime(2026, 3, 18, tzinfo=timezone.utc)
        cur.fetchall.return_value = [
            (
                "app-1",
                "applied",
                now,
                now,
                "Backend Dev",
                "Acme",
                "Remote",
                "https://example.com/job",
                "primary_search",
                2,
            )
        ]

        items = queries.applications_overview(conn, days=90)
        self.assertEqual(len(items), 1)
        a = items[0]
        self.assertEqual(a["application_id"], "app-1")
        self.assertEqual(a["status"], "applied")
        self.assertEqual(a["title"], "Backend Dev")
        self.assertEqual(a["company"], "Acme")
        self.assertEqual(a["profile_name"], "primary_search")
        self.assertEqual(a["interview_count"], 2)

    def test_application_timeline_includes_status_and_events(self) -> None:
        from roleforge.web import queries

        conn = MagicMock()
        cur = MagicMock()
        conn.cursor.return_value.__enter__ = lambda self: cur
        conn.cursor.return_value.__exit__ = lambda *a: None

        applied_at = datetime(2026, 3, 10, tzinfo=timezone.utc)
        updated_at = datetime(2026, 3, 12, tzinfo=timezone.utc)

        # First SELECT ... FROM applications ...
        cur.fetchone.return_value = (
            "app-1",
            "interview_scheduled",
            applied_at,
            updated_at,
            {},
            "Backend Dev",
            "Acme",
            "Remote",
            "https://example.com/job",
            {},
            "primary_search",
        )

        # Then employer_threads and interview_events.
        thread_row_time = datetime(2026, 3, 11, tzinfo=timezone.utc)
        interview_time = datetime(2026, 3, 13, tzinfo=timezone.utc)
        cur.fetchall.side_effect = [
            [
                ("thread-1", "acme.com", thread_row_time, {}, thread_row_time),
            ],
            [
                ("technical", interview_time, {}, interview_time),
            ],
        ]

        data = queries.application_timeline(conn, "app-1")
        assert data is not None
        app = data["application"]
        events = data["events"]

        self.assertEqual(app["application_id"], "app-1")
        self.assertEqual(app["status"], "interview_scheduled")
        # We expect at least three events: applied, status update, employer thread, interview.
        kinds = [e["kind"] for e in events]
        self.assertIn("status", kinds)
        self.assertIn("employer_thread", kinds)
        self.assertIn("interview_event", kinds)

