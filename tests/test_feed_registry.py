"""Tests for feed registry and kill-switch (TASK-046)."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from roleforge.feed_registry import is_feed_intake_enabled, load_registry, get_enabled_feeds


class TestFeedIntakeKillSwitch(unittest.TestCase):
    def test_default_disabled(self) -> None:
        if "FEED_INTAKE_ENABLED" in os.environ:
            del os.environ["FEED_INTAKE_ENABLED"]
        self.assertFalse(is_feed_intake_enabled())

    def test_enabled_when_true(self) -> None:
        os.environ["FEED_INTAKE_ENABLED"] = "true"
        try:
            self.assertTrue(is_feed_intake_enabled())
        finally:
            del os.environ["FEED_INTAKE_ENABLED"]

    def test_enabled_when_1(self) -> None:
        os.environ["FEED_INTAKE_ENABLED"] = "1"
        try:
            self.assertTrue(is_feed_intake_enabled())
        finally:
            del os.environ["FEED_INTAKE_ENABLED"]

    def test_disabled_when_false(self) -> None:
        os.environ["FEED_INTAKE_ENABLED"] = "false"
        try:
            self.assertFalse(is_feed_intake_enabled())
        finally:
            del os.environ["FEED_INTAKE_ENABLED"]


class TestLoadRegistry(unittest.TestCase):
    def test_missing_file_returns_empty(self) -> None:
        self.assertEqual(load_registry(path=Path("/nonexistent/feeds.yaml")), [])

    def test_empty_feeds_returns_empty(self) -> None:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("feeds: []\n")
            path = Path(f.name)
        try:
            self.assertEqual(load_registry(path=path), [])
        finally:
            path.unlink()

    def test_loads_enabled_feed(self) -> None:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("""
feeds:
  - id: test_feed
    name: Test RSS
    url: https://example.com/feed.xml
    type: rss
    enabled: true
""")
            path = Path(f.name)
        try:
            out = load_registry(path=path)
            self.assertEqual(len(out), 1)
            self.assertEqual(out[0]["id"], "test_feed")
            self.assertEqual(out[0]["url"], "https://example.com/feed.xml")
            self.assertEqual(out[0]["type"], "rss")
        finally:
            path.unlink()

    def test_skips_disabled_feed(self) -> None:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("""
feeds:
  - id: disabled_feed
    url: https://example.com/off.xml
    enabled: false
""")
            path = Path(f.name)
        try:
            self.assertEqual(load_registry(path=path), [])
        finally:
            path.unlink()

    def test_get_enabled_feeds_respects_kill_switch(self) -> None:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("""
feeds:
  - id: a
    url: https://a.com/feed.xml
    enabled: true
""")
            path = Path(f.name)
        try:
            os.environ["FEED_INTAKE_ENABLED"] = "false"
            try:
                self.assertEqual(get_enabled_feeds(path=path), [])
            finally:
                del os.environ["FEED_INTAKE_ENABLED"]
        finally:
            path.unlink()
