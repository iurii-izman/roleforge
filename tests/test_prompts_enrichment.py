# Tests for roleforge.prompts.enrichment (TASK-066)

import unittest

from roleforge.prompts.enrichment import (
    PROMPT_VERSION,
    build_user_prompt,
    prompt_hash_text,
    USER_PROMPT_TEMPLATE,
)


class TestEnrichmentPromptVersion(unittest.TestCase):
    def test_prompt_version_is_set(self) -> None:
        self.assertEqual(PROMPT_VERSION, "summary_v1")

    def test_user_prompt_template_has_placeholders(self) -> None:
        self.assertIn("{title}", USER_PROMPT_TEMPLATE)
        self.assertIn("{company}", USER_PROMPT_TEMPLATE)
        self.assertIn("{body_excerpt}", USER_PROMPT_TEMPLATE)


class TestBuildUserPrompt(unittest.TestCase):
    def test_build_user_prompt_fills_all_fields(self) -> None:
        out = build_user_prompt(
            title="Backend Engineer",
            company="Acme",
            location="Remote",
            salary_raw="100k",
            body_excerpt="We need Python and PostgreSQL.",
        )
        self.assertIn("Backend Engineer", out)
        self.assertIn("Acme", out)
        self.assertIn("Remote", out)
        self.assertIn("100k", out)
        self.assertIn("We need Python", out)

    def test_build_user_prompt_handles_none(self) -> None:
        out = build_user_prompt(
            title=None,
            company=None,
            location=None,
            salary_raw=None,
            body_excerpt="",
        )
        self.assertIn("(not specified)", out)
        self.assertIn("(no description)", out)


class TestPromptHash(unittest.TestCase):
    def test_prompt_hash_deterministic(self) -> None:
        a = prompt_hash_text("sys", "user")
        b = prompt_hash_text("sys", "user")
        self.assertEqual(a, b)

    def test_prompt_hash_different_for_different_input(self) -> None:
        a = prompt_hash_text("sys1", "user1")
        b = prompt_hash_text("sys2", "user2")
        self.assertNotEqual(a, b)

    def test_prompt_hash_prefixed(self) -> None:
        h = prompt_hash_text("x", "y")
        self.assertTrue(h.startswith("sha256:"))
