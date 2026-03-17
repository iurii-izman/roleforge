# Tests for roleforge.scheduler (EPIC-16).

from __future__ import annotations

import unittest
from datetime import datetime, time as dt_time, timezone
from typing import Any

from roleforge.scheduler import RoleforgeScheduler, SchedulerJob, _next_daily_run


UTC = timezone.utc


def _make_job(name: str, *, due: bool = True, should_fail: bool = False) -> tuple[SchedulerJob, list[str]]:
    calls: list[str] = []

    def runner() -> dict[str, Any]:
        calls.append(name)
        if should_fail:
            raise RuntimeError(f"{name} failed")
        return {"status": "ok", "job": name}

    job = SchedulerJob(
        name=name,
        runner=runner,
        run_on_startup=due,
        interval_seconds=60,
    )
    return job, calls


class TestSchedulerTimeHelpers(unittest.TestCase):
    def test_next_daily_run_same_day_when_future(self) -> None:
        now = datetime(2026, 3, 18, 8, 0, tzinfo=UTC)
        next_run = _next_daily_run(now, dt_time(9, 0, tzinfo=UTC))
        self.assertEqual(next_run, datetime(2026, 3, 18, 9, 0, tzinfo=UTC))

    def test_next_daily_run_tomorrow_when_past(self) -> None:
        now = datetime(2026, 3, 18, 10, 0, tzinfo=UTC)
        next_run = _next_daily_run(now, dt_time(9, 0, tzinfo=UTC))
        self.assertEqual(next_run, datetime(2026, 3, 19, 9, 0, tzinfo=UTC))


class TestSchedulerTick(unittest.TestCase):
    def test_tick_runs_due_jobs_and_reschedules(self) -> None:
        job, calls = _make_job("gmail_poll", due=True)
        now = datetime(2026, 3, 18, 12, 0, tzinfo=UTC)
        scheduler = RoleforgeScheduler([job], now=now)
        result = scheduler.tick(now=now)
        self.assertEqual(calls, ["gmail_poll"])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["job_name"], "gmail_poll")
        self.assertEqual(result[0]["status"], "success")
        self.assertEqual(scheduler.state["gmail_poll"].last_status, "success")
        self.assertGreater(scheduler.state["gmail_poll"].next_run_at, now)

    def test_tick_skips_not_due_jobs(self) -> None:
        job, calls = _make_job("digest", due=False)
        now = datetime(2026, 3, 18, 12, 0, tzinfo=UTC)
        scheduler = RoleforgeScheduler([job], now=now)
        scheduler.state["digest"].next_run_at = datetime(2026, 3, 18, 13, 0, tzinfo=UTC)
        result = scheduler.tick(now=now)
        self.assertEqual(calls, [])
        self.assertEqual(result, [])

    def test_tick_continues_after_failure(self) -> None:
        fail_job, fail_calls = _make_job("alert", due=True, should_fail=True)
        ok_job, ok_calls = _make_job("batch", due=True)
        now = datetime(2026, 3, 18, 12, 0, tzinfo=UTC)
        scheduler = RoleforgeScheduler([fail_job, ok_job], now=now)
        result = scheduler.tick(now=now)
        self.assertEqual(fail_calls, ["alert"])
        self.assertEqual(ok_calls, ["batch"])
        self.assertEqual([row["status"] for row in result], ["failure", "success"])

