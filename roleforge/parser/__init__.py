"""Deterministic vacancy extraction from Gmail message bodies (TASK-017, TASK-018)."""

from roleforge.parser.extractor import extract_candidates
from roleforge.parser.schema import RawCandidate, validate_candidate

__all__ = ["extract_candidates", "RawCandidate", "validate_candidate"]
