# Minimal Admin Alert Path (TASK-039)

**Scope:** One minimal path for operational failures so an admin can notice without polling logs.

---

## 1. When to signal

- **Permanent auth failure:** Gmail, Telegram, or AI provider returns 401/403 or invalid token; retry layer has already logged the run with `job_runs.status = 'failure'` and `summary.error_type = 'permanent'`.
- **Critical runtime failure:** Optional: repeated replay/poll failures, or a single run that the job runner marks as critical (e.g. configurable).

MVP: treat **permanent auth** as the primary trigger. Other failures remain in `job_runs` for inspection.

---

## 2. Signal (MVP)

- **Primary:** `job_runs` row with `status = 'failure'` and `summary.error_type = 'permanent'`. No extra table; operators (or a future dashboard/cron) query for recent failures.
- **Optional hook:** A single function `notify_admin(conn, run_id, message)` that:
  - Reads admin delivery config (e.g. Telegram chat_id from keyring or env).
  - Sends one message to that chat (e.g. "RoleForge: permanent failure, run_id=..., message=...").
  - Logs the send to `telegram_deliveries` with `delivery_type = 'admin_alert'` (schema may add this value) or reuses a generic type.
- If no admin chat_id is configured, the hook is a no-op; auth failures still appear only in `job_runs`.

---

## 3. Rule (acceptance)

- [x] **Critical auth or runtime failures create an admin signal:** Today = row in `job_runs` with clear `error_type`. Optional = one Telegram message to admin when `notify_admin` is called and config present.
- Implementation: call `notify_admin(conn, run_id, summary.get("message", ""))` from the job runner when it sets `status = 'failure'` and `summary.error_type = 'permanent'`. No heavy alerting platform in MVP.

---

*Ref: TASK-039, EPIC-08; retry-and-fallback-policy.md, job-runs-logging.md.*
