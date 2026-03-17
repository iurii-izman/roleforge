# Job Runs Logging and Execution Stats (TASK-036)

**Scope:** Every scheduled or triggered job records start, finish, status, and summary in `job_runs`. Operators see success/failure and stats without a separate platform.

---

## 1. Contract

- **Start:** Before doing work, call `roleforge.job_runs.log_job_start(conn, job_type)` → returns `run_id`.
- **Finish:** On exit (success or exception path), call `roleforge.job_runs.log_job_finish(conn, run_id, status, summary)`.
- **job_type:** One of `gmail_poll` | `digest` | `queue` | `replay` | `feed_poll`.

---

## 2. Job types and summary shape

| Job type     | Summary (success) | Summary (failure) |
|-------------|-------------------|-------------------|
| **gmail_poll** | `messages_fetched`, `messages_stored`, optional `messages_skipped` | `error_type`: `transient` \| `permanent`, `message` |
| **digest**   | `profiles`, `messages_sent`, optional `truncated` | `error_type`, `message` |
| **queue**   | `cards_sent`, `profile_id` (if single-profile) | `error_type`, `message` |
| **replay**  | `messages_processed`, `vacancies_created`, `window_start`, `window_end` | `error_type`, `message` |
| **feed_poll** | `feeds_checked`, `entries_processed`, `vacancies_created` | `feed_id`, `message` |

All summaries are JSON-serializable dicts. No secrets in `summary`.

#### Optional: AI cost (TASK-104)

When a job runs AI enrichment (e.g. vacancy summarizer), the summary may include:

- **`ai_cost_usd`** (number): estimated or actual cost in USD for that run (e.g. from provider usage/cost APIs). Used for cost governance and monthly review; see [Cost governance](cost-governance.md).

If present, it is included in structured logs only in sanitized form (no raw tokens or request payloads). Reporting and guardrails are documented in the cost-governance spec.

---

## 3. Visibility

- Query `job_runs` by `job_type`, `started_at DESC` to see last runs.
- `status = 'failure'` + `summary.error_type = 'permanent'` → surface for admin (e.g. re-auth).
- No separate DLQ or heavy platform; Postgres is the log.

---

*Ref: TASK-036, EPIC-07; roleforge/job_runs.py; schema job_runs table.*
