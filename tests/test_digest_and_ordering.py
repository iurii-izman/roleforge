"""
Tests for digest formatter (TASK-028) and review ordering (TASK-025).
"""

from __future__ import annotations

import unittest

from roleforge.digest import build_digest_sections_from_matches, format_digest
from roleforge.review_ordering import assign_review_ranks
from roleforge.scoring import compute_score


class TestExplainabilityFactors(unittest.TestCase):
    """TASK-025: positive/negative factors in explainability."""

    def test_explainability_has_positive_and_negative_factors(self) -> None:
        _, expl = compute_score({}, {"title": "Engineer", "company": "Acme", "location": "Remote"})
        self.assertIn("positive_factors", expl)
        self.assertIn("negative_factors", expl)
        self.assertIsInstance(expl["positive_factors"], list)
        self.assertIsInstance(expl["negative_factors"], list)


class TestReviewOrdering(unittest.TestCase):
    """TASK-025: deterministic review_rank."""

    def test_assign_review_ranks_by_score_desc(self) -> None:
        matches = [
            {"id": "a", "score": 0.3, "created_at": "2026-01-01"},
            {"id": "b", "score": 0.9, "created_at": "2026-01-02"},
            {"id": "c", "score": 0.5, "created_at": "2026-01-01"},
        ]
        out = assign_review_ranks(matches)
        self.assertEqual(len(out), 3)
        ids_by_rank = {rank: mid for mid, rank in out}
        self.assertEqual(ids_by_rank[0], "b")
        self.assertEqual(ids_by_rank[1], "c")
        self.assertEqual(ids_by_rank[2], "a")


class TestDigestFormatter(unittest.TestCase):
    """TASK-028: digest grouped by profile."""

    def test_format_digest_groups_by_profile(self) -> None:
        sections = [
            {
                "profile_name": "Backend",
                "total": 3,
                "new_count": 2,
                "shortlisted_count": 1,
                "review_later_count": 0,
                "highlights": [
                    {"title": "Senior Dev", "company": "Acme", "score": 0.8},
                    {"title": "Engineer", "company": "Foo", "score": 0.6},
                ],
            },
        ]
        text = format_digest(sections)
        self.assertIn("Backend", text)
        self.assertIn("3 total", text)
        self.assertIn("Senior Dev", text)
        self.assertIn("Acme", text)
        self.assertIn("Open queue", text)

    def test_build_sections_from_matches(self) -> None:
        matches_by_profile = {
            "Profile A": [
                {"state": "new", "score": 0.9, "vacancy": {"title": "T1", "company": "C1"}},
                {"state": "new", "score": 0.5, "vacancy": {"title": "T2", "company": "C2"}},
            ],
        }
        sections = build_digest_sections_from_matches(matches_by_profile, top_n=2)
        self.assertEqual(len(sections), 1)
        self.assertEqual(sections[0]["profile_name"], "Profile A")
        self.assertEqual(sections[0]["total"], 2)
        self.assertEqual(sections[0]["new_count"], 2)
        self.assertEqual(len(sections[0]["highlights"]), 2)
        self.assertEqual(sections[0]["highlights"][0]["title"], "T1")

    def test_format_digest_includes_bands_and_states_line(self) -> None:
        sections = [
            {
                "profile_name": "primary_search",
                "total": 4,
                "new_count": 2,
                "shortlisted_count": 1,
                "review_later_count": 1,
                "high_count": 1,
                "medium_count": 2,
                "low_count": 1,
                "highlights": [{"title": "Role", "company": "Co", "score": 0.8}],
            },
        ]
        text = format_digest(sections)
        self.assertIn("primary_search", text)
        self.assertIn("bands:", text)
        self.assertIn("high", text)
        self.assertIn("medium", text)
        self.assertIn("states:", text)
        self.assertIn("shortlisted", text)
