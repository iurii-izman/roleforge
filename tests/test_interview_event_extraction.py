from __future__ import annotations

import unittest
from datetime import datetime, timezone

from roleforge.interview_event_extraction import extract_interview_event, find_meeting_links, has_interview_signal


class TestInterviewEventExtraction(unittest.TestCase):
    def test_no_signal_returns_none(self) -> None:
        self.assertIsNone(extract_interview_event("Hello", "Just checking in."))

    def test_meeting_link_is_detected(self) -> None:
        text = "Join: https://meet.google.com/abc-defg-hij"
        links = find_meeting_links(text)
        self.assertEqual(links, ["https://meet.google.com/abc-defg-hij"])

    def test_signal_true_on_keywords(self) -> None:
        self.assertTrue(has_interview_signal("Interview invite", "Let's schedule a call."))

    def test_iso_datetime_parsed_with_utc_default(self) -> None:
        c = extract_interview_event(
            "Interview scheduled",
            "Your interview is on 2026-03-20 15:30. Meeting: https://zoom.us/j/123456789",
        )
        self.assertIsNotNone(c)
        assert c is not None
        self.assertEqual(c.event_type, "other")
        self.assertEqual(c.meeting_link, "https://zoom.us/j/123456789")
        self.assertIsInstance(c.scheduled_at, datetime)
        assert c.scheduled_at is not None
        self.assertEqual(c.scheduled_at.tzinfo, timezone.utc)
        self.assertEqual(c.scheduled_at.year, 2026)
        self.assertEqual(c.scheduled_at.month, 3)
        self.assertEqual(c.scheduled_at.day, 20)
        self.assertEqual(c.scheduled_at.hour, 15)
        self.assertEqual(c.scheduled_at.minute, 30)

    def test_month_name_datetime_parsed(self) -> None:
        c = extract_interview_event(
            "Next steps",
            "We'd like to invite you on March 21, 2026 at 3:00 PM UTC.",
        )
        self.assertIsNotNone(c)
        assert c is not None
        self.assertIsNotNone(c.scheduled_at)
        assert c.scheduled_at is not None
        self.assertEqual(c.scheduled_at, datetime(2026, 3, 21, 15, 0, tzinfo=timezone.utc))

    def test_signal_without_datetime_still_returns_candidate(self) -> None:
        c = extract_interview_event(
            "Interview invite",
            "Can you share your availability for an interview next week? Thanks.",
        )
        self.assertIsNotNone(c)
        assert c is not None
        self.assertIsNone(c.scheduled_at)

