"""
Simple in-process scheduler for RoleForge (EPIC-16).

Chosen for MVP over APScheduler, the schedule package, or a Postgres-backed cron
table: the standard-library loop keeps the runtime light, avoids another
dependency, and stays aligned with the repo's single-operator, Postgres-first
assumptions. Each scheduled job keeps its own job_runs logging.
"""

from __future__ import annotations

import argparse
import json
import time
from dataclasses import dataclass
from datetime import datetime, time as dt_time, timedelta, timezone
from typing import Any, Callable, Iterable

from roleforge.jobs.alert import run_once as run_alert_once
from roleforge.jobs.batch import run_once as run_batch_once
from roleforge.jobs.digest import run_once as run_digest_once
from roleforge.jobs.feed_poll import run_once as run_feed_poll_once
from roleforge.jobs.gmail_poll import run_once as run_gmail_poll_once
from roleforge.structured_log import log_struct
from roleforge.runtime import get_setting


UTC = timezone.utc


@dataclass(frozen=True)
class SchedulerJob:
    name: str
    runner: Callable[[], dict[str, Any]]
    run_on_startup: bool
    interval_seconds: int | None = None
    daily_at_utc: dt_time | None = None


@dataclass
class ScheduledState:
    next_run_at: datetime
    last_run_at: datetime | None = None
    last_status: str | None = None
    last_summary: dict[str, Any] | None = None


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _int_setting(name: str, default: int) -> int:
    raw = get_setting(name)
    if raw in (None, ""):
        return default
    return int(raw)


def _parse_hhmm(value: str) -> dt_time:
    parts = value.strip().split(":", 1)
    if len(parts) != 2:
        raise ValueError(f"Invalid HH:MM time: {value!r}")
    hour = int(parts[0])
    minute = int(parts[1])
    return dt_time(hour=hour, minute=minute, tzinfo=UTC)


def _next_daily_run(now: datetime, daily_at_utc: dt_time) -> datetime:
    candidate = now.astimezone(UTC).replace(
        hour=daily_at_utc.hour,
        minute=daily_at_utc.minute,
        second=0,
        microsecond=0,
    )
    if candidate <= now.astimezone(UTC):
        candidate += timedelta(days=1)
    return candidate


def _next_interval_run(now: datetime, interval_seconds: int, *, run_on_startup: bool) -> datetime:
    if run_on_startup:
        return now
    return now + timedelta(seconds=interval_seconds)


def build_default_jobs() -> list[SchedulerJob]:
    """Build the approved job set and cadences from env defaults."""
    gmail_minutes = _int_setting("GMAIL_POLL_INTERVAL_MINUTES", 15)
    feed_minutes = _int_setting("FEED_POLL_INTERVAL_MINUTES", 60)
    alert_minutes = _int_setting("ALERT_POLL_INTERVAL_MINUTES", 5)
    batch_minutes = _int_setting("BATCH_POLL_INTERVAL_MINUTES", 15)
    digest_at = get_setting("DIGEST_AT_UTC", "09:00")
    daily_digest = _parse_hhmm(digest_at or "09:00")

    return [
        SchedulerJob(
            name="gmail_poll",
            runner=run_gmail_poll_once,
            run_on_startup=True,
            interval_seconds=gmail_minutes * 60,
        ),
        SchedulerJob(
            name="feed_poll",
            runner=run_feed_poll_once,
            run_on_startup=True,
            interval_seconds=feed_minutes * 60,
        ),
        SchedulerJob(
            name="alert",
            runner=run_alert_once,
            run_on_startup=True,
            interval_seconds=alert_minutes * 60,
        ),
        SchedulerJob(
            name="batch",
            runner=run_batch_once,
            run_on_startup=True,
            interval_seconds=batch_minutes * 60,
        ),
        SchedulerJob(
            name="digest",
            runner=run_digest_once,
            run_on_startup=False,
            daily_at_utc=daily_digest,
        ),
    ]


