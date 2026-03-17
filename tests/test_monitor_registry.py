"""Tests for monitor registry and kill-switch (TASK-085)."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from roleforge.monitor_registry import get_enabled_monitors, is_monitor_intake_enabled, load_registry


class TestMonitorIntakeKillSwitch(unittest.TestCase):
    def test_default_disabled(self) -> None:
        os.environ.pop("MONITOR_INTAKE_ENABLED", None)
        self.assertFalse(is_monitor_intake_enabled())

    def test_enabled_when_true(self) -> None:
        os.environ["MONITOR_INTAKE_ENABLED"] = "true"
        try:
            self.assertTrue(is_monitor_intake_enabled())
        finally:
            os.environ.pop("MONITOR_INTAKE_ENABLED", None)

    def test_disabled_when_false(self) -> None:
        os.environ["MONITOR_INTAKE_ENABLED"] = "false"
        try:
            self.assertFalse(is_monitor_intake_enabled())
        finally:
            os.environ.pop("MONITOR_INTAKE_ENABLED", None)


class TestMonitorRegistry(unittest.TestCase):
    def test_missing_file_returns_empty(self) -> None:
        self.assertEqual(load_registry(path=Path("/nonexistent/monitors.yaml")), [])

    def test_loads_enabled_hh_monitor(self) -> None:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(
                """
monitors:
  - id: hh_python_remote
    name: HH.ru Python Remote
    type: hh_api
    enabled: true
    poll_interval_minutes: 60
    params:
      text: python backend
      area: 1
      schedule: remote
      per_page: 100
"""
            )
            path = Path(f.name)
        try:
            monitors = load_registry(path=path)
            self.assertEqual(len(monitors), 1)
            self.assertEqual(monitors[0]["id"], "hh_python_remote")
            self.assertEqual(monitors[0]["type"], "hh_api")
            self.assertEqual(monitors[0]["poll_interval_minutes"], 60)
        finally:
            path.unlink()

    def test_skips_disabled_monitor(self) -> None:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(
                """
monitors:
  - id: disabled
    type: hh_api
    enabled: false
    params:
      text: go backend
"""
            )
            path = Path(f.name)
        try:
            self.assertEqual(load_registry(path=path), [])
        finally:
            path.unlink()

    def test_get_enabled_monitors_respects_kill_switch(self) -> None:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(
                """
monitors:
  - id: one
    type: hh_api
    enabled: true
    params:
      text: python
"""
            )
            path = Path(f.name)
        try:
            os.environ["MONITOR_INTAKE_ENABLED"] = "false"
            try:
                self.assertEqual(get_enabled_monitors(path=path), [])
            finally:
                os.environ.pop("MONITOR_INTAKE_ENABLED", None)
        finally:
            path.unlink()
