"""
Tests for queue card formatting and review actions (TASK-029).
"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from roleforge.queue import (
    ACTION_TO_STATE,
    VALID_ACTIONS,
    apply_review_action,
    format_queue_card,
    get_next_queue_match,
)


class TestFormatQueueCard(unittest.TestCase):
    def test_format_queue_card_includes_title_company_score(self) -> None:
        match = {"score": 0.75, "explainability": None}
        vacancy = {"title": "Backend Dev", "company": "Acme", "location": "Remote", "canonical_url": "https://example.com/job"}
        text = format_queue_card(match, vacancy, profile_name="primary_search")
        self.assertIn("Backend Dev", text)
        self.assertIn("Acme", text)
        self.assertIn("0.75", text)
        self.assertIn("https://example.com/job", text)
        self.assertIn("Remote", text)
        self.assertIn("Profile: primary_search", text)

    def test_format_queue_card_with_positive_factors(self) -> None:
        match = {"score": 0.8, "explainability": {"positive_factors": ["title_match", "location_match"]}}
        vacancy = {"title": "Engineer", "company": "Foo"}
        text = format_queue_card(match, vacancy)
        self.assertIn("Why in queue", text)

    def test_format_queue_card_shows_position_and_profile(self) -> None:
        match = {
            "score": 0.6,
            "queue_position": 2,
            "queue_total": 5,
            "explainability": None,
        }
        vacancy = {"title": "Dev", "company": "Bar", "canonical_url": "https://x.co"}
        text = format_queue_card(match, vacancy, profile_name="stretch_geo")
        self.assertIn("Queue: 2 of 5", text)
        self.assertIn("Profile: stretch_geo", text)


class TestApplyReviewAction(unittest.TestCase):
    def test_action_to_state_mapping(self) -> None:
        self.assertEqual(ACTION_TO_STATE["shortlist"], "shortlisted")
        self.assertEqual(ACTION_TO_STATE["ignore"], "ignored")
        self.assertEqual(ACTION_TO_STATE["applied"], "applied")

    def test_valid_actions_include_all_six(self) -> None:
        self.assertIn("open", VALID_ACTIONS)
        self.assertIn("next", VALID_ACTIONS)
        self.assertEqual(len(VALID_ACTIONS), 6)

    def test_apply_review_action_inserts_and_updates(self) -> None:
        conn = MagicMock()
        cur = MagicMock()
        conn.cursor.return_value.__enter__ = lambda self: cur
        conn.cursor.return_value.__exit__ = lambda *a: None
        apply_review_action(conn, "match-uuid-123", "shortlist")
        cur.execute.assert_any_call(
            "INSERT INTO review_actions (profile_match_id, action) VALUES (%s, %s)",
            ("match-uuid-123", "shortlist"),
        )
        cur.execute.assert_any_call(
            "UPDATE profile_matches SET state = %s, updated_at = now() WHERE id = %s",
            ("shortlisted", "match-uuid-123"),
        )
        conn.commit.assert_called_once()

    def test_apply_open_only_inserts_no_state_update(self) -> None:
        conn = MagicMock()
        cur = MagicMock()
        conn.cursor.return_value.__enter__ = lambda self: cur
        conn.cursor.return_value.__exit__ = lambda *a: None
        apply_review_action(conn, "m1", "open")
        self.assertEqual(cur.execute.call_count, 1)
        conn.commit.assert_called_once()

    def test_apply_review_action_invalid_raises(self) -> None:
        conn = MagicMock()
        with self.assertRaises(ValueError):
            apply_review_action(conn, "m1", "invalid_action")


class TestGetNextQueueMatch(unittest.TestCase):
    def test_returns_none_when_no_rows(self) -> None:
        conn = MagicMock()
        cur = MagicMock()
        cur.fetchone.return_value = None
        conn.cursor.return_value.__enter__ = lambda self: cur
        conn.cursor.return_value.__exit__ = lambda *a: None
        out = get_next_queue_match(conn, "profile-uuid")
        self.assertIsNone(out)
        cur.execute.assert_called_once()

    def test_returns_match_and_vacancy_when_row_exists(self) -> None:
        conn = MagicMock()
        cur = MagicMock()
        # id, profile_id, vacancy_id, score, state, explainability, review_rank,
        # v_id, canonical_url, company, title, location, queue_position, queue_total
        cur.fetchone.return_value = (
            "pm-id",
            "profile-id",
            "vacancy-id",
            0.7,
            "new",
            None,
            0,
            "v-id",
            "https://job.url",
            "Company",
            "Title",
            "Berlin",
            1,
            5,
        )
        conn.cursor.return_value.__enter__ = lambda self: cur
        conn.cursor.return_value.__exit__ = lambda *a: None
        out = get_next_queue_match(conn, "profile-uuid")
        self.assertIsNotNone(out)
        self.assertEqual(out["match"]["id"], "pm-id")
        self.assertEqual(out["match"]["score"], 0.7)
        self.assertEqual(out["vacancy"]["title"], "Title")
        self.assertEqual(out["vacancy"]["company"], "Company")
        self.assertEqual(out["match"]["queue_position"], 1)
        self.assertEqual(out["match"]["queue_total"], 5)
