# Deployment and Runtime Contract (MVP)

Status: Draft for TASK-041–TASK-043 (EPIC-09)

This spec defines the minimum deployment contract for the Gmail-only, Postgres-first MVP. It is deliberately conservative: one hosted runtime, one Postgres instance, and secrets injected via the hosting provider’s secret store as environment variables that mirror the local keyring layout.

## 1. Runtime shape

- **Process model**: a single containerized app image (or equivalent) that can run:
  - a scheduled Gmail polling job,
  - a scheduled digest job,
  - optional alert and batch delivery jobs,
  - an optional in-process scheduler,
  - optional admin / health endpoints and Telegram webhook handler if webhook mode is chosen.
- **Entry points** (suggested; exact commands live next to code, not here):
  - `python -m roleforge.scheduler` – optional in-process coordinator for Gmail/feed/alert/batch/digest cadences.
  - `python -m roleforge.jobs.gmail_poll` – Gmail polling (messages.list/messages.get → Postgres via `gmail_reader` + `gmail_reader.store`).
  - `python -m roleforge.jobs.digest` – build and send Telegram digests.
  - `python -m roleforge.jobs.queue` – Telegram review queue on-demand entrypoint.
  - `python -m roleforge.jobs.alert` – threshold-triggered Telegram alert path.
  - `python -m roleforge.jobs.batch` – micro-batch delivery path.
  - `python -m roleforge.jobs.monitor_poll` – HH.ru market monitoring sweep.
  - `python -m roleforge.jobs.replay` – manual replay helpers.
  - `python -m roleforge.jobs.inbox_classify` – classify stored Gmail messages (set `gmail_messages.classified_as`); uses intake label from config (see below).
  - `python -m roleforge.jobs.employer_thread_match` – create/update `employer_threads` by linking employer replies to applications via Gmail thread ID.
  - `python -m roleforge.jobs.interview_event_extract` – extract interview signals (meeting links, best-effort datetime) from employer replies into `interview_events`.
  - `python -m roleforge.jobs.application_notify` – send low-noise Telegram updates for application lifecycle signals (disabled by default; see env below).
  - `python -m roleforge.jobs.interview_event_ai_enrich` – AI enrich interview events (company brief + prep checklist) into `interview_events.notes` (disabled by default; see env below).
- **Scheduling**: done either by the hosting platform/external scheduler or by the optional in-process `roleforge.scheduler` loop. RoleForge itself is stateless between runs and assumes Postgres as the source of truth.

## 2. Environment contract

The runtime reads configuration from environment variables. Local development may additionally use the `roleforge` keyring; hosted runtimes must rely on environment variables only, injected from the provider’s secret store.

### 2.1 Core application

- `APP_ENV` — `development` \| `staging` \| `production`; defaults to `development`.
- `APP_PORT` — port for any HTTP endpoints (health, Telegram webhook).
- `LOG_LEVEL` — optional; `INFO` by default.
- `WEB_BEARER_TOKEN` — optional for local dev; required for hosted web UI. Used by `roleforge.web` Bearer auth middleware.

### 2.2 Postgres (system of record)

- `DATABASE_URL` — required in hosted runtime; e.g. `postgresql://user:pass@host:5432/roleforge`.
- Optional: `DATABASE_POOL_SIZE`, `DATABASE_POOL_MAX_OVERFLOW` if a pooling layer is introduced later.

### 2.3 Gmail intake

- `GMAIL_CLIENT_ID` — OAuth client id.
- `GMAIL_CLIENT_SECRET` — OAuth client secret.
- `GMAIL_REFRESH_TOKEN` — long-lived refresh token for the intake account.
- `GMAIL_INTAKE_LABEL` — label name or ID used for intake (see `gmail-intake-spec.md`). Also used by the inbox classification job when `GMAIL_INTAKE_LABEL_IDS` is not set.
- `GMAIL_INTAKE_LABEL_IDS` — optional; comma-separated Gmail label IDs for inbox classification (Rule 2: intake label + single-message thread → vacancy_alert). If not set, the inbox_classify job uses `GMAIL_INTAKE_LABEL` (resolved via Gmail API when credentials exist, else the value as single ID).
- `GMAIL_POLL_INTERVAL_MINUTES` — polling cadence for the scheduler; default 15.
- `FEED_POLL_INTERVAL_MINUTES` — polling cadence for feed intake; default 60.
- `ALERT_POLL_INTERVAL_MINUTES` — polling cadence for threshold alerts; default 5.
- `BATCH_POLL_INTERVAL_MINUTES` — polling cadence for batch delivery; default 15.
- `DIGEST_AT_UTC` — daily digest run time in `HH:MM` UTC; default `09:00`.
- `MONITOR_INTAKE_ENABLED` — global kill-switch for HH.ru market monitoring; default false.

### 2.4 Telegram

- `TELEGRAM_BOT_TOKEN` — bot token.
- `TELEGRAM_CHAT_ID` — primary chat/channel for digests.
- `TELEGRAM_APPLICATION_CHAT_ID` — optional; override chat for application updates (defaults to `TELEGRAM_CHAT_ID`).
- `TELEGRAM_ADMIN_CHAT_ID` — chat/user for admin alerts (may equal `TELEGRAM_CHAT_ID` in MVP).
- Optional webhook-related variables (only if webhook mode is used per Telegram spec):
  - `TELEGRAM_WEBHOOK_URL` — full HTTPS URL for the bot webhook.
  - `TELEGRAM_WEBHOOK_SECRET` — shared secret token, if the hosting platform supports it.

