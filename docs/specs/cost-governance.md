# Cost Governance (TASK-105)

**Scope:** Make recurring cost and operations review executable with current tooling. No new tables; use `job_runs.summary` and optional reporting scripts.

---

## 1. Cost sources in MVP

- **Postgres:** hosting/provider bill; not stored in app.
- **Telegram:** free for bot usage within normal limits.
- **Gmail API:** free within quota.
- **AI provider (OpenAI or Anthropic):** usage-based; the only cost we can track per run inside the app once enrichment runs.

---

## 2. AI cost reporting (TASK-104)

When AI enrichment is implemented (e.g. vacancy summarizer, v4):

- Jobs that call the AI provider should set **`ai_cost_usd`** in `job_runs.summary` for that run (e.g. from provider usage/cost API or estimated from token counts).
- **Guardrails:** No secrets or raw prompts in `summary`; only the numeric cost and optional high-level metadata (e.g. model name, prompt version).
- **Contract:** See [Job runs logging](job-runs-logging.md) for the summary shape; `ai_cost_usd` is optional and additive.

Until enrichment is live, `ai_cost_usd` will not appear in summaries; the reporting path below still applies once it is populated.

---

## 3. Monthly review query (TASK-105)

Run periodically (e.g. first day of month) to sum AI cost from `job_runs` for the previous calendar month. Assumes `summary` is JSONB and may contain `ai_cost_usd`.

```sql
-- AI cost for previous calendar month (UTC)
SELECT
  job_type,
  COUNT(*) AS runs,
  SUM((summary->>'ai_cost_usd')::numeric) AS ai_cost_usd
FROM job_runs
WHERE finished_at >= date_trunc('month', now() AT TIME ZONE 'UTC' - interval '1 month')
  AND finished_at < date_trunc('month', now() AT TIME ZONE 'UTC')
  AND status = 'success'
  AND summary ? 'ai_cost_usd'
GROUP BY job_type
ORDER BY job_type;
```

For a single “total last month” number:

```sql
SELECT COALESCE(SUM((summary->>'ai_cost_usd')::numeric), 0) AS ai_cost_usd_last_month
FROM job_runs
WHERE finished_at >= date_trunc('month', now() AT TIME ZONE 'UTC' - interval '1 month')
  AND finished_at < date_trunc('month', now() AT TIME ZONE 'UTC')
  AND status = 'success'
  AND summary ? 'ai_cost_usd';
```

---

## 4. Review cadence and checklist

- **Cadence:** Monthly (e.g. first week of the month for the previous month).
- **Checklist:**
  1. Run the monthly query above (or equivalent script) and record the total.
  2. Compare to budget or threshold if one is set.
  3. Check `job_runs` for repeated failures or unusual run counts that might indicate wasted calls.
  4. If enrichment is not yet implemented, the query returns zero/empty; keep the ritual so it is ready when `ai_cost_usd` is added.

---

## 5. Summary

- **Cost reporting path:** `job_runs.summary.ai_cost_usd` when enrichment runs; documented in job-runs-logging.md.
- **Monthly review:** SQL above; cadence and checklist in this spec.
- **No new tables:** All reporting is query-backed from existing `job_runs`.

---

*Ref: TASK-104, TASK-105, EPIC-20; job-runs-logging.md.*
