"""
Run one feed polling cycle: fetch enabled feeds, normalize/dedup, persist (TASK-047).

Same pipeline shape as gmail_poll + replay: no new infra; job_runs type 'feed_poll'.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from roleforge.dedup import group_by_dedup_key, persist_deduped
from roleforge.feed_reader import fetch_feed_candidates
from roleforge.feed_registry import get_enabled_feeds
from roleforge.job_runs import log_job_finish, log_job_start
from roleforge.runtime import connect_db


def _seen_feed_source_keys(conn) -> set[str]:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT DISTINCT feed_source_key FROM vacancy_observations WHERE feed_source_key IS NOT NULL AND feed_source_key != ''"
        )
        return {row[0] for row in cur.fetchall()}


def run_once(*, registry_path: Path | None = None) -> dict:
    conn = connect_db()
    run_id = log_job_start(conn, "feed_poll")
    try:
        feeds = get_enabled_feeds(path=registry_path)
        if not feeds:
            summary = {
                "run_id": str(run_id),
                "status": "success",
                "feeds_checked": 0,
                "entries_processed": 0,
                "vacancies_created": 0,
                "message": "no enabled feeds or feed intake disabled",
            }
            log_job_finish(conn, run_id, "success", summary)
            return summary

        seen = _seen_feed_source_keys(conn)
        all_candidates = []
        for feed in feeds:
            fid = feed["id"]
            url = feed["url"]
            try:
                candidates = fetch_feed_candidates(fid, url, seen)
                all_candidates.extend(candidates)
                for c in candidates:
                    seen.add(c.get("feed_source_key") or "")
            except Exception as e:
                summary = {
                    "run_id": str(run_id),
                    "status": "failure",
                    "feed_id": fid,
                    "message": str(e),
                }
                log_job_finish(conn, run_id, "failure", summary)
                raise

        if not all_candidates:
            summary = {
                "run_id": str(run_id),
                "status": "success",
                "feeds_checked": len(feeds),
                "entries_processed": 0,
                "vacancies_created": 0,
            }
            log_job_finish(conn, run_id, "success", summary)
            return summary

        grouped = group_by_dedup_key(all_candidates)
        vacancy_ids = persist_deduped(conn, grouped)
        summary = {
            "run_id": str(run_id),
            "status": "success",
            "feeds_checked": len(feeds),
            "entries_processed": len(all_candidates),
            "vacancies_created": len(vacancy_ids),
        }
        log_job_finish(conn, run_id, "success", summary)
        return summary
    except Exception as exc:
        summary = {"run_id": str(run_id), "status": "failure", "message": str(exc)}
        log_job_finish(conn, run_id, "failure", summary)
        raise
    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run one feed poll and persist new entries via normalize/dedup.")
    parser.add_argument("--registry", type=Path, default=None, help="Path to feeds.yaml (default: config/feeds.yaml)")
    args = parser.parse_args()
    result = run_once(registry_path=args.registry)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
