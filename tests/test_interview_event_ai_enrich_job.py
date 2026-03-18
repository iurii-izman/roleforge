from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from roleforge.jobs.interview_event_ai_enrich import JOB_TYPE, run_once


class TestInterviewEventAiEnrichJob(unittest.TestCase):
    def test_disabled_by_default(self) -> None:
        mock_conn = MagicMock()
        with patch("roleforge.jobs.interview_event_ai_enrich.connect_db", return_value=mock_conn), patch(
            "roleforge.jobs.interview_event_ai_enrich.log_job_start", return_value="run-1"
        ), patch("roleforge.jobs.interview_event_ai_enrich.log_job_finish") as log_finish, patch(
            "roleforge.jobs.interview_event_ai_enrich.get_setting", return_value=None
        ):
            out = run_once()
        self.assertEqual(out["status"], "success")
        self.assertFalse(out["enabled"])
        log_finish.assert_called_once()

    def test_enriches_and_writes_notes_with_cost(self) -> None:
        mock_conn = MagicMock()

        select_cur = MagicMock()
        select_cur.fetchall.return_value = [
            ("ie-1", {}, "Acme", "Backend Engineer", "Excerpt"),
        ]
        update_cur = MagicMock()
        mock_conn.cursor.return_value.__enter__ = MagicMock(side_effect=[select_cur, update_cur])
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        def get_setting_side_effect(name: str, default: str | None = None) -> str | None:
            mapping = {
                "INTERVIEW_AI_ENRICH_ENABLED": "true",
                "INTERVIEW_AI_MAX_PER_RUN": "10",
                "INTERVIEW_AI_REENRICH": "",
            }
            return mapping.get(name, default)

        with patch("roleforge.jobs.interview_event_ai_enrich.connect_db", return_value=mock_conn), patch(
            "roleforge.jobs.interview_event_ai_enrich.log_job_start", return_value="run-1"
        ), patch("roleforge.jobs.interview_event_ai_enrich.log_job_finish") as log_finish, patch(
            "roleforge.jobs.interview_event_ai_enrich.get_setting", side_effect=get_setting_side_effect
        ), patch(
            "roleforge.jobs.interview_event_ai_enrich.enrich_company_briefing",
            return_value=({"text": "brief", "model": "m", "prompt_version": "v", "prompt_hash": "h", "enriched_at": "t"}, 0.01),
        ), patch(
            "roleforge.jobs.interview_event_ai_enrich.enrich_prep_checklist",
            return_value=({"text": "- a\n- b\n- c\n- d\n- e\n- f\n- g\n- h", "model": "m", "prompt_version": "v", "prompt_hash": "h", "enriched_at": "t"}, 0.02),
        ):
            out = run_once()

        self.assertEqual(out["status"], "success")
        self.assertTrue(out["enabled"])
        self.assertEqual(out["briefings_ok"], 1)
        self.assertEqual(out["checklists_ok"], 1)
        self.assertAlmostEqual(out["ai_cost_usd"], 0.03, places=6)
        self.assertEqual(update_cur.execute.call_count, 1)
        log_finish.assert_called_once()

    def test_skips_existing_when_reenrich_off(self) -> None:
        mock_conn = MagicMock()
        select_cur = MagicMock()
        select_cur.fetchall.return_value = [
            ("ie-1", {"ai_briefing": {"text": "x"}, "prep_checklist": {"text": "y"}}, "Acme", "Backend", "Excerpt"),
        ]
        mock_conn.cursor.return_value.__enter__ = MagicMock(side_effect=[select_cur])
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        def get_setting_side_effect(name: str, default: str | None = None) -> str | None:
            mapping = {
                "INTERVIEW_AI_ENRICH_ENABLED": "true",
                "INTERVIEW_AI_REENRICH": "false",
            }
            return mapping.get(name, default)

        with patch("roleforge.jobs.interview_event_ai_enrich.connect_db", return_value=mock_conn), patch(
            "roleforge.jobs.interview_event_ai_enrich.log_job_start", return_value="run-1"
        ), patch("roleforge.jobs.interview_event_ai_enrich.log_job_finish"), patch(
            "roleforge.jobs.interview_event_ai_enrich.get_setting", side_effect=get_setting_side_effect
        ), patch("roleforge.jobs.interview_event_ai_enrich.enrich_company_briefing") as brief, patch(
            "roleforge.jobs.interview_event_ai_enrich.enrich_prep_checklist"
        ) as check:
            out = run_once()

        self.assertEqual(out["skipped_existing"], 1)
        brief.assert_not_called()
        check.assert_not_called()

