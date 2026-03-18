"""
AI enrichment for interview events (TASK-081, TASK-082).

Writes bounded, prompt-versioned artifacts into interview_events.notes:
- ai_briefing: company briefer artifact
- prep_checklist: preparation checklist artifact

Governance:
- disabled by default (INTERVIEW_AI_ENRICH_ENABLED=false)
- pinned model (PRIMARY_AI_PROVIDER + INTERVIEW_AI_MODEL)
- per-run cap (INTERVIEW_AI_MAX_PER_RUN)
- cost visible in job_runs.summary.ai_cost_usd when enabled
"""

from __future__ import annotations

import argparse
import json
from typing import Any

from roleforge.interview_event_ai import enrich_company_briefing, enrich_prep_checklist
from roleforge.job_runs import log_job_finish, log_job_start
from roleforge.runtime import connect_db, get_setting, load_jsonb


JOB_TYPE = "interview_event_ai_enrich"


def _enabled() -> bool:
    raw = (get_setting("INTERVIEW_AI_ENRICH_ENABLED") or "").strip().lower()
    return raw in ("1", "true", "yes", "on")


def _reenrich_enabled() -> bool:
    raw = (get_setting("INTERVIEW_AI_REENRICH") or "").strip().lower()
    return raw in ("1", "true", "yes", "on")


def _int_setting(name: str, default: int) -> int:
    raw = get_setting(name)
    if raw in (None, ""):
        return default
    assert raw is not None
    return int(raw)


def _select_candidates(conn: Any, *, limit: int) -> list[dict[str, Any]]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                ie.id,
                ie.notes,
                v.company,
                v.title,
                COALESCE(vo.raw_snippet, '') AS raw_snippet
            FROM interview_events ie
            JOIN applications a ON a.id = ie.application_id
            JOIN vacancies v ON v.id = a.vacancy_id
            LEFT JOIN LATERAL (
                SELECT raw_snippet
                FROM vacancy_observations
                WHERE vacancy_id = v.id
                ORDER BY created_at ASC NULLS LAST
                LIMIT 1
            ) vo ON true
            ORDER BY ie.created_at ASC
            LIMIT %s
            """,
            (int(limit),),
        )
        rows = cur.fetchall()
    out: list[dict[str, Any]] = []
    for r in rows:
        out.append(
            {
                "interview_event_id": r[0],
                "notes": r[1],
                "company": r[2],
                "title": r[3],
                "raw_snippet": r[4],
            }
        )
    return out


def _should_skip_existing(existing: dict[str, Any], key: str, *, allow_reenrich: bool) -> bool:
    if not existing:
        return False
    if allow_reenrich:
        return False
    value = existing.get(key)
    return value is not None


def _update_notes(conn: Any, interview_event_id: Any, patch: dict[str, Any]) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE interview_events
            SET notes = COALESCE(notes, '{}'::jsonb) || %s::jsonb
            WHERE id = %s
            """,
            (json.dumps(patch), interview_event_id),
        )


def run_once(*, max_per_run: int | None = None) -> dict[str, Any]:
    conn = connect_db()
    run_id = log_job_start(conn, JOB_TYPE)
    try:
        if not _enabled():
            summary = {"run_id": str(run_id), "status": "success", "enabled": False, "ai_cost_usd": 0.0}
            log_job_finish(conn, run_id, "success", summary)
            return summary

        cap = max_per_run if max_per_run is not None else _int_setting("INTERVIEW_AI_MAX_PER_RUN", 10)
        allow_reenrich = _reenrich_enabled()

        candidates = _select_candidates(conn, limit=cap)
        briefing_ok = 0
        checklist_ok = 0
        skipped_existing = 0
        failures = 0
        total_cost = 0.0

        for item in candidates:
            notes = load_jsonb(item.get("notes"))
            patch: dict[str, Any] = {}

            if _should_skip_existing(notes, "ai_briefing", allow_reenrich=allow_reenrich) and _should_skip_existing(
                notes, "prep_checklist", allow_reenrich=allow_reenrich
            ):
                skipped_existing += 1
                continue

            try:
                if not _should_skip_existing(notes, "ai_briefing", allow_reenrich=allow_reenrich):
                    artifact, cost = enrich_company_briefing(
                        company=item.get("company"),
                        title=item.get("title"),
                        body_excerpt=item.get("raw_snippet") or "",
                    )
                    patch["ai_briefing"] = artifact
                    briefing_ok += 1
                    if cost is not None:
                        total_cost += cost

                if not _should_skip_existing(notes, "prep_checklist", allow_reenrich=allow_reenrich):
                    artifact, cost = enrich_prep_checklist(
                        company=item.get("company"),
                        title=item.get("title"),
                        body_excerpt=item.get("raw_snippet") or "",
                    )
                    patch["prep_checklist"] = artifact
                    checklist_ok += 1
                    if cost is not None:
                        total_cost += cost

                if patch:
                    _update_notes(conn, item["interview_event_id"], patch)
            except Exception:
                failures += 1

        conn.commit()
        summary = {
            "run_id": str(run_id),
            "status": "success",
            "enabled": True,
            "candidates_considered": len(candidates),
            "briefings_ok": briefing_ok,
            "checklists_ok": checklist_ok,
            "skipped_existing": skipped_existing,
            "failures": failures,
            "ai_cost_usd": round(total_cost, 6),
            "max_per_run": int(cap),
            "reenrich": bool(allow_reenrich),
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
    parser = argparse.ArgumentParser(description="AI enrich interview_events notes (company briefer + prep checklist).")
    parser.add_argument("--max-per-run", type=int, help="Override INTERVIEW_AI_MAX_PER_RUN for this run.")
    args = parser.parse_args()
    result = run_once(max_per_run=args.max_per_run)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()

