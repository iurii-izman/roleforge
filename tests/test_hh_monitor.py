"""Tests for HH.ru monitor adapter (TASK-086)."""

from __future__ import annotations

import json
import unittest
from unittest.mock import patch

from roleforge.monitors.hh import _format_salary, fetch_candidates


class TestFormatSalary(unittest.TestCase):
    def test_formats_salary_range(self) -> None:
        out = _format_salary({"from": 100000, "to": 150000, "currency": "RUR", "gross": True})
        self.assertIn("100000–150000", out)
        self.assertIn("RUR", out)
        self.assertIn("gross", out)

    def test_handles_missing_salary(self) -> None:
        self.assertIsNone(_format_salary(None))


class TestFetchCandidates(unittest.TestCase):
    @patch("roleforge.monitors.hh._fetch_json")
    def test_fetch_candidates_maps_vacancies(self, fetch_json) -> None:
        fetch_json.return_value = {
            "items": [
                {
                    "id": "123",
                    "name": "Python Backend Engineer",
                    "alternate_url": "https://hh.ru/vacancy/123",
                    "published_at": "2026-03-18T10:00:00+0300",
                    "salary": {"from": 100000, "to": 150000, "currency": "RUR", "gross": True},
                    "employer": {"name": "Acme"},
                    "area": {"name": "Remote"},
                }
            ],
            "pages": 1,
        }
        out = fetch_candidates("hh_python_remote", {"text": "python backend", "per_page": 100}, set())
        self.assertEqual(len(out), 1)
        row = out[0]
        self.assertEqual(row["feed_source_key"], "monitor:hh:123")
        self.assertEqual(row["canonical_url"], "https://hh.ru/vacancy/123")
        self.assertEqual(row["company"], "Acme")
        self.assertEqual(row["title"], "Python Backend Engineer")
        self.assertEqual(row["location"], "Remote")
        self.assertIn("gross", row["salary_raw"])
        self.assertEqual(row["parse_confidence"], 1.0)

    @patch("roleforge.monitors.hh._fetch_json")
    def test_fetch_candidates_filters_seen_keys(self, fetch_json) -> None:
        fetch_json.return_value = {
            "items": [
                {"id": "123", "name": "Python Backend Engineer", "alternate_url": "https://hh.ru/vacancy/123", "employer": {"name": "Acme"}, "area": {"name": "Remote"}},
            ],
            "pages": 1,
        }
        out = fetch_candidates("hh_python_remote", {"text": "python backend", "per_page": 100}, {"monitor:hh:123"})
        self.assertEqual(out, [])
