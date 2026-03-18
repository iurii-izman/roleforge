from __future__ import annotations

import unittest

from roleforge.web.profile_editor import validate_profile_config


class TestProfileEditorValidation(unittest.TestCase):
    def test_rejects_non_object(self) -> None:
        out = validate_profile_config("[]")
        self.assertFalse(out.ok)

    def test_rejects_unknown_top_level_key(self) -> None:
        out = validate_profile_config('{"foo": 1}')
        self.assertFalse(out.ok)
        self.assertIn("unknown top-level keys", out.message)

    def test_accepts_minimal_valid_config(self) -> None:
        out = validate_profile_config('{"hard_filters": {}, "weights": {"title_match": 1.0}}')
        self.assertTrue(out.ok)

    def test_rejects_bad_min_score(self) -> None:
        out = validate_profile_config('{"min_score": 2.0}')
        self.assertFalse(out.ok)

