"""
AI vacancy enrichment (TASK-063, EPIC-15).

Post-scoring only: generates a short summary for high-score vacancies and stores
it in vacancies.ai_metadata. Uses PRIMARY_AI_PROVIDER (openai | anthropic) and
pinned model. See docs/specs/ai-enrichment-contract.md.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from roleforge.prompts.enrichment import (
    PROMPT_VERSION,
    SYSTEM_PROMPT,
    build_user_prompt,
    prompt_hash_text,
)
from roleforge.retry import is_permanent_ai, is_transient_ai, with_retry
from roleforge.runtime import get_setting

# Default models per provider (contract: pin explicit version)
DEFAULT_MODEL_OPENAI = "gpt-4o-mini"
DEFAULT_MODEL_ANTHROPIC = "claude-3-5-haiku-20241022"

# Max summary length stored (contract)
MAX_SUMMARY_CHARS = 500

# Request timeout seconds (contract: 15-30)
ENRICHMENT_TIMEOUT_SEC = 25


def _get_provider_and_model() -> tuple[str, str]:
    provider = (get_setting("PRIMARY_AI_PROVIDER") or "openai").strip().lower()
    if provider == "anthropic":
        model = get_setting("AI_ENRICHMENT_MODEL") or DEFAULT_MODEL_ANTHROPIC
        return "anthropic", model
    provider = "openai"
    model = get_setting("AI_ENRICHMENT_MODEL") or DEFAULT_MODEL_OPENAI
    return provider, model


def _call_openai(user_text: str, system_text: str, model: str) -> tuple[str, float | None]:
    import openai

    api_key = get_setting("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY not set")
    client = openai.OpenAI(api_key=api_key)
    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_text},
            {"role": "user", "content": user_text},
        ],
        max_tokens=256,
        timeout=ENRICHMENT_TIMEOUT_SEC,
    )
    summary = (resp.choices[0].message.content or "").strip()
    summary = re.sub(r"\s+", " ", summary)[:MAX_SUMMARY_CHARS]
    cost: float | None = None
    if resp.usage:
        # Rough gpt-4o-mini: input ~$0.15/1M, output ~$0.60/1M
        cost = (resp.usage.prompt_tokens * 0.15 / 1e6) + (resp.usage.completion_tokens * 0.60 / 1e6)
    return summary, cost


def _call_anthropic(user_text: str, system_text: str, model: str) -> tuple[str, float | None]:
    import anthropic

    api_key = get_setting("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY not set")
    client = anthropic.Anthropic(api_key=api_key)
    resp = client.messages.create(
        model=model,
        max_tokens=256,
        system=system_text,
        messages=[{"role": "user", "content": user_text}],
        timeout=ENRICHMENT_TIMEOUT_SEC,
    )
    text = ""
    for block in resp.content:
        if hasattr(block, "text"):
            text += block.text
    summary = text.strip()
    summary = re.sub(r"\s+", " ", summary)[:MAX_SUMMARY_CHARS]
    cost = None
    if resp.usage:
        # Rough Haiku: input ~$0.80/1M, output ~$4/1M
        cost = (resp.usage.input_tokens * 0.80 / 1e6) + (resp.usage.output_tokens * 4.0 / 1e6)
    return summary, cost


def enrich_one(
    *,
    title: str | None = None,
    company: str | None = None,
    location: str | None = None,
    salary_raw: str | None = None,
    body_excerpt: str = "",
) -> tuple[dict[str, Any], float | None]:
    """
    Call the configured AI provider to produce a vacancy summary.

    body_excerpt should be truncated by the caller (e.g. 2000–4000 chars).
    Returns (ai_metadata dict, estimated_cost_usd or None).
    Raises on permanent error; transient errors are retried via with_retry.
    """
    user_text = build_user_prompt(
        title=title,
        company=company,
        location=location,
        salary_raw=salary_raw,
        body_excerpt=(body_excerpt or "")[:4000],
    )
    system_text = SYSTEM_PROMPT
    prompt_hash = prompt_hash_text(system_text, user_text)

    provider, model = _get_provider_and_model()

    def _do_call() -> tuple[str, float | None]:
        if provider == "openai":
            return _call_openai(user_text, system_text, model)
        if provider == "anthropic":
            return _call_anthropic(user_text, system_text, model)
        raise RuntimeError(f"Unknown PRIMARY_AI_PROVIDER: {provider}")

    summary, cost_usd = with_retry(
        _do_call,
        is_transient=is_transient_ai,
        is_permanent=is_permanent_ai,
        max_attempts=3,
        backoff_base_sec=1.0,
    )

    if not summary:
        raise ValueError("AI returned empty summary")
    summary = summary[:MAX_SUMMARY_CHARS]

    ai_metadata = {
        "summary": summary,
        "model": model,
        "prompt_version": PROMPT_VERSION,
        "prompt_hash": prompt_hash,
        "enriched_at": datetime.now(timezone.utc).isoformat(),
    }
    return ai_metadata, cost_usd


def update_vacancy_ai_metadata(conn: Any, vacancy_id: Any, ai_metadata: dict[str, Any]) -> None:
    """Write ai_metadata to vacancies for the given vacancy_id."""
    import json

    with conn.cursor() as cur:
        cur.execute(
            "UPDATE vacancies SET ai_metadata = %s::jsonb WHERE id = %s",
            (json.dumps(ai_metadata), vacancy_id),
        )
        conn.commit()


def run_enrichment_for_high_scores(
    conn: Any,
    *,
    min_score: float = 0.75,
    max_per_run: int = 20,
) -> dict[str, Any]:
    """
    Enrich high-score vacancies that do not yet have ai_metadata (TASK-064).

    Selects vacancies with at least one profile_match with score >= min_score
    and ai_metadata IS NULL, up to max_per_run. For each, fetches body excerpt
    from vacancy_observations.raw_snippet, calls enrich_one, and writes
    ai_metadata. On failure for a vacancy, continues (graceful degradation).

    Returns a summary dict suitable for job_runs.summary, including
    enrichments_ok, enrichment_failures, enrichments_skipped_cap, and
    ai_cost_usd (TASK-065). Caller must merge this into log_job_finish(..., summary).
    """
    min_score = float(get_setting("AI_ENRICHMENT_MIN_SCORE") or min_score)
    max_per_run = int(get_setting("AI_ENRICHMENT_MAX_PER_RUN") or max_per_run)

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT v.id, v.title, v.company, v.location, v.salary_raw
            FROM vacancies v
            INNER JOIN profile_matches pm ON pm.vacancy_id = v.id
            WHERE v.ai_metadata IS NULL AND pm.score >= %s
            GROUP BY v.id, v.title, v.company, v.location, v.salary_raw
            ORDER BY MAX(pm.score) DESC
            LIMIT %s
            """,
            (min_score, max_per_run),
        )
        rows = cur.fetchall()

    if not rows:
        return {"enrichments_ok": 0, "enrichment_failures": 0, "enrichments_skipped_cap": 0, "ai_cost_usd": 0.0}

    enrichments_ok = 0
    enrichment_failures = 0
    total_cost: float = 0.0
    body_excerpt_max = 4000

    for (vacancy_id, title, company, location, salary_raw) in rows:
        body_excerpt = ""
        with conn.cursor() as cur:
            cur.execute(
                "SELECT raw_snippet FROM vacancy_observations WHERE vacancy_id = %s LIMIT 1",
                (vacancy_id,),
            )
            row = cur.fetchone()
            if row and row[0]:
                body_excerpt = (row[0] or "")[:body_excerpt_max]

        try:
            meta, cost = enrich_one(
                title=title,
                company=company,
                location=location,
                salary_raw=salary_raw,
                body_excerpt=body_excerpt,
            )
            update_vacancy_ai_metadata(conn, vacancy_id, meta)
            enrichments_ok += 1
            if cost is not None:
                total_cost += cost
        except Exception:
            enrichment_failures += 1

    return {
        "enrichments_ok": enrichments_ok,
        "enrichment_failures": enrichment_failures,
        "enrichments_skipped_cap": 0,
        "ai_cost_usd": round(total_cost, 6),
    }
