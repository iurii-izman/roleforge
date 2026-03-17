# AI Enrichment Contract (TASK-062, EPIC-15)

**Scope:** Define the contract for post-scoring AI enrichment (vacancy summarizer) before any runtime AI implementation. Enrichment is additive only; it never blocks the deterministic pipeline.

**Refs:** docs/research-v4-plus.md §4.1, §6.5, §6.6; [Cost governance](cost-governance.md); [Job runs logging](job-runs-logging.md); [Retry and fallback policy](retry-and-fallback-policy.md).

---

## 1. Provider and model

- **Primary provider:** One provider per deployment, chosen in TASK-010 and exposed as `PRIMARY_AI_PROVIDER` (e.g. `openai` or `anthropic`). API key from keyring/env per [Bootstrap](../bootstrap-access.md).
- **Shortlist (MVP):**
  - **OpenAI:** `gpt-4o-mini` (default for cost-effective short summarization).
  - **Anthropic:** `claude-3-5-haiku-20241022` or current stable Haiku variant.
- **Default:** Use the provider from `PRIMARY_AI_PROVIDER` with the following default model per provider:
  - `openai` → `gpt-4o-mini`
  - `anthropic` → `claude-3-5-haiku-20241022` (or documented pinned Haiku ID).
- **Model pinning:** Always use an explicit model ID in code/config. Never use "latest" or unversioned aliases in production. Model choice is configurable only within the shortlist (env or config key) so that upgrades are explicit.
- **Dual-provider:** No dual-provider hot path in MVP; one provider per run.

---

## 2. Input contract (enrichment request)

Enrichment receives a single **vacancy** (and optional context) that has already been scored. Only fields needed for the prompt are passed to the AI.

**Required input shape (logical):**

| Field | Type | Description |
|-------|------|-------------|
| `vacancy_id` | UUID | For idempotency and storage. |
| `title` | str \| None | Job title. |
| `company` | str \| None | Company name. |
| `location` | str \| None | Location. |
| `salary_raw` | str \| None | Salary as stored. |
| `body_excerpt` | str | Truncated job description or parsed body for summarization (e.g. first 2000 chars). Empty string if none. |

**Source:** Built from `vacancies` row (and optionally one linked `vacancy_observations` / raw snippet). No PII beyond what is already in the vacancy (public job listing content). Do not send operator identity, Telegram chat IDs, or email content that is not the job description.

**Size limits:** `body_excerpt` must be truncated to a fixed max (e.g. 2000–4000 characters) so that prompt size is bounded and cost predictable.

---

## 3. Output contract (enrichment response)

**Stored shape:** `vacancies.ai_metadata` JSONB.

| Key | Type | Description |
|-----|------|-------------|
| `summary` | str | 2–3 sentence summary of the vacancy (plain text, no markdown). |
| `model` | str | Exact model ID used (e.g. `gpt-4o-mini`). |
| `prompt_version` | str | Version or identifier from prompt module (e.g. `summary_v1`). |
| `prompt_hash` | str | Optional short hash of prompt text for reproducibility (e.g. `sha256:abc...`). |
| `enriched_at` | str | ISO 8601 UTC timestamp when enrichment was written. |

**Parsing:** Implementation must validate that the model returns a single summary string; strip leading/trailing whitespace; reject or truncate if over max length (e.g. 500 chars). On parse failure, do not write `ai_metadata`; treat as enrichment failure and apply fallback (no retry of same vacancy in same run beyond policy below).

---

## 4. Gating rule (when enrichment runs)

- **Score band:** Enrichment runs only for vacancies that have at least one **profile_match** with `score >= enrichment_min_score`.
- **Default threshold:** `enrichment_min_score = 0.75` (high-score band). Align with `delivery_mode.immediate_threshold` so that enriched items are the same set eligible for immediate alerts when alerts are enabled.
- **Configurable:** The threshold may be read from a single global config or from the highest `delivery_mode.immediate_threshold` across profiles (so that “high signal” is consistent). Spec: one numeric threshold, env or config key (e.g. `AI_ENRICHMENT_MIN_SCORE`, default 0.75).
- **Per-vacancy:** A vacancy is enriched at most once per “enrichment run” (e.g. per scoring cycle or per explicit enrichment job). If `ai_metadata` is already present and prompt_version/model match current config, skip (idempotent). Optionally support re-enrich on prompt version change (TASK-066).
- **Cap per run:** Hard cap on number of enrichments per job run (e.g. max 20 or 50) to avoid runaway cost if many vacancies qualify. When cap is hit, skip remaining; log count in `job_runs.summary` (e.g. `enrichments_skipped_cap`).

