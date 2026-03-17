# Tests for roleforge.enrichment (TASK-063). No real API calls; use mocks.

import unittest
from unittest.mock import MagicMock, Mock, patch

from roleforge.enrichment import (
    DEFAULT_MODEL_OPENAI,
    DEFAULT_MODEL_ANTHROPIC,
    enrich_one,
    run_enrichment_for_high_scores,
    update_vacancy_ai_metadata,
    _get_provider_and_model,
)


class TestGetProviderAndModel(unittest.TestCase):
    @patch("roleforge.enrichment.get_setting")
    def test_default_openai(self, get_setting: object) -> None:
        get_setting.side_effect = lambda k, default=None: None if default is None else default
        provider, model = _get_provider_and_model()
        self.assertEqual(provider, "openai")
        self.assertEqual(model, DEFAULT_MODEL_OPENAI)

    @patch("roleforge.enrichment.get_setting")
    def test_anthropic_when_set(self, get_setting: object) -> None:
        def get(k, default=None):
            if k == "PRIMARY_AI_PROVIDER":
                return "anthropic"
            if k == "AI_ENRICHMENT_MODEL":
                return None
            return default
        get_setting.side_effect = get
        provider, model = _get_provider_and_model()
        self.assertEqual(provider, "anthropic")
        self.assertEqual(model, DEFAULT_MODEL_ANTHROPIC)


class TestEnrichOneMocked(unittest.TestCase):
    @patch("roleforge.enrichment.with_retry")
    def test_enrich_one_returns_metadata_and_cost(self, with_retry: object) -> None:
        with_retry.side_effect = lambda fn, **kw: fn()
        with patch("roleforge.enrichment._get_provider_and_model", return_value=("openai", "gpt-4o-mini")):
            with patch("roleforge.enrichment._call_openai", return_value=("A short summary.", 0.001)):
                meta, cost = enrich_one(
                    title="Engineer",
                    company="Co",
                    body_excerpt="Python role.",
                )
        self.assertIn("summary", meta)
        self.assertEqual(meta["summary"], "A short summary.")
        self.assertIn("model", meta)
        self.assertIn("prompt_version", meta)
        self.assertIn("enriched_at", meta)
        self.assertIn("prompt_hash", meta)
        self.assertEqual(cost, 0.001)

    @patch("roleforge.enrichment.with_retry")
    def test_enrich_one_truncates_long_summary(self, with_retry: object) -> None:
        long_sum = "x" * 600
        with_retry.side_effect = lambda fn, **kw: fn()
        with patch("roleforge.enrichment._get_provider_and_model", return_value=("openai", "gpt-4o-mini")):
            with patch("roleforge.enrichment._call_openai", return_value=(long_sum, None)):
                meta, _ = enrich_one(title="T", body_excerpt="")
        self.assertLessEqual(len(meta["summary"]), 500)


class TestUpdateVacancyAiMetadata(unittest.TestCase):
    def test_update_vacancy_ai_metadata_executes_sql(self) -> None:
        cur = Mock()
        conn = MagicMock()
        conn.cursor.return_value.__enter__.return_value = cur
        conn.cursor.return_value.__exit__.return_value = None
        update_vacancy_ai_metadata(conn, "uuid-here", {"summary": "Hi", "model": "gpt-4o-mini"})
        cur.execute.assert_called_once()
        call_args = cur.execute.call_args[0]
        self.assertIn("vacancies", call_args[0])
        self.assertEqual(call_args[1][1], "uuid-here")
        conn.commit.assert_called_once()


class TestRunEnrichmentForHighScores(unittest.TestCase):
    def test_returns_zero_summary_when_no_candidates(self) -> None:
        conn = MagicMock()
        cur = MagicMock()
        cur.fetchall.return_value = []
        conn.cursor.return_value.__enter__.return_value = cur
        conn.cursor.return_value.__exit__.return_value = None
        out = run_enrichment_for_high_scores(conn, min_score=0.75, max_per_run=20)
        self.assertEqual(out["enrichments_ok"], 0)
        self.assertEqual(out["enrichment_failures"], 0)
        self.assertIn("ai_cost_usd", out)
        self.assertEqual(out["ai_cost_usd"], 0.0)

    @patch("roleforge.enrichment.enrich_one")
    @patch("roleforge.enrichment.update_vacancy_ai_metadata")
    def test_returns_summary_with_cost_when_one_enriched(
        self, update_meta: Mock, enrich_one_fn: Mock
    ) -> None:
        conn = MagicMock()
        cur = MagicMock()
        cur.fetchall.side_effect = [
            [("v1", "Engineer", "Acme", "Remote", "100k")],
            [(None,)],
        ]
        conn.cursor.return_value.__enter__.return_value = cur
        conn.cursor.return_value.__exit__.return_value = None
        enrich_one_fn.return_value = ({"summary": "Hi", "model": "gpt-4o-mini"}, 0.002)
        out = run_enrichment_for_high_scores(conn, min_score=0.75, max_per_run=20)
        self.assertEqual(out["enrichments_ok"], 1)
        self.assertEqual(out["ai_cost_usd"], 0.002)
        update_meta.assert_called_once()