def _initial_state_for(job: SchedulerJob, now: datetime) -> ScheduledState:
    if job.daily_at_utc is not None:
        return ScheduledState(next_run_at=_next_daily_run(now, job.daily_at_utc))
    if job.interval_seconds is None:
        raise ValueError(f"Job {job.name} missing interval or daily_at_utc")
    return ScheduledState(
        next_run_at=_next_interval_run(now, job.interval_seconds, run_on_startup=job.run_on_startup)
    )


class RoleforgeScheduler:
    """In-process scheduler that runs approved job entrypoints."""

    def __init__(self, jobs: Iterable[SchedulerJob] | None = None, *, now: datetime | None = None) -> None:
        self.jobs = list(jobs or build_default_jobs())
        self.now = now or _utc_now()
        self.state: dict[str, ScheduledState] = {
            job.name: _initial_state_for(job, self.now) for job in self.jobs
        }

    def _next_run_for(self, job: SchedulerJob, now: datetime) -> datetime:
        if job.daily_at_utc is not None:
            return _next_daily_run(now, job.daily_at_utc)
        if job.interval_seconds is None:
            raise ValueError(f"Job {job.name} missing interval or daily_at_utc")
        return now + timedelta(seconds=job.interval_seconds)

    def tick(self, *, now: datetime | None = None) -> list[dict[str, Any]]:
        """Run every due job once and return job execution results."""
        now = now or _utc_now()
        results: list[dict[str, Any]] = []

        for job in self.jobs:
            state = self.state[job.name]
            if state.next_run_at > now:
                continue

            log_struct(
                "info",
                "scheduler_job_start",
                f"scheduler started job: {job.name}",
                job_name=job.name,
                next_run_at=state.next_run_at.isoformat(),
            )
            started_at = now
            status = "success"
            summary: dict[str, Any]
            try:
                summary = job.runner()
            except Exception as exc:  # noqa: BLE001 - per-job boundary
                status = "failure"
                summary = {"message": str(exc)}
            finished_at = now
            state.last_run_at = finished_at
            state.last_status = status
            state.last_summary = summary
            state.next_run_at = self._next_run_for(job, finished_at)

            result = {
                "job_name": job.name,
                "status": status,
                "started_at": started_at.isoformat(),
                "finished_at": finished_at.isoformat(),
                "next_run_at": state.next_run_at.isoformat(),
                "summary": summary,
            }
            results.append(result)
            log_struct(
                "info" if status == "success" else "error",
                "scheduler_job_finish",
                f"scheduler finished job: {job.name} status={status}",
                job_name=job.name,
                status=status,
                summary=summary,
                next_run_at=state.next_run_at.isoformat(),
            )

        return results

    def sleep_until_next_run(self, *, max_sleep_seconds: int = 60) -> float:
        """Return seconds until the next due job, capped for responsive loops."""
        now = _utc_now()
        next_due = min((state.next_run_at for state in self.state.values()), default=None)
        if next_due is None:
            return float(max_sleep_seconds)
        delay = (next_due - now).total_seconds()
        if delay <= 0:
            return 0.0
        return min(delay, float(max_sleep_seconds))

    def run_forever(self, *, max_sleep_seconds: int = 60) -> None:
        """Run the scheduler loop until interrupted."""
        log_struct("info", "scheduler_start", "scheduler loop started")
        try:
            while True:
                self.tick()
                sleep_for = self.sleep_until_next_run(max_sleep_seconds=max_sleep_seconds)
                time.sleep(max(1.0, sleep_for))
        except KeyboardInterrupt:
            log_struct("info", "scheduler_stop", "scheduler loop stopped by keyboard interrupt")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the RoleForge in-process scheduler.")
    parser.add_argument("--once", action="store_true", help="Run one tick and exit.")
    parser.add_argument(
        "--max-sleep-seconds",
        type=int,
        default=60,
        help="Maximum sleep between ticks in loop mode.",
    )
    args = parser.parse_args()

    scheduler = RoleforgeScheduler()
    if args.once:
        result = scheduler.tick()
        print(json.dumps({"jobs_run": result}, indent=2))
        return

    scheduler.run_forever(max_sleep_seconds=args.max_sleep_seconds)


if __name__ == "__main__":
    main()