---

## 5. Timeout, retry, and fallback (no blocking)

- **Timeout:** Single enrichment call timeout (e.g. 15–30 s). On timeout, treat as transient failure for that vacancy.
- **Retry:** Per [Retry and fallback policy](retry-and-fallback-policy.md) §4: transient errors (429, 503, timeout) → bounded retries (e.g. max 2 retries per vacancy with backoff). Permanent errors (401, 403, 400) → no retry; log and skip that vacancy.
- **Fallback:** If enrichment fails (after retries) or is skipped:
  - Do **not** block the deterministic pipeline. The vacancy remains in the DB without `ai_metadata`; delivery (digest, alert, queue) proceeds without the summary.
  - Optionally: set a flag in `job_runs.summary` (e.g. `enrichment_failures: N`) for visibility.
- **Pipeline order:** Enrichment runs **after** scoring and **after** profile_matches are written. It is a separate step or same job after scoring; scoring and delivery must not wait on enrichment.

---

## 6. Cost guardrails and ai_cost_usd

- **Per-run cost:** Every run that calls the AI must add **`ai_cost_usd`** to `job_runs.summary` (see [Job runs logging](job-runs-logging.md), [Cost governance](cost-governance.md)). Value is estimated from token usage (input + output) using provider-specific pricing or actual usage API when available.
- **Guardrails:**
  - Per-run cap: do not exceed a configured max enrichments per run (see §4); this caps cost per run.
  - No raw prompts or secrets in `summary`; only numeric cost and optional high-level metadata (model name, prompt version).
- **Monthly review:** Use the existing monthly query in [Cost governance](cost-governance.md) to sum `ai_cost_usd` by `job_type`; no new tables.

---

## 7. Prompt and versioning expectations

- **Location:** Prompts live in code under `roleforge/prompts/` (e.g. `roleforge/prompts/enrichment.py`). TASK-066 implements this pattern.
- **Versioning:** Each prompt module exposes a `PROMPT_VERSION` string (e.g. `"summary_v1"`). When the prompt text or instructions change, the version must change so that stored `ai_metadata.prompt_version` remains meaningful for audit and re-enrichment.
- **Hash (optional):** Store a short hash of the prompt body in `prompt_hash` for reproducibility. Implementation may use first 8–12 chars of SHA-256 of the final prompt string.
- **Re-enrichment:** When prompt version or model is upgraded, implementation may support re-enriching vacancies that have older `prompt_version` or `model`; this is an optional follow-up (e.g. batch job or on-next-view). Contract: stored `prompt_version` and `model` must always reflect the run that produced the summary.

---

## 8. Privacy and logging guardrails

- **Input to AI:** Only vacancy fields and `body_excerpt` derived from job listing content. No operator PII, no Telegram IDs, no email headers or bodies that are not the job description. Employer reply emails (v5) are out of scope for this contract.
- **Logging:** Do not log full prompt or full model response to stdout or to `job_runs.summary`. Log only: job_type, run_id, counts (enrichments_ok, enrichment_failures, enrichments_skipped_cap), `ai_cost_usd`, and optional model + prompt_version. Structured logs (JSON) must not contain raw vacancy text or summaries.
- **Storage:** Only the agreed `ai_metadata` shape is stored in `vacancies`. No extra AI payloads in other tables for this contract.

---

## 9. Path to implementation tasks

| Task | Dependency | Notes |
|------|------------|-------|
| **TASK-061** | None | Add `ai_metadata JSONB` to `vacancies`; migration idempotent. |
| **TASK-062** | None | This spec; contract and guardrails defined. |
| **TASK-063** | TASK-061, TASK-062 | Implement `roleforge/enrichment.py`: call provider, parse response, write `ai_metadata`; pin model; record prompt_version/prompt_hash. |
| **TASK-064** | TASK-063 | Add enrichment step after scoring (gating by score, cap per run); degrade gracefully on failure. |
| **TASK-065** | TASK-063 | Set `ai_cost_usd` in `job_runs.summary` when enrichment runs. |
| **TASK-066** | TASK-062 | Add `roleforge/prompts/enrichment.py` with `PROMPT_VERSION` and prompt text. |
| **TASK-067** | TASK-062 | Document AI governance rules in docs/architecture.md (model choice, prompt versioning, failure behavior). |

---

*Ref: TASK-062, EPIC-15; research-v4-plus.md §4.1, §6.5, §6.6.*
