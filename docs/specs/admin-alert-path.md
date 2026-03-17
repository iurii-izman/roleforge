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
  - Logs the send to `telegram_deliveries` with `delivery_type = 'admin_alert'`.
- If no admin chat_id is configured, the hook is a no-op; auth failures still appear only in `job_runs`.

---

## 3. Rule (acceptance)

- [x] **Critical auth or runtime failures create an admin signal:** Today = row in `job_runs` with clear `error_type`. Optional = one Telegram message to admin when `notify_admin` is called and config present.
- Implementation: call `notify_admin(conn, run_id, summary.get("message", ""))` from the job runner when it sets `status = 'failure'` and `summary.error_type = 'permanent'`. No heavy alerting platform in MVP.

---

## 4. Consecutive-failure admin alert (TASK-103)

- **Trigger:** When a job type has **exactly 3** consecutive failures (counting from the most recent run backwards), one Telegram message is sent to the admin chat. One or two failures do not trigger; four or more in a row do not send a second alert (only when the streak first hits 3).
- **Config:** `TELEGRAM_ADMIN_CHAT_ID` (env or .env). If unset, no Telegram alert is sent; failures still appear in `job_runs`. Same bot as digest/queue: `TELEGRAM_BOT_TOKEN`.
- **Implementation:** `roleforge.admin_alert.check_and_alert_consecutive_failures(conn, job_type, run_id, summary)`. Called from `log_job_finish` when `status == 'failure'`. Alerts are logged to `telegram_deliveries` with `delivery_type = 'admin_alert'`.
- **Deduplication:** Alert is sent only when the consecutive failure count equals 3 (not on 4th, 5th, …). After a successful run, the streak resets; the next time the same job type fails 3 times in a row, one alert is sent again.

---

*Ref: TASK-039, TASK-103, EPIC-08, EPIC-20; retry-and-fallback-policy.md, job-runs-logging.md.*
