"""
Poll enabled market monitors and persist new vacancies (TASK-087, EPIC-18).

Currently supported: HH.ru public API monitor. The job reads config/monitors.yaml,
runs enabled monitors, dedups into vacancies, and records the run in job_runs.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from roleforge.dedup import group_by_dedup_key, persist_deduped
from roleforge.job_runs import log_job_finish, log_job_start
from roleforge.monitor_registry import get_enabled_monitors
from roleforge.monitors.hh import fetch_candidates as fetch_hh_candidates
from roleforge.runtime import connect_db


def _seen_monitor_source_keys(conn: Any) -> set[str]:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT DISTINCT feed_source_key FROM vacancy_observations WHERE feed_source_key LIKE 'monitor:%'"
        )
        return {row[0] for row in cur.fetchall() if row and row[0]}


def run_once(*, registry_path: Path | None = None) -> dict[str, Any]:
    conn = connect_db()
    run_id = log_job_start(conn, "monitor_poll")
    try:
        monitors = get_enabled_monitors(path=registry_path)
        if not monitors:
            summary = {
                "run_id": str(run_id),
                "status": "success",
                "monitors_checked": 0,
                "monitors_ran": 0,
                "entries_processed": 0,
                "vacancies_created": 0,
                "message": "no enabled monitors or monitor intake disabled",
            }
            log_job_finish(conn, run_id, "success", summary)
            return summary

        seen = _seen_monitor_source_keys(conn)
        monitor_results: list[dict[str, Any]] = []
        entries_processed = 0
        vacancies_created = 0
        monitor_failures = 0

        for monitor in monitors:
            monitor_id = monitor["id"]
            monitor_type = monitor["type"]
            if monitor_type != "hh_api":
                monitor_failures += 1
                monitor_results.append(
                    {
                        "monitor_id": monitor_id,
                        "status": "failure",
                        "message": f"unsupported monitor type: {monitor_type}",
                    }
                )
                continue
            try:
                candidates = fetch_hh_candidates(monitor_id, monitor.get("params") or {}, seen)
                for candidate in candidates:
                    source_key = candidate.get("feed_source_key") or ""
                    if source_key:
                        seen.add(source_key)
                grouped = group_by_dedup_key(candidates)
                vacancy_ids = persist_deduped(conn, grouped) if grouped else []
                entries_processed += len(candidates)
                vacancies_created += len(vacancy_ids)
                monitor_results.append(
                    {
                        "monitor_id": monitor_id,
                        "monitor_type": monitor_type,
                        "status": "success",
                        "entries_processed": len(candidates),
                        "vacancies_created": len(vacancy_ids),
                    }
                )
            except Exception as exc:  # noqa: BLE001 - per-monitor isolation
                monitor_failures += 1
                monitor_results.append(
                    {
                        "monitor_id": monitor_id,
                        "monitor_type": monitor_type,
                        "status": "failure",
                        "message": str(exc),
                    }
                )

        status = "success" if monitor_failures < len(monitors) else "failure"
        summary: dict[str, Any] = {
            "run_id": str(run_id),
            "status": status,
            "monitors_checked": len(monitors),
            "monitors_ran": len([m for m in monitor_results if m.get("status") == "success"]),
            "monitor_failures": monitor_failures,
            "entries_processed": entries_processed,
            "vacancies_created": vacancies_created,
            "monitor_ids": [m["id"] for m in monitors],
            "monitor_results": monitor_results,
        }
        if status == "failure":
            summary["message"] = "all enabled monitors failed"
        log_job_finish(conn, run_id, status, summary)
        return summary
    except Exception as exc:
        summary = {"run_id": str(run_id), "status": "failure", "message": str(exc)}
        log_job_finish(conn, run_id, "failure", summary)
        raise
    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Poll enabled HH.ru market monitors once.")
    parser.add_argument("--registry", type=Path, default=None, help="Path to monitors.yaml (default: config/monitors.yaml)")
    args = parser.parse_args()
    result = run_once(registry_path=args.registry)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
