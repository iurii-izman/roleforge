# Retry and Fallback Policy: Gmail, Telegram, AI (TASK-037)

**Scope:** Bounded retries and clear failure behavior for the three external systems in MVP. No heavy DLQ platform.

---

## 1. Principles

- **Transient:** Retry with exponential backoff (e.g. max 3 attempts, base 1s). Then log run as failure and surface.
- **Permanent:** Do not retry; fail fast; log with `error_type: 'permanent'` so admin can fix (e.g. re-auth).
- **No DLQ:** We do not introduce a dead-letter queue or external retry platform in MVP. Log to `job_runs.summary` and optionally alert later (TASK-039).

---

## 2. Gmail

- **Implemented:** `roleforge.gmail_reader.retry`: `is_transient_error`, `is_permanent_auth_error`, `with_retry`.
- **Transient:** 429, 5xx, connection/timeout errors → retry.
- **Permanent:** 401, 403, invalid_grant, token revoked → no retry.
- **Detail:** [Gmail retry policy](gmail-retry-policy.md).

---

## 3. Telegram (Bot API)

- **Transient:** 5xx, 429 (rate limit), network/timeout. Retry with same backoff as Gmail.
- **Permanent:** 401 (wrong token), 400 (bad request), 403 (bot blocked). No retry.
- **Hook:** Use a generic retry helper with Telegram-specific classifiers (e.g. `roleforge.retry.with_retry(..., is_transient=is_transient_telegram, is_permanent=is_permanent_telegram)`). On permanent failure: log to job_runs; do not crash the process if it is a digest send (log and skip that send).

---

## 4. AI provider (OpenAI / Anthropic / etc.)

- **Transient:** 429 (rate limit), 503, timeout. Retry with backoff.
- **Permanent:** 401, 403 (invalid key), 400 (invalid request). No retry.
- **Hook:** Same generic retry + AI-specific classifiers. On permanent failure: log and surface; digest/queue can degrade (e.g. skip AI summary for that run).

---

## 5. Summary (acceptance)

- [x] **Transient retries exist** for Gmail (code), Telegram and AI (policy + generic helper).
- [x] **Permanent failures surface clearly** via job_runs and optional summary fields.
- [x] **No heavy DLQ** — Postgres and run logging only.

---

*Ref: TASK-037; roleforge.gmail_reader.retry (Gmail); roleforge.retry (generic + Telegram/AI hooks).*
