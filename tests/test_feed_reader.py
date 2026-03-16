"""Tests for feed reader and entry-to-candidate (TASK-047)."""

from __future__ import annotations

import unittest
from hashlib import sha256
from unittest.mock import MagicMock, patch

from roleforge.feed_reader import (
    _stable_entry_id,
    entry_to_candidate,
    fetch_feed_candidates,
)


class TestStableEntryId(unittest.TestCase):
    def test_uses_id_first(self) -> None:
        entry = MagicMock()
        entry.id = "entry-123"
        entry.guid = None
        entry.link = "https://example.com/1"
        entry.title = "Job"
        self.assertEqual(_stable_entry_id(entry), "entry-123")

    def test_fallback_to_link(self) -> None:
        entry = MagicMock()
        entry.id = None
        entry.guid = None
        entry.link = "https://example.com/job/1"
        entry.title = "Job"
        self.assertEqual(_stable_entry_id(entry), "https://example.com/job/1")

    def test_fallback_to_title_hash(self) -> None:
        entry = MagicMock()
        entry.id = None
        entry.guid = None
        entry.link = None
        entry.title = "Engineer"
        out = _stable_entry_id(entry)
        self.assertEqual(out, sha256(b"Engineer").hexdigest()[:16])


class TestEntryToCandidate(unittest.TestCase):
    def test_maps_link_and_title(self) -> None:
        entry = MagicMock()
        entry.link = "https://jobs.example.com/123"
        entry.title = "Senior Backend Engineer"
        entry.summary = None
        entry.description = None
        entry.content = None
        c = entry_to_candidate(entry, "feed1", "feed1:entry-1")
        self.assertEqual(c["canonical_url"], "https://jobs.example.com/123")
        self.assertEqual(c["title"], "Senior Backend Engineer")
        self.assertEqual(c["feed_source_key"], "feed1:entry-1")
        self.assertEqual(c["fragment_key"], "0")
        self.assertIn("parse_confidence", c)

    def test_extracts_company_from_summary(self) -> None:
        entry = MagicMock()
        entry.link = "https://example.com/j"
        entry.title = "Dev"
        entry.summary = "Company: Acme Inc\nLocation: Remote"
        entry.description = None
        entry.content = None
        c = entry_to_candidate(entry, "f", "f:e1")
        self.assertEqual(c["company"], "Acme Inc")
        self.assertEqual(c["location"], "Remote")


class TestFetchFeedCandidates(unittest.TestCase):
    @patch("roleforge.feed_reader.fetch_feed")
    def test_filters_by_seen_source_keys(self, fetch_feed) -> None:
        entry = MagicMock()
        entry.id = "e1"
        entry.link = "https://example.com/1"
        entry.title = "Job"
        entry.summary = None
        entry.description = None
        entry.content = None
        entry.guid = None
        fetch_feed.return_value = [entry]
        seen = {"myfeed:e1"}
        out = fetch_feed_candidates("myfeed", "https://example.com/feed.xml", seen)
        self.assertEqual(len(out), 0)

    @patch("roleforge.feed_reader.fetch_feed")
    def test_returns_candidates_for_new_entries(self, fetch_feed) -> None:
        entry = MagicMock()
        entry.id = "e2"
        entry.link = "https://example.com/2"
        entry.title = "Another Job"
        entry.summary = None
        entry.description = None
        entry.content = None
        entry.guid = None
        fetch_feed.return_value = [entry]
        out = fetch_feed_candidates("myfeed", "https://example.com/feed.xml", set())
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["feed_source_key"], "myfeed:e2")
