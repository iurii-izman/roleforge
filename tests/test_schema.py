"""
Basic tests for MVP Postgres schema (TASK-032).

Validates that schema SQL exists and defines all required tables.
No database connection required.
"""

from __future__ import annotations

import unittest
from pathlib import Path

REQUIRED_TABLES = [
    "profiles",
    "gmail_messages",
    "vacancies",
    "vacancy_observations",
    "profile_matches",
    "telegram_deliveries",
    "review_actions",
    "job_runs",
]

SCHEMA_FILE = Path(__file__).resolve().parent.parent / "schema" / "001_initial_mvp.sql"


class TestSchemaExists(unittest.TestCase):
    def test_schema_file_exists(self) -> None:
        self.assertTrue(SCHEMA_FILE.exists(), f"Schema file not found: {SCHEMA_FILE}")

    def test_schema_defines_all_required_tables(self) -> None:
        content = SCHEMA_FILE.read_text(encoding="utf-8").lower()
        for table in REQUIRED_TABLES:
            self.assertIn(table, content, f"Table '{table}' not found in schema")
            self.assertIn(f"create table", content, "Schema must contain CREATE TABLE statements")


if __name__ == "__main__":
    unittest.main()
