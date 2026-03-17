# JSON Structured Logging (TASK-102)

**Scope:** Core jobs emit one JSON object per log line to stdout so logs are machine-readable without adding external log systems.

---

## 1. Contract

- **Output:** stdout only; one JSON object per line (newline-delimited).
- **Trigger:** Every `log_job_start` and `log_job_finish` call emits a structured line; no per-job code changes required.
- **No new dependencies:** Uses only the standard library (`json`, `sys`).

---

## 2. Log shape

Each line is a single JSON object with at least:

| Field     | Type   | Description |
|----------|--------|-------------|
| `ts`     | string | ISO 8601 UTC timestamp |
| `level`  | string | `info` \| `warning` \| `error` |
| `event`  | string | `job_start` \| `job_finish` |
| `message`| string | Short human-readable message |
| `job_type` | string | When applicable: `gmail_poll`, `digest`, `queue`, `replay`, `feed_poll` |
| `run_id` | string | When applicable: job run UUID |
| `status` | string | For `job_finish`: `success` \| `failure` |
| `summary` | object | For `job_finish`: sanitized summary (no secrets, no long previews) |

Summary is sanitized: keys like `telegram_response`, `preview`, `text_preview` are omitted; any key suggesting a secret (e.g. token, password) is omitted.

---

## 3. Implementation

- **Module:** `roleforge.structured_log`. Helpers: `log_struct`, `log_job_start_structured`, `log_job_finish_structured`.
- **Integration:** `roleforge.job_runs.log_job_start` and `log_job_finish` call the structured logger after DB writes so all jobs using job_runs get structured logs.

---

## 4. Local readability

Logs remain readable locally: each line is valid JSON; `ts`, `event`, `job_type`, and `message` give quick context. Optional: pipe to `jq` for pretty-print.

---

*Ref: TASK-102, EPIC-20; job-runs-logging.md.*
