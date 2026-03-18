"""
AI enrichment for interview events (TASK-081, TASK-082).

Uses the same governance discipline as vacancy enrichment:
- PRIMARY_AI_PROVIDER (openai | anthropic) with pinned model
- prompt versioning via roleforge.prompts.*
- bounded outputs
- graceful degradation (caller decides whether to skip/continue)
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Callable

from roleforge.prompts.enrichment import prompt_hash_text
from roleforge.retry import is_permanent_ai, is_transient_ai, with_retry
from roleforge.runtime import get_setting

from roleforge.prompts.interview_company_briefing import (
    PROMPT_VERSION as BRIEF_PROMPT_VERSION,
    SYSTEM_PROMPT as BRIEF_SYSTEM_PROMPT,
    build_user_prompt as build_brief_user_prompt,
)
from roleforge.prompts.interview_prep_checklist import (
    PROMPT_VERSION as CHECK_PROMPT_VERSION,
    SYSTEM_PROMPT as CHECK_SYSTEM_PROMPT,
    build_user_prompt as build_check_user_prompt,
)


DEFAULT_MODEL_OPENAI = "gpt-4o-mini"
DEFAULT_MODEL_ANTHROPIC = "claude-3-5-haiku-20241022"

INTERVIEW_AI_TIMEOUT_SEC = 25

MAX_BRIEF_CHARS = 1400
MAX_CHECKLIST_CHARS = 1200


def _get_provider_and_model() -> tuple[str, str]:
    provider = (get_setting("PRIMARY_AI_PROVIDER") or "openai").strip().lower()
    if provider == "anthropic":
        model = get_setting("INTERVIEW_AI_MODEL") or DEFAULT_MODEL_ANTHROPIC
        return "anthropic", model
    provider = "openai"
    model = get_setting("INTERVIEW_AI_MODEL") or DEFAULT_MODEL_OPENAI
    return provider, model


def _call_openai(user_text: str, system_text: str, model: str, *, max_tokens: int) -> tuple[str, float | None]:
    import openai  # type: ignore[import-not-found]

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
        max_tokens=max_tokens,
        timeout=INTERVIEW_AI_TIMEOUT_SEC,
    )
    text = (resp.choices[0].message.content or "").strip()
    text = re.sub(r"\s+\n", "\n", text).strip()
    cost: float | None = None
    if resp.usage:
        cost = (resp.usage.prompt_tokens * 0.15 / 1e6) + (resp.usage.completion_tokens * 0.60 / 1e6)
    return text, cost


def _call_anthropic(user_text: str, system_text: str, model: str, *, max_tokens: int) -> tuple[str, float | None]:
    import anthropic  # type: ignore[import-not-found]

    api_key = get_setting("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY not set")
    client = anthropic.Anthropic(api_key=api_key)
    resp = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=system_text,
        messages=[{"role": "user", "content": user_text}],
        timeout=INTERVIEW_AI_TIMEOUT_SEC,
    )
    text = ""
    for block in resp.content:
        if hasattr(block, "text"):
            text += block.text
    text = text.strip()
    cost: float | None = None
    if resp.usage:
        cost = (resp.usage.input_tokens * 0.80 / 1e6) + (resp.usage.output_tokens * 4.0 / 1e6)
    return text, cost


def _call_ai(user_text: str, system_text: str, *, max_tokens: int) -> tuple[str, str, float | None]:
    provider, model = _get_provider_and_model()

    def _do_call() -> tuple[str, float | None]:
        if provider == "openai":
            return _call_openai(user_text, system_text, model, max_tokens=max_tokens)
        if provider == "anthropic":
            return _call_anthropic(user_text, system_text, model, max_tokens=max_tokens)
        raise RuntimeError(f"Unknown PRIMARY_AI_PROVIDER: {provider}")

    text, cost_usd = with_retry(
        _do_call,
        is_transient=is_transient_ai,
        is_permanent=is_permanent_ai,
        max_attempts=3,
        backoff_base_sec=1.0,
    )
    return model, text, cost_usd


def enrich_company_briefing(*, company: str | None, title: str | None, body_excerpt: str) -> tuple[dict[str, Any], float | None]:
    user_text = build_brief_user_prompt(company=company, title=title, body_excerpt=(body_excerpt or "")[:2500])
    system_text = BRIEF_SYSTEM_PROMPT
    prompt_hash = prompt_hash_text(system_text, user_text)
    model, text, cost = _call_ai(user_text, system_text, max_tokens=400)
    text = re.sub(r"[ \t]+", " ", text).strip()
    if len(text) > MAX_BRIEF_CHARS:
        text = text[:MAX_BRIEF_CHARS].rstrip()
    if not text:
        raise ValueError("AI returned empty company briefing")
    artifact = {
        "text": text,
        "model": model,
        "prompt_version": BRIEF_PROMPT_VERSION,
        "prompt_hash": prompt_hash,
        "enriched_at": datetime.now(timezone.utc).isoformat(),
    }
    return artifact, cost


def enrich_prep_checklist(*, company: str | None, title: str | None, body_excerpt: str) -> tuple[dict[str, Any], float | None]:
    user_text = build_check_user_prompt(company=company, title=title, body_excerpt=(body_excerpt or "")[:2500])
    system_text = CHECK_SYSTEM_PROMPT
    prompt_hash = prompt_hash_text(system_text, user_text)
    model, text, cost = _call_ai(user_text, system_text, max_tokens=350)
    text = text.strip()
    if not text:
        raise ValueError("AI returned empty prep checklist")

    # Enforce bounded, line-based checklist. Keep first 8 "- " lines; otherwise coerce by splitting.
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    checklist_lines = [ln for ln in lines if ln.startswith("- ")]
    if len(checklist_lines) < 8:
        # Coerce: treat non-empty lines as items.
        checklist_lines = [("- " + ln.lstrip("- ").strip()) for ln in lines]
    checklist_lines = checklist_lines[:8]
    checklist_lines = [ln[:124].rstrip() for ln in checklist_lines]
    final_text = "\n".join(checklist_lines).strip()
    if len(final_text) > MAX_CHECKLIST_CHARS:
        final_text = final_text[:MAX_CHECKLIST_CHARS].rstrip()

    artifact = {
        "text": final_text,
        "model": model,
        "prompt_version": CHECK_PROMPT_VERSION,
        "prompt_hash": prompt_hash,
        "enriched_at": datetime.now(timezone.utc).isoformat(),
    }
    return artifact, cost

