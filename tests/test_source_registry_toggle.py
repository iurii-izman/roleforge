from __future__ import annotations

import tempfile
import unittest
from pathlib import Path


class TestSourceRegistryToggle(unittest.TestCase):
    def test_toggle_feed_enabled_writes_yaml(self) -> None:
        from roleforge.web import source_registry as sr

        with tempfile.TemporaryDirectory() as td:
            # Patch paths by monkeypatching REPO_ROOT indirectly: write directly to expected locations via temp.
            # Easiest: create minimal fake repo root structure and temporarily replace module-level helpers.
            root = Path(td)
            (root / "config").mkdir(parents=True, exist_ok=True)
            (root / "config" / "feeds.yaml").write_text(
                "feeds:\n  - id: f1\n    name: Feed1\n    url: https://x\n    type: rss\n    enabled: false\n",
                encoding="utf-8",
            )

            orig_repo_root = sr.REPO_ROOT
            try:
                sr.REPO_ROOT = root  # type: ignore[misc]
                out = sr.toggle_feed("f1", enabled=True)
                self.assertTrue(out.ok)
                data = (root / "config" / "feeds.yaml").read_text(encoding="utf-8")
                self.assertIn("enabled: true", data)
            finally:
                sr.REPO_ROOT = orig_repo_root  # type: ignore[misc]

    def test_toggle_monitor_enabled_writes_yaml(self) -> None:
        from roleforge.web import source_registry as sr

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "config").mkdir(parents=True, exist_ok=True)
            (root / "config" / "monitors.yaml").write_text(
                "monitors:\n  - id: m1\n    name: Monitor1\n    type: hh_api\n    enabled: true\n",
                encoding="utf-8",
            )

            orig_repo_root = sr.REPO_ROOT
            try:
                sr.REPO_ROOT = root  # type: ignore[misc]
                out = sr.toggle_monitor("m1", enabled=False)
                self.assertTrue(out.ok)
                data = (root / "config" / "monitors.yaml").read_text(encoding="utf-8")
                self.assertIn("enabled: false", data)
            finally:
                sr.REPO_ROOT = orig_repo_root  # type: ignore[misc]

