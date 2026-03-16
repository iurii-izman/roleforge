# Gmail Read: Retry and Failure Policy (TASK-014)

**Scope:** Gmail API calls used for intake (messages.list, messages.get).  
**Out of scope in this doc:** Telegram, AI provider (see EPIC-08 TASK-037 for unified policy).

---

## 1. Transient vs permanent

| Category | Examples | Action |
|----------|----------|--------|
| **Transient** | 429 (rate limit), 500/502/503, connection timeout, socket errors | Retry with backoff; then log run as failure if exhausted |
| **Permanent** | 401 Unauthorized, 403 Forbidden, invalid_grant (OAuth), 404 (message/label gone) | Do not retry; log run as failure and surface for admin |

Auth failures (invalid token, revoked consent) must be clearly visible so the user can re-run OAuth (TASK-009). No silent retry on auth.

---

## 2. Retry parameters (MVP)

- **Max attempts:** 3 (initial + 2 retries).
- **Backoff:** Exponential: e.g. 2s, 4s (or 1s, 2s for minimal delay).
- **Only for:** Transient errors as above. Permanent errors fail immediately and are logged.

---

## 3. Run logging

Every Gmail poll run should:

1. **Start:** Insert into `job_runs` with `job_type = 'gmail_poll'`, `status = 'running'`, `started_at = now()`.
2. **Finish:** Update the same row: `finished_at = now()`, `status = 'success' | 'failure'`, `summary = { ... }`.

Summary (JSONB) should include at least:

- On success: e.g. `{ "messages_seen": N, "messages_new": M }`.
- On failure: `{ "error_type": "transient" | "permanent", "message": "...", "last_exception": "..." }` (no secrets).

This allows operators to see failed runs and distinguish transient (retry later) from permanent (fix credentials/config).

---

## 4. Admin alerts (future)

Permanent auth failures should eventually trigger an admin notification path (TASK-039). In MVP, logging to `job_runs` with `status = 'failure'` and a clear `summary.error_type = 'permanent'` is sufficient so that a future alert job or dashboard can surface them.

---

*Ref: TASK-014, EPIC-03 Gmail Intake; TASK-037 (unified retry policy).*
