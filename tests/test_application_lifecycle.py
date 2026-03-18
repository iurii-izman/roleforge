"""
Tests for roleforge.application_lifecycle (TASK-078).

State machine and apply_application_transition; uses mocks for DB.
"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from roleforge.application_lifecycle import (
    APPLICATION_STATUSES,
    TERMINAL_STATUSES,
    apply_application_transition,
    get_current_status,
    is_allowed_transition,
)


class TestApplicationStatusConstants(unittest.TestCase):
    def test_all_eight_statuses_defined(self) -> None:
        self.assertEqual(len(APPLICATION_STATUSES), 8)
        for s in (
            "applied",
            "hr_pinged",
            "interview_scheduled",
            "offer",
            "rejected",
            "ghosted",
            "accepted",
            "declined",
        ):
            self.assertIn(s, APPLICATION_STATUSES)

    def test_terminal_statuses(self) -> None:
        self.assertEqual(TERMINAL_STATUSES, {"rejected", "ghosted", "accepted", "declined"})


class TestIsAllowedTransition(unittest.TestCase):
    def test_same_status_not_allowed(self) -> None:
        self.assertFalse(is_allowed_transition("applied", "applied"))
        self.assertFalse(is_allowed_transition("offer", "offer"))

    def test_from_terminal_not_allowed(self) -> None:
        for term in TERMINAL_STATUSES:
            self.assertFalse(is_allowed_transition(term, "applied"))
            self.assertFalse(is_allowed_transition(term, "hr_pinged"))

    def test_accepted_declined_only_from_offer(self) -> None:
        self.assertTrue(is_allowed_transition("offer", "accepted"))
        self.assertTrue(is_allowed_transition("offer", "declined"))
        self.assertFalse(is_allowed_transition("applied", "accepted"))
        self.assertFalse(is_allowed_transition("applied", "declined"))
        self.assertFalse(is_allowed_transition("interview_scheduled", "accepted"))

    def test_rejected_ghosted_from_any_non_terminal(self) -> None:
        for from_s in ("applied", "hr_pinged", "interview_scheduled", "offer"):
            self.assertTrue(is_allowed_transition(from_s, "rejected"))
            self.assertTrue(is_allowed_transition(from_s, "ghosted"))

    def test_progressive_forward_allowed(self) -> None:
        self.assertTrue(is_allowed_transition("applied", "hr_pinged"))
        self.assertTrue(is_allowed_transition("applied", "interview_scheduled"))
        self.assertTrue(is_allowed_transition("applied", "offer"))
        self.assertTrue(is_allowed_transition("hr_pinged", "interview_scheduled"))
        self.assertTrue(is_allowed_transition("hr_pinged", "offer"))
        self.assertTrue(is_allowed_transition("interview_scheduled", "offer"))

    def test_skip_ahead_allowed(self) -> None:
        self.assertTrue(is_allowed_transition("applied", "offer"))
        self.assertTrue(is_allowed_transition("hr_pinged", "offer"))

    def test_backward_not_allowed(self) -> None:
        self.assertFalse(is_allowed_transition("hr_pinged", "applied"))
        self.assertFalse(is_allowed_transition("offer", "interview_scheduled"))
        self.assertFalse(is_allowed_transition("interview_scheduled", "hr_pinged"))

    def test_invalid_status_false(self) -> None:
        self.assertFalse(is_allowed_transition("applied", "unknown"))
        self.assertFalse(is_allowed_transition("unknown", "applied"))


class TestGetCurrentStatus(unittest.TestCase):
    def test_returns_status_when_found(self) -> None:
        conn = MagicMock()
        cur = MagicMock()
        cur.fetchone.return_value = ("hr_pinged",)
        conn.cursor.return_value.__enter__ = lambda self: cur
        conn.cursor.return_value.__exit__ = lambda *a: None
        self.assertEqual(get_current_status(conn, "app-uuid"), "hr_pinged")

    def test_returns_none_when_not_found(self) -> None:
        conn = MagicMock()
        cur = MagicMock()
        cur.fetchone.return_value = None
        conn.cursor.return_value.__enter__ = lambda self: cur
        conn.cursor.return_value.__exit__ = lambda *a: None
        self.assertIsNone(get_current_status(conn, "missing-id"))


class TestApplyApplicationTransition(unittest.TestCase):
    def test_valid_transition_updates_db(self) -> None:
        conn = MagicMock()
        cur = MagicMock()
        cur.fetchone.return_value = ("applied",)
        conn.cursor.return_value.__enter__ = lambda self: cur
        conn.cursor.return_value.__exit__ = lambda *a: None
        apply_application_transition(conn, "app-1", "hr_pinged")
        cur.execute.assert_any_call(
            "SELECT status FROM applications WHERE id = %s",
            ("app-1",),
        )
        cur.execute.assert_any_call(
            """
            UPDATE applications
            SET status = %s, updated_at = now()
            WHERE id = %s
            """,
            ("hr_pinged", "app-1"),
        )
        conn.commit.assert_called_once()

    def test_invalid_status_raises(self) -> None:
        conn = MagicMock()
        with self.assertRaises(ValueError) as ctx:
            apply_application_transition(conn, "app-1", "invalid_status")
        self.assertIn("Invalid status", str(ctx.exception))

    def test_application_not_found_raises(self) -> None:
        conn = MagicMock()
        cur = MagicMock()
        cur.fetchone.return_value = None
        conn.cursor.return_value.__enter__ = lambda self: cur
        conn.cursor.return_value.__exit__ = lambda *a: None
        with self.assertRaises(ValueError) as ctx:
            apply_application_transition(conn, "missing", "hr_pinged")
        self.assertIn("not found", str(ctx.exception))

    def test_invalid_transition_raises(self) -> None:
        conn = MagicMock()
        cur = MagicMock()
        cur.fetchone.return_value = ("rejected",)  # terminal
        conn.cursor.return_value.__enter__ = lambda self: cur
        conn.cursor.return_value.__exit__ = lambda *a: None
        with self.assertRaises(ValueError) as ctx:
            apply_application_transition(conn, "app-1", "hr_pinged")
        self.assertIn("Invalid transition", str(ctx.exception))
