"""
Tests for generic retry and Telegram/AI classifiers (TASK-037).
"""

from __future__ import annotations

import unittest

from roleforge.retry import (
    is_permanent_ai,
    is_permanent_telegram,
    is_transient_ai,
    is_transient_telegram,
    with_retry,
)


class _ExcWithStatus(Exception):
    def __init__(self, status: int, msg: str = ""):
        super().__init__(msg)
        self.status_code = status


class TestGenericRetry(unittest.TestCase):
    def test_success_first_try(self) -> None:
        out = with_retry(lambda: 42, is_transient=lambda e: True, is_permanent=lambda e: False)
        self.assertEqual(out, 42)

    def test_transient_then_success(self) -> None:
        attempts = [0]

        def flaky() -> int:
            attempts[0] += 1
            if attempts[0] < 2:
                raise _ExcWithStatus(503)
            return 1

        out = with_retry(flaky, is_transient=lambda e: _http_status(e) == 503, is_permanent=lambda e: False, max_attempts=3)
        self.assertEqual(out, 1)
        self.assertEqual(attempts[0], 2)

    def test_permanent_raises_immediately(self) -> None:
        calls = [0]

        def fail() -> int:
            calls[0] += 1
            raise _ExcWithStatus(401)

        def is_transient(e: BaseException) -> bool:
            return _http_status(e) in (429, 503)

        def is_permanent(e: BaseException) -> bool:
            return _http_status(e) in (401, 403)

        with self.assertRaises(_ExcWithStatus):
            with_retry(fail, is_transient=is_transient, is_permanent=is_permanent)
        self.assertEqual(calls[0], 1)


def _http_status(exc: BaseException) -> int | None:
    return getattr(exc, "status_code", None)


class TestTelegramClassifiers(unittest.TestCase):
    def test_429_is_transient(self) -> None:
        self.assertTrue(is_transient_telegram(_ExcWithStatus(429)))
        self.assertFalse(is_permanent_telegram(_ExcWithStatus(429)))

    def test_401_is_permanent(self) -> None:
        self.assertTrue(is_permanent_telegram(_ExcWithStatus(401)))
        self.assertFalse(is_transient_telegram(_ExcWithStatus(401)))

    def test_503_is_transient(self) -> None:
        self.assertTrue(is_transient_telegram(_ExcWithStatus(503)))


class TestAIClassifiers(unittest.TestCase):
    def test_429_is_transient(self) -> None:
        self.assertTrue(is_transient_ai(_ExcWithStatus(429)))
        self.assertFalse(is_permanent_ai(_ExcWithStatus(429)))

    def test_401_is_permanent(self) -> None:
        self.assertTrue(is_permanent_ai(_ExcWithStatus(401)))

    def test_503_is_transient(self) -> None:
        self.assertTrue(is_transient_ai(_ExcWithStatus(503)))
