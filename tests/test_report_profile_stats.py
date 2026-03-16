"""
Tests for report_profile_stats analytics (v2.1).
"""

from __future__ import annotations

import importlib.util
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = REPO_ROOT / "scripts"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def _load_report_module():
    spec = importlib.util.spec_from_file_location(
        "report_profile_stats",
        SCRIPTS / "report_profile_stats.py",
        submodule_search_locations=[str(SCRIPTS)],
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestReportProfileStatsSummarize(unittest.TestCase):
    def test_summarize_rows_aggregates_state_and_high_score(self) -> None:
        mod = _load_report_module()
        rows = [
            ("p1", "new", 0.8, None),
            ("p1", "shortlisted", 0.9, None),
            ("p1", "applied", 0.75, None),
        ]
        out = mod._summarize_rows(rows, since=None)
        self.assertEqual(out["p1"]["matches_total"], 3)
        self.assertEqual(out["p1"]["state_counts"]["new"], 1)
        self.assertEqual(out["p1"]["state_counts"]["shortlisted"], 1)
        self.assertEqual(out["p1"]["state_counts"]["applied"], 1)
        self.assertEqual(out["p1"]["high_score_matches"], 3)
        self.assertEqual(out["p1"]["high_score_applied"], 1)

    def test_summarize_rows_new_in_window_when_since_set(self) -> None:
        mod = _load_report_module()
        since = datetime(2026, 3, 10, tzinfo=timezone.utc)
        # created_at naive UTC
        old = datetime(2026, 3, 9, 12, 0, 0)
        new = datetime(2026, 3, 11, 12, 0, 0)
        rows = [
            ("p1", "new", 0.5, old),
            ("p1", "new", 0.6, new),
        ]
        out = mod._summarize_rows(rows, since=since)
        self.assertEqual(out["p1"]["new_in_window"], 1)