### 2.4.1 Application update notifications (v5)

- `APPLICATION_NOTIFY_ENABLED` — `true`/`false`; default false (digest-first, low-noise). When true, `python -m roleforge.jobs.application_notify` can send application update messages (employer thread linked, interview event created).

### 2.6.1 Interview AI enrichment (v5, optional)

- `INTERVIEW_AI_ENRICH_ENABLED` — `true`/`false`; default false. When true, `python -m roleforge.jobs.interview_event_ai_enrich` writes `ai_briefing` and `prep_checklist` artifacts to `interview_events.notes`.
- `INTERVIEW_AI_MODEL` — optional pinned model override (defaults to provider’s default pinned model).
- `INTERVIEW_AI_MAX_PER_RUN` — optional int cap per run (default 10).
- `INTERVIEW_AI_REENRICH` — `true`/`false`; default false. If true, overwrites existing `ai_briefing` / `prep_checklist` artifacts.

### 2.5 AI provider (single in MVP)

- `PRIMARY_AI_PROVIDER` — `openai` \| `anthropic`; must match the MVP choice recorded in backlog (TASK-010).
- If `PRIMARY_AI_PROVIDER=openai`:
  - `OPENAI_API_KEY`.
- If `PRIMARY_AI_PROVIDER=anthropic`:
  - `ANTHROPIC_API_KEY`.

Only one provider is used on the hot path; any remaining AI keys are optional and unused in MVP.

### 2.6 GitHub / Linear integration (optional in hosted runtime)

Most backlog sync runs from the operator’s machine; hosted runtime normally does not need these variables. If a hosted job syncs status:

- `GITHUB_TOKEN` — GitHub token with `project` scope.
- `LINEAR_API_KEY` — Linear API key (mirrors keyring `linear` / `api_key`).

## 3. Hosted secret mapping (TASK-042)

Local development uses the `roleforge` keyring with domains and keys defined in `docs/bootstrap-access.md`. Hosted runtime uses environment variables with the same logical names. The mapping is one-to-one where possible:

| Keyring (service=roleforge) | Hosted env var | Notes |
| --- | --- | --- |
| `google` / `client_id` | `GMAIL_CLIENT_ID` | |
| `google` / `client_secret` | `GMAIL_CLIENT_SECRET` | |
| `google` / `refresh_token` | `GMAIL_REFRESH_TOKEN` | |
| `telegram` / `bot_token` | `TELEGRAM_BOT_TOKEN` | |
| `openai` / `api_key` | `OPENAI_API_KEY` | Used only if `PRIMARY_AI_PROVIDER=openai`. |
| `anthropic` / `api_key` | `ANTHROPIC_API_KEY` | Used only if `PRIMARY_AI_PROVIDER=anthropic`. |
| `db` / `url` | `DATABASE_URL` | |
| `linear` / `api_key` | `LINEAR_API_KEY` | Only if hosted jobs touch Linear API. |
| `app` / key | App-specific env var | Naming stays 1:1 where possible. |

Principles:

- Local-first: scripts and CLI tools prefer keyring for secrets; `.env` is for bootstrap only.
- Hosted-first: runtime prefers environment variables injected by the hosting provider; no keyring on the server.
- Names are stable: the same logical secret has one canonical name in keyring and one in env; no extra secret-mapping service is introduced in MVP.

## 4. Postgres provisioning and backup minimum (TASK-043)

### 4.1 Version and shape

- **Version**: Postgres ≥ 13; recommended ≥ 15 to match common managed offerings.
- **Topology (MVP)**:
  - Single primary instance.
  - One database: `roleforge`.
  - Time zone: UTC.
  - Encoding: UTF8.
  - No replicas or read-only followers in MVP.

### 4.2 Capacity (starting point)

- Instance class sized for:
  - a few GB of data (gmail_messages + vacancies + audit trails),
  - tens of concurrent connections at most.
- If the hosting provider exposes a “micro”/“dev” class with backups included, that is sufficient for MVP; performance tuning is explicitly deferred.

### 4.3 Backups and recovery

Minimum acceptable baseline:

- Automated daily backups enabled.
- Retention: at least 7 days (14 preferred).
- If the provider supports point-in-time recovery (PITR), enable it; otherwise rely on daily snapshots.
- Clear documented procedure (outside of this repo) for:
  - restoring to a new instance from backup,
  - updating `DATABASE_URL` to point to the restored instance.

No additional backup tooling (logical dump pipelines, external backup services) is introduced in MVP unless the hosting provider offers them “for free”.

## 5. Webhook and job exposure model

- Gmail intake uses polling only (no Gmail webhooks or History API in MVP); no public Gmail endpoint is required.
- Telegram can run either:
  - in **polling mode** (bot long polling; no public endpoint), or
  - in **webhook mode** (single HTTPS endpoint with `TELEGRAM_WEBHOOK_URL` and optional `TELEGRAM_WEBHOOK_SECRET`), consistent with the Telegram interaction spec.
- Admin/health:
  - Optional `/health` endpoint bound to `APP_PORT` for uptime checks; no authentication required in MVP if it only returns a simple status.

The exact hosting provider and concrete URL patterns are defined by the decision captured in TASK-040; this spec keeps the contract provider-neutral.
