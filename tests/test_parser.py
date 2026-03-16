"""
Tests for parser: extract_candidates (TASK-017) and validate_candidate (TASK-018).

Deterministic extraction; fixture-driven.
"""

from __future__ import annotations

import unittest
from pathlib import Path

from roleforge.parser import extract_candidates, validate_candidate
from roleforge.parser.schema import RawCandidate

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


def _load_fixture(name: str) -> str:
    with open(FIXTURES_DIR / name, encoding="utf-8") as f:
        return f.read()


class TestExtractCandidates(unittest.TestCase):
    """Test deterministic extraction (single-job and digest)."""

    def test_single_job_with_structured_body(self) -> None:
        body = _load_fixture("single_job_body.txt")
        out = extract_candidates(body_plain=body, subject="Senior Engineer at Acme")
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["fragment_key"], "0")
        self.assertIn("jobs.example.com", out[0]["canonical_url"] or "")
        self.assertEqual(out[0]["company"], "Acme Corp")
        self.assertEqual(out[0]["title"], "Senior Engineer")
        self.assertEqual(out[0]["location"], "Remote")
        self.assertEqual(out[0]["salary_raw"], "100k–120k")
        self.assertGreaterEqual(out[0]["parse_confidence"], 0.8)

    def test_single_job_subject_only(self) -> None:
        out = extract_candidates(body_plain="", subject="Data Engineer at TechCo")
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["title"], "Data Engineer at TechCo")
        self.assertIsNone(out[0]["canonical_url"])
        self.assertLess(out[0]["parse_confidence"], 0.7)

    def test_digest_multiple_urls(self) -> None:
        body = _load_fixture("digest_body.txt")
        out = extract_candidates(body_plain=body)
        self.assertGreaterEqual(len(out), 2)
        self.assertEqual(out[0]["fragment_key"], "0")
        self.assertEqual(out[1]["fragment_key"], "1")
        self.assertIn("jobs.example.com", out[0]["canonical_url"] or "")

    def test_empty_body_no_subject_returns_empty(self) -> None:
        out = extract_candidates(body_plain="", subject="")
        self.assertEqual(out, [])

    def test_resume_view_notification_without_url_is_ignored(self) -> None:
        out = extract_candidates(
            body_plain="Здравствуйте! Компания просмотрела ваше резюме.",
            subject="Компания Acme просмотрела ваше резюме",
        )
        self.assertEqual(out, [])

    def test_deterministic_same_input_same_output(self) -> None:
        body = _load_fixture("single_job_body.txt")
        a = extract_candidates(body_plain=body)
        b = extract_candidates(body_plain=body)
        self.assertEqual(a, b)


class TestValidateCandidate(unittest.TestCase):
    """Test schema validation (TASK-018)."""

    def test_valid_candidate_no_errors(self) -> None:
        c = RawCandidate(canonical_url="https://example.com/job", title="Dev", parse_confidence=0.9)
        self.assertEqual(validate_candidate(c), [])

    def test_confidence_out_of_range(self) -> None:
        c = RawCandidate(parse_confidence=1.5)
        errs = validate_candidate(c)
        self.assertTrue(any("parse_confidence" in e for e in errs))

    def test_confidence_in_range_ok(self) -> None:
        self.assertEqual(validate_candidate(RawCandidate(parse_confidence=0)), [])
        self.assertEqual(validate_candidate(RawCandidate(parse_confidence=1.0)), [])

    def test_invalid_url_scheme(self) -> None:
        c = RawCandidate(canonical_url="ftp://example.com")
        errs = validate_candidate(c)
        self.assertTrue(any("canonical_url" in e for e in errs))
