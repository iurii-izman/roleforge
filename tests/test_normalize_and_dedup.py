"""
Tests for normalize (TASK-019), dedup (TASK-020), and idempotency/replay (TASK-034).
"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from roleforge.dedup import group_by_dedup_key, normalize_candidate, persist_deduped
from roleforge.normalize import dedup_key, normalize_location, normalize_title, normalize_url


class TestNormalizeUrl(unittest.TestCase):
    """TASK-019: URL normalization."""

    def test_strips_utm_params(self) -> None:
        u = "https://jobs.example.com/job/1?utm_source=email&utm_medium=link&foo=bar"
        self.assertIn("foo=bar", normalize_url(u) or "")
        self.assertNotIn("utm_source", normalize_url(u) or "")

    def test_returns_none_for_empty(self) -> None:
        self.assertIsNone(normalize_url(None))
        self.assertIsNone(normalize_url(""))

    def test_returns_none_for_non_http(self) -> None:
        self.assertIsNone(normalize_url("ftp://x.com"))

    def test_normalizes_host_lowercase(self) -> None:
        self.assertIn("example.com", normalize_url("https://Example.COM/path") or "")


class TestNormalizeText(unittest.TestCase):
    """TASK-019: title, company, location."""

    def test_collapses_whitespace(self) -> None:
        self.assertEqual(normalize_title("  Senior   Engineer  "), "Senior Engineer")
        self.assertEqual(normalize_location("  Remote  "), "Remote")


class TestDedupKey(unittest.TestCase):
    """Dedup key for grouping."""

    def test_same_url_same_key(self) -> None:
        a = {"canonical_url": "https://example.com/job", "title": "Dev", "company": "Acme"}
        b = {"canonical_url": "https://example.com/job", "title": "Developer", "company": "Acme"}
        self.assertEqual(dedup_key(a)[0], dedup_key(b)[0])

    def test_different_url_different_key(self) -> None:
        a = {"canonical_url": "https://a.com/1", "title": "X", "company": "Y"}
        b = {"canonical_url": "https://b.com/2", "title": "X", "company": "Y"}
        self.assertNotEqual(dedup_key(a), dedup_key(b))


class TestGroupByDedupKey(unittest.TestCase):
    """TASK-020: group by canonical key."""

    def test_single_candidate_one_group(self) -> None:
        c = {
            "canonical_url": "https://example.com/1",
            "title": "Engineer",
            "company": "Acme",
            "gmail_message_id": "msg-1",
            "fragment_key": "0",
            "raw_snippet": None,
        }
        grouped = group_by_dedup_key([c])
        self.assertEqual(len(grouped), 1)
        vac, sources = grouped[0]
        self.assertEqual(vac["canonical_url"], "https://example.com/1")
        self.assertEqual(len(sources), 1)
        self.assertEqual(sources[0]["gmail_message_id"], "msg-1")

    def test_two_same_url_one_group(self) -> None:
        a = {"canonical_url": "https://example.com/job", "title": "A", "gmail_message_id": "m1", "fragment_key": "0", "raw_snippet": None}
        b = {"canonical_url": "https://example.com/job", "title": "A", "gmail_message_id": "m2", "fragment_key": "0", "raw_snippet": None}
        grouped = group_by_dedup_key([a, b])
        self.assertEqual(len(grouped), 1)
        vac, sources = grouped[0]
        self.assertEqual(len(sources), 2)


class TestPersistDeduped(unittest.TestCase):
    """TASK-020: persist grouped (mock conn)."""

    def test_inserts_vacancy_and_observations(self) -> None:
        vacancy_row = {"canonical_url": "https://example.com/1", "company": "Acme", "title": "Dev", "location": None, "salary_raw": None, "parse_confidence": 0.9}
        sources = [{"gmail_message_id": "msg-1", "fragment_key": "0", "raw_snippet": "snippet"}]
        mock_cur = MagicMock()
        mock_cur.fetchone.side_effect = [None, ("uuid-1",)]  # no existing vacancy; then RETURNING id
        mock_conn = MagicMock()
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cur)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        ids = persist_deduped(mock_conn, [(vacancy_row, sources)])
        self.assertEqual(len(ids), 1)
        mock_conn.commit.assert_called_once()
        self.assertGreaterEqual(mock_cur.execute.call_count, 2)

    def test_reuses_existing_vacancy_without_url_by_title_and_company(self) -> None:
        vacancy_row = {
            "canonical_url": None,
            "company": None,
            "title": "Компания Acme просмотрела ваше резюме",
            "location": None,
            "salary_raw": None,
            "parse_confidence": 0.6,
        }
        sources = [{"gmail_message_id": "msg-1", "fragment_key": "0", "raw_snippet": "snippet"}]
        mock_cur = MagicMock()
        mock_cur.fetchone.side_effect = [("existing-uuid",)]
        mock_conn = MagicMock()
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cur)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        ids = persist_deduped(mock_conn, [(vacancy_row, sources)])

        self.assertEqual(ids, ["existing-uuid"])
        executed_sql = " ".join(call.args[0] for call in mock_cur.execute.call_args_list)
        self.assertIn("canonical_url IS NULL", executed_sql)
        self.assertNotIn("INSERT INTO vacancies", executed_sql)
