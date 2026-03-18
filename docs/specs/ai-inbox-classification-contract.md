# AI Inbox Classification Contract (TASK-074)

**Scope:** Define when and how to call AI for ambiguous Gmail messages that the deterministic inbox classifier could not classify. Output is merged into `gmail_messages.classified_as`. No AI in the core rule path; this contract applies only to the optional fallback step.

**Refs:** [Inbox classifier](inbox-classifier.md), [v5 application lifecycle](v5-application-lifecycle.md), [AI enrichment contract](ai-enrichment-contract.md), [AI governance](../architecture.md#ai-governance-v4-task-067).

---

## 1. Purpose

- **Goal:** When the rule-first classifier leaves `classified_as = NULL` (ambiguous), an optional AI step may classify the message. The result is written to the same column; authority remains advisory—operator and Telegram stay the control surface.
- **Gating:** AI classification runs only for messages that (a) have no existing non-null `classified_as`, and (b) are explicitly eligible for AI fallback (e.g. marked ambiguous or selected by the classification job). Deterministic rules always run first; AI is a second pass.

---

## 2. When to call AI

- **Eligibility:** Call AI only for a message that:
  1. Has `classified_as IS NULL` after the deterministic classifier run (first-write-wins: we do not overwrite an existing non-null value unless a future “reclassify” mode is introduced).
  2. Is selected by the classification job for AI fallback (e.g. all unclassified, or only those with `classification_metadata->>'ambiguous' = 'true'` if we add that field).
- **Cap per run:** Hard cap on number of AI classification calls per job run (e.g. 50 or 100) to limit cost. When cap is hit, skip remaining; log in `job_runs.summary` (e.g. `ai_classifications_skipped_cap`).
- **No blocking:** If the AI call fails (timeout, rate limit, parse error), leave `classified_as` NULL and continue. Do not block the classification job or the rest of the pipeline.

---

## 3. Input contract (to the model)

Send only the minimum needed for a three-way decision. No operator PII.

| Field        | Type   | Description |
|-------------|--------|-------------|
| `subject`   | str    | Subject line (from headers). Empty string if missing. |
| `snippet`   | str    | Short body snippet (e.g. first 300–500 chars of body_plain). Truncated to fixed max. |
| `from_domain` | str  | Sender domain extracted from From/Reply-To (e.g. `company.com`). Empty if unparseable. |

- **Size limits:** `snippet` truncated to a fixed max (e.g. 500 chars). `subject` truncated (e.g. 200 chars).
- **Privacy:** Do not send full body, thread IDs, message IDs, or any operator identity. Do not log full prompt or response.

---

## 4. Output contract (from the model)

- **Stored:** Result is written to `gmail_messages.classified_as` as one of: `vacancy_alert`, `employer_reply`, `other`.
- **Parsing:** Response must be normalized to exactly one of these three. If the model returns something else or parse fails, do not write; treat as AI failure and leave `classified_as` NULL.
- **Metadata (optional):** If we add a `classification_metadata` JSONB column or reuse an existing field, we may store: `model`, `prompt_version`, `classified_at` (ISO 8601). Not required for MVP; the main contract is writing to `classified_as`.

---

## 5. Provider, model, and prompt

- **Provider:** Same primary provider as enrichment (`PRIMARY_AI_PROVIDER`). One provider per deployment.
- **Model:** Same shortlist as enrichment (e.g. `gpt-4o-mini`, Haiku). May use the same model or a cheaper one; model must be pinned (no “latest”).
- **Prompt:** Stored in code under `roleforge/prompts/` (e.g. `inbox_classification.py`). Versioned with `PROMPT_VERSION`; when the prompt changes, the version changes. Instructions: given subject, snippet, and sender domain, respond with exactly one of: `vacancy_alert`, `employer_reply`, `other`.

---

## 6. Timeout, retry, and fallback

- **Timeout:** Single call timeout (e.g. 10–15 s). On timeout, treat as transient; do not retry indefinitely.
- **Retry:** Per [Retry and fallback policy](retry-and-fallback-policy.md): transient errors → bounded retries (e.g. max 2 per message with backoff). Permanent errors → no retry; skip that message.
- **Fallback:** On any failure, leave `classified_as` NULL and continue. Log count in `job_runs.summary` (e.g. `ai_classification_failures: N`). Pipeline and downstream jobs (replay, digest) do not depend on AI classification.

---

## 7. Cost and job summary

- **Per-run cost:** If the classification job calls AI, add **`ai_cost_usd`** to `job_runs.summary` (same field as enrichment; sum token-based cost for the run). See [Cost governance](cost-governance.md).
- **Logging:** Do not log full prompt or full model response. Log only: job_type, run_id, counts (e.g. `ai_classifications_ok`, `ai_classification_failures`, `ai_classifications_skipped_cap`), `ai_cost_usd`, model, prompt_version.

---

## 8. Merge rule with deterministic result

- **Order of operations:** (1) Run deterministic classifier. (2) For messages still with `classified_as IS NULL` and eligible for AI, call AI. (3) Write AI result only when current value is NULL.
- **Idempotency:** If the job is re-run, deterministic rules run again; existing non-null `classified_as` is not overwritten. AI is only invoked for rows that are still NULL after the deterministic pass (or in a dedicated “reclassify ambiguous” mode if we add it).

---

## 9. Implementation tasks (after this spec)

| Task        | Role |
|------------|------|
| **TASK-075** | Implement deterministic classifier; no AI yet. |
| **TASK-076** | Run classification as a job; deterministic only, or deterministic + optional AI fallback when implemented. |
| **Follow-up** | Add AI classification step to the job (prompt module, provider call, write to `classified_as`, cost in summary); gate by eligibility and cap. |

---

## 10. Summary

| Item       | Decision |
|-----------|----------|
| When      | Only when `classified_as` is NULL and message is in AI-eligible set; cap per run. |
| Input     | subject, snippet, from_domain; no PII; bounded size. |
| Output    | One of vacancy_alert, employer_reply, other → `classified_as`. |
| Merge     | Write only if current value is NULL. |
| Failure   | Leave NULL; do not block; log counts and cost. |
| Provider  | Same as enrichment; pinned model; versioned prompt. |
