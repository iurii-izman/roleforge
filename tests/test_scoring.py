"""
Tests for scoring engine (TASK-024): hard filters, score computation, persist.
"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from roleforge.scoring import (
    DEFAULT_WEIGHTS,
    apply_hard_filters,
    compute_score,
    persist_matches,
    score_vacancy_for_profiles,
)


class TestHardFilters(unittest.TestCase):
    """TASK-023: eligibility via hard filters."""

    def test_no_filters_pass(self) -> None:
        self.assertTrue(apply_hard_filters({}, {"title": "Dev", "company": "Acme"}))

    def test_location_filter_fail(self) -> None:
        config = {"hard_filters": {"locations": ["Remote", "Berlin"]}}
        self.assertFalse(apply_hard_filters(config, {"location": "London"}))

    def test_location_filter_pass(self) -> None:
        config = {"hard_filters": {"locations": ["Remote", "Berlin"]}}
        self.assertTrue(apply_hard_filters(config, {"location": "Remote"}))

    def test_exclude_company_fail(self) -> None:
        config = {"hard_filters": {"exclude_companies": ["Acme"]}}
        self.assertFalse(apply_hard_filters(config, {"company": "Acme Corp"}))

    def test_min_parse_confidence_fail(self) -> None:
        config = {"hard_filters": {"min_parse_confidence": 0.8}}
        self.assertFalse(apply_hard_filters(config, {"parse_confidence": 0.5}))


class TestComputeScore(unittest.TestCase):
    """Score and explainability."""

    def test_score_between_0_and_1(self) -> None:
        vacancy = {"title": "Engineer", "company": "Foo", "location": "Remote"}
        config = {"weights": DEFAULT_WEIGHTS}
        score, expl = compute_score(config, vacancy)
        self.assertGreaterEqual(score, 0.0)
        self.assertLessEqual(score, 1.0)
        self.assertIn("dimensions", expl)
        self.assertEqual(expl["score"], score)

    def test_empty_vacancy_lower_score(self) -> None:
        _, expl_empty = compute_score({}, {})
        _, expl_full = compute_score({}, {"title": "A", "company": "B", "location": "Remote"})
        self.assertLess(expl_empty["score"], expl_full["score"])

    def test_title_match_uses_profile_keywords(self) -> None:
        vacancy = {"title": "Senior Python Backend Engineer"}
        config_with_kw = {"weights": DEFAULT_WEIGHTS, "keywords": ["python", "backend"]}
        config_no_kw = {"weights": DEFAULT_WEIGHTS}

        score_with_kw, expl_with_kw = compute_score(config_with_kw, vacancy)
        score_no_kw, expl_no_kw = compute_score(config_no_kw, vacancy)

        self.assertGreater(score_with_kw, score_no_kw)
        self.assertEqual(expl_with_kw["dimensions"]["title_match"], 1.0)
        self.assertEqual(expl_no_kw["dimensions"]["title_match"], 0.5)

    def test_company_match_prefers_preferred_companies(self) -> None:
        vacancy = {"title": "Engineer", "company": "Acme Corp"}
        pref_config = {
            "weights": DEFAULT_WEIGHTS,
            "preferred_companies": ["Acme"],
        }
        neutral_config = {
            "weights": DEFAULT_WEIGHTS,
        }
        excluded_config = {
            "weights": DEFAULT_WEIGHTS,
            "hard_filters": {"exclude_companies": ["Acme"]},
        }

        score_pref, expl_pref = compute_score(pref_config, vacancy)
        score_neutral, expl_neutral = compute_score(neutral_config, vacancy)
        score_excluded, expl_excluded = compute_score(excluded_config, vacancy)

        self.assertGreater(score_pref, score_neutral)
        self.assertEqual(expl_excluded["dimensions"]["company_match"], 0.0)
        self.assertLess(score_excluded, score_neutral)

    def test_keyword_bonus_uses_skills(self) -> None:
        vacancy = {
            "title": "Senior Backend Engineer",
            "company": "Example",
            "location": "Remote",
            "description": "Stack: Python, Django, PostgreSQL, Kubernetes.",
        }
        with_skills = {
            "weights": DEFAULT_WEIGHTS,
            "skills": ["python", "django"],
        }
        without_skills = {
            "weights": DEFAULT_WEIGHTS,
            "skills": [],
        }

        _, expl_with = compute_score(with_skills, vacancy)
        _, expl_without = compute_score(without_skills, vacancy)

        self.assertGreater(
            expl_with["dimensions"]["keyword_bonus"],
            expl_without["dimensions"]["keyword_bonus"],
        )

    def test_config_with_delivery_mode_ignored_by_scoring(self) -> None:
        """TASK-056: delivery_mode in config is ignored by scoring; no error."""
        vacancy = {"title": "Engineer", "company": "Acme", "location": "Remote"}
        config = {
            "weights": DEFAULT_WEIGHTS,
            "delivery_mode": {
                "alert_enabled": False,
                "immediate_threshold": 0.80,
                "batch_enabled": False,
                "batch_threshold": 0.55,
                "batch_interval_minutes": 30,
            },
        }
        score, _ = compute_score(config, vacancy)
        self.assertGreaterEqual(score, 0.0)
        self.assertLessEqual(score, 1.0)


class TestScoreVacancyForProfiles(unittest.TestCase):
    """One vacancy, multiple profiles."""

    def test_one_profile_one_match(self) -> None:
        vacancy = {"title": "Dev", "company": "Acme"}
        profiles = [{"id": "p1", "config": {}}]
        out = score_vacancy_for_profiles(vacancy, profiles)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0][0], "p1")
        self.assertIsInstance(out[0][1], float)
        self.assertIn("dimensions", out[0][2])

    def test_hard_filter_excludes_profile(self) -> None:
        vacancy = {"location": "London"}
        profiles = [{"id": "p1", "config": {"hard_filters": {"locations": ["Remote"]}}}]
        out = score_vacancy_for_profiles(vacancy, profiles)
        self.assertEqual(len(out), 0)

    def test_one_vacancy_two_profiles(self) -> None:
        vacancy = {"title": "Dev", "company": "X"}
        profiles = [{"id": "p1", "config": {}}, {"id": "p2", "config": {}}]
        out = score_vacancy_for_profiles(vacancy, profiles)
        self.assertEqual(len(out), 2)


class TestPersistMatches(unittest.TestCase):
    """Persist profile_matches (mock conn)."""

    def test_persist_calls_insert(self) -> None:
        mock_cur = MagicMock()
        mock_conn = MagicMock()
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cur)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        n = persist_matches(mock_conn, "vac-1", [("prof-1", 0.7, {"score": 0.7, "dimensions": {}})])
        self.assertEqual(n, 1)
        mock_conn.commit.assert_called_once()
        args = mock_cur.execute.call_args[0][1]
        self.assertEqual(args[0], "prof-1")
        self.assertEqual(args[1], "vac-1")
        self.assertEqual(args[2], 0.7)
