# Architecture Notes

## Current Direction

- Intake source for MVP: Gmail only
- Ingestion path for MVP: Gmail API polling, scoped by dedicated mailbox label rules
- System of record: Postgres
- Delivery path: Telegram digest plus pull-based review queue
- AI usage in MVP: one primary provider, narrow usage for concise summary and selective relevance help (the chosen provider is captured in TASK-010 and exposed via `PRIMARY_AI_PROVIDER` and a single API key env/secret)
- Local secret handling: keyring-first; keyring name **roleforge**, namespace `service=roleforge` (see [Bootstrap: Access and Secrets](bootstrap-access.md))
- Backlog canon: Linear project `RoleForge MVP`
- GitHub Projects role: execution mirror only

## Technical Principles

- Start with one reliable source and one reliable state store
- Prefer deterministic workflow logic over generic agent orchestration
- Use AI only where the ROI is explicit
- Keep secrets out of git and prefer local keyring for bootstrap
- Keep the data model replayable and audit-friendly

## MVP Architecture Shape

1. Gmail polling job fetches new message IDs from a dedicated intake label (see [Gmail intake spec](specs/gmail-intake-spec.md)).
2. Message bodies and metadata are stored in Postgres (see `schema/001_initial_mvp.sql` and [State transitions](specs/state-transitions.md)).
3. Deterministic parsing extracts vacancy candidates.
4. Normalization and dedup produce canonical vacancies.
5. Each vacancy is matched against multiple profiles through one shared scoring model.
6. Telegram receives compact digests and queue-entry actions.
7. Review actions and run logs are persisted in Postgres.
8. **Observability:** JSON structured logs to stdout from job start/finish ([Structured logging](specs/structured-logging.md)); consecutive-failure admin alert to Telegram when a job type has 3 consecutive failures ([Admin alert path](specs/admin-alert-path.md)).

## Deployment and Runtime (EPIC-09)

- Hosted runtime: one provider and hosting model, chosen and approved in TASK-040 (kept provider-neutral here; see that task in Linear for concrete choice and budget envelope).
- Environment contract:
  - Local development prefers keyring-first secrets under `service=roleforge` with a thin `.env` bootstrap layer.
  - Hosted runtime uses environment variables only, injected from the provider’s secret store; variable names mirror the local `.env.example` and keyring domains.
  - The canonical list of runtime variables, including Gmail polling cadence, Telegram chat IDs, `DATABASE_URL`, and `PRIMARY_AI_PROVIDER`, is defined in [Deployment and Runtime Contract](specs/deployment-runtime.md).
- Secret mapping:
  - Keyring domains (`google`, `telegram`, `openai`, `anthropic`, `db`, `linear`, `app`) map 1:1 to hosted env vars such as `GMAIL_CLIENT_ID`, `TELEGRAM_BOT_TOKEN`, `OPENAI_API_KEY`, `DATABASE_URL`, `LINEAR_API_KEY`.
  - No additional secret-mapping infrastructure is introduced in MVP; the hosting provider’s native secret store plus env injection is sufficient.
- Postgres runtime minimum:
  - Single primary Postgres instance (version ≥ 13, recommended ≥ 15) with one `roleforge` database, UTC timezone and UTF8 encoding.
  - Automatic daily backups with at least 7 days of retention (14 preferred); PITR enabled if available.
  - No replicas or heavy infra platforms in MVP; advanced HA/observability are explicitly deferred.

## Scheduler (EPIC-16, TASK-068–070)

- **Chosen approach:** a small in-process scheduler in `roleforge/scheduler.py` using the standard library. APScheduler, the `schedule` package, and a Postgres cron table were evaluated but are heavier than the MVP needs.
- **Contract:** the scheduler coordinates approved job entrypoints; it does not replace Postgres or introduce a queue. Each scheduled job still owns its own `job_runs` logging.
- **Default cadence:** Gmail polling every 15 minutes, feeds every 60 minutes, alert every 5 minutes, batch every 15 minutes, and digest daily at `DIGEST_AT_UTC` (default `09:00` UTC). Queue remains on-demand.
- **Failure behavior:** one job failure must not stop the loop or block other jobs. Underlying jobs keep their own retry/fallback policies; scheduler state is in-memory only.

## v3.1 Feed intake (EPIC-11)

- **Feed registry:** File-driven; `config/feeds.yaml` (id, name, url, type, enabled). No DB table for registry.
- **Kill-switch:** Env `FEED_INTAKE_ENABLED` (default false); per-feed `enabled` in YAML.
- **Intake path:** Same normalized vacancy schema and dedup path as Gmail; `vacancy_observations` supports either `gmail_message_id` or `feed_source_key` (schema 002).
- **Job:** `feed_poll`; logs to `job_runs`; no new infra.

## v3.2 Connector contract (EPIC-12, TASK-048–049)

- **Contract:** Minimal connector contract in [v3 feeds and connectors](specs/v3-feeds-and-connectors.md). Connectors emit same candidate shape as Gmail/feeds; source key in `vacancy_observations.feed_source_key` with prefix `connector:{connector_id}:{id}` (no new tables).
- **Enable/disable:** Env `CONNECTOR_INTAKE_ENABLED` (default false); per-connector `enabled` in future registry file.
- **First candidates:** Greenhouse (preferred), Lever; implementation only after MVP metrics and product go-ahead.
- **Rollout:** Doc-only for now; registry and first adapter when unblocked.

## AI governance (v4+, TASK-067)

Rules for all AI use in the pipeline (enrichment, future inbox classification, etc.):

- **Provider and model:** One primary provider per deployment (`PRIMARY_AI_PROVIDER`). Model must be pinned to an explicit version (e.g. `gpt-4o-mini`, `claude-3-5-haiku-20241022`); never use "latest" in production. See [AI enrichment contract](specs/ai-enrichment-contract.md).
- **Prompt versioning:** Prompts are versioned in code (`roleforge/prompts/`). Each prompt has a `PROMPT_VERSION`; when the prompt changes, the version changes. Stored AI output includes `prompt_version` (and optional `prompt_hash`) for audit and re-enrichment.
- **Output tracking:** AI-generated content is stored in bounded fields (e.g. `vacancies.ai_metadata`). Shape and semantics are defined in the relevant spec; no open-ended payloads.
- **Failure behavior:** AI calls must not block the deterministic pipeline. On transient failure: retry with bounded backoff; then skip and continue. On permanent failure: skip and log. Delivery and scoring proceed without AI output when enrichment fails.
- **Cost:** Every job that calls the AI must set `ai_cost_usd` in `job_runs.summary`. Monthly review uses the query in [Cost governance](specs/cost-governance.md). Per-run caps (e.g. max enrichments per run) limit cost exposure.
- **Privacy and logging:** Do not send operator PII to the AI. Do not log full prompts or full model responses; log only counts, cost, and high-level metadata (model, prompt_version).

## Market monitoring (v6, TASK-091)

HH.ru is the first active market-monitoring source. The implementation keeps the same normalized vacancy pipeline and adds only a file-driven registry plus a sweep job.

- **Source choice:** Use the official HH.ru public vacancy search API for personal monitoring. The official developer agreement allows application registration and is explicit that API data is for the developer's own hiring-related use, not commercial redistribution or third-party sharing.
- **Registry and kill-switch:** `config/monitors.yaml` plus `MONITOR_INTAKE_ENABLED` keep the monitor path reversible without changing Gmail or feed intake.
- **Adapter and source keys:** `roleforge.monitors.hh` maps HH.ru vacancy payloads to the shared candidate shape; source keys use `monitor:hh:{vacancy_id}` in `vacancy_observations.feed_source_key`.
- **Operational policy:** Identify the app with a clear User-Agent, use conservative paging/backoff, and do not HTML-scrape job boards. The public docs expose `alternate_url` and structured `salary` fields; optional salary-aware filtering stays deferred until product value is explicit.
- **Job logging:** `roleforge.jobs.monitor_poll` records a `job_runs` summary with per-monitor results so source health remains auditable.

## v5 application lifecycle (EPIC-17, TASK-071)

- **Lifecycle shape:** `applied` → `hr_pinged` → `interview_scheduled` → `offer` → `accepted` / `declined`, with `rejected` and `ghosted` as terminal exits.
- **State authority:** State changes stay operator-confirmed. Telegram is the control surface; Gmail thread matching and later classifier work only assist with detection.
- **Schema shape:** Additive tables in the same Postgres instance: `applications`, `employer_threads`, and `interview_events`.
- **Migration file:** `schema/004_application_lifecycle.sql` (the v5 migration follows `003_ai_metadata.sql`).
- **Deferred scope:** No separate application service, no calendar sync, and no AI-driven state transitions in this slice.
- **Message classification:** `gmail_messages.classified_as` (migration 005) stores deterministic inbox classification; rules and replay semantics in [Inbox classifier](specs/inbox-classifier.md) (TASK-073); implementation in `roleforge.inbox_classifier` (TASK-075). [AI inbox classification contract](specs/ai-inbox-classification-contract.md) (TASK-074) defines when and how to call AI for ambiguous messages.

## Explicitly Deferred

- IMAP
- Outlook / Graph
- Official ATS connector implementation (until v3.2 unblocked)
- Notion or any second hub
- n8n
- Instant alerts by default
- Dual-provider hot path
- Adaptive scoring loops

## Decision Log

| Date | Decision | Status | Notes |
| --- | --- | --- | --- |
| 2026-03-15 | Create repository baseline for AI-first development | Accepted | Initial docs and workflow files added |
| 2026-03-15 | Scope MVP to Gmail-only intake | Accepted | Avoid connector sprawl and premature universality |
| 2026-03-15 | Use Postgres as the only source of truth in MVP | Accepted | No secondary hub in MVP |
| 2026-03-15 | Use Telegram digest plus review queue for MVP delivery | Accepted | Low-noise review path |
| 2026-03-15 | Keep Linear canonical and GitHub Projects mirrored | Accepted | Backlog management decision |
| 2026-03-15 | Use keyring-first local secret storage under service=roleforge | Accepted | Bootstrap path before hosted secrets |
| 2026-03-15 | Lock canonical backlog structure and define ticket/hygiene rules | Accepted | TASK-001–003: JSON meta lock, AI ticket template, sync policy in docs/backlog |
| 2026-03-15 | Minimal Postgres MVP schema and state transitions | Accepted | TASK-032, TASK-033: schema in schema/, state spec in docs/specs/state-transitions.md |
| 2026-03-15 | Linear placement: API-driven | Accepted | TASK-006: max autopilot; create/update issues via Linear GraphQL API, not manual import |
| 2026-03-15 | Gmail message persistence and retry policy | Accepted | TASK-013: gmail_reader/store.py + persist_messages; TASK-014: docs/specs/gmail-retry-policy.md, retry.py, job_runs.py |
| 2026-03-15 | Parser behavior, extraction pipeline, vacancy schema | Accepted | TASK-016: docs/specs/parser-behavior.md; TASK-017: roleforge/parser/ + tests; TASK-018: docs/specs/vacancy-schema.md, parser/schema.py |
| 2026-03-15 | Normalization, dedup, idempotency and replay | Accepted | TASK-019: roleforge/normalize.py; TASK-020: roleforge/dedup.py; TASK-034: docs/specs/idempotency-and-replay.md |
| 2026-03-15 | Profile schema, scoring spec, shared scoring engine | Accepted | TASK-022–024: profile-schema, scoring-spec, roleforge/scoring.py |
| 2026-03-15 | Explainability, review ordering, Telegram spec, digest formatter | Accepted | TASK-025: scoring explainability + roleforge/review_ordering.py; TASK-027: docs/specs/telegram-interaction.md; TASK-028: roleforge/digest.py |
| 2026-03-15 | Queue cards, job_runs contract, retry policy (Gmail/Telegram/AI) | Accepted | TASK-029: roleforge/queue.py; TASK-036: docs/specs/job-runs-logging.md; TASK-037: docs/specs/retry-and-fallback-policy.md, roleforge/retry.py |
| 2026-03-16 | Telegram delivery log, replay entrypoints, admin alert path | Accepted | TASK-030: roleforge/delivery_log.py; TASK-038: roleforge/replay.py; TASK-039: docs/specs/admin-alert-path.md |
| 2026-03-16 | v3.2 connector contract and first candidates (TASK-048, TASK-049) | Accepted | docs/specs/v3-feeds-and-connectors.md: minimal contract, feed_source_key convention, enable/disable, Greenhouse/Lever candidates, risks and rollout; no new code |
| 2026-03-17 | Scoring dimensions are placeholders; EPIC-13 required before delivery intelligence | Accepted | title_match/company_match return 0.5-if-present; keyword_bonus always 0; all vacancies score ~0.52; threshold-triggered alerts are meaningless until real keyword matching is implemented; see docs/research-v4-plus.md §1.3 |
| 2026-03-17 | v4 delivery mode: threshold-triggered alerts default-off per profile | Accepted | profiles.config extended with delivery_mode (alert_enabled, immediate_threshold, batch_enabled, batch_threshold, batch_interval_minutes); both flags default false to preserve digest-only behavior; see docs/research-v4-plus.md §4.1 |
| 2026-03-17 | AI enrichment post-scoring only, never in scoring path | Accepted | AI may generate vacancy summary and inbox classification; scoring dimensions remain deterministic keyword rules; AI output stored in vacancies.ai_metadata JSONB; prompt version + model pinned; see docs/research-v4-plus.md §6.5 |
| 2026-03-18 | v5 application lifecycle: minimal state machine and additive schema | Accepted | `applied` → `hr_pinged` → `interview_scheduled` → `offer` → `accepted` / `declined`, with `rejected` and `ghosted` as terminal exits; additive tables in `schema/004_application_lifecycle.sql`; see `docs/specs/v5-application-lifecycle.md` |
| 2026-03-17 | v6 market monitoring: HH.ru API first, monitor registry in config/monitors.yaml | Accepted | Official public API (no auth), same candidate shape via monitor:hh:{id} source key; MONITOR_INTAKE_ENABLED kill-switch; no HTML scraping ever; see docs/research-v4-plus.md §4.3 |
| 2026-03-17 | v7 web UI: FastAPI + Jinja2 + HTMX, Bearer token auth, no build system | Accepted | Single Python process; Telegram stays as primary delivery channel; web UI handles configuration, analytics, bulk queue, application workspace; see docs/research-v4-plus.md §4.4 |
| 2026-03-17 | Source key convention extended to monitors: monitor:{type}:{ext_id} in vacancy_observations.feed_source_key | Accepted | No schema change needed; consistent with connector:{id}:{ext_id} convention; feed_source_key is already the generic non-Gmail source field |
| 2026-03-18 | AI enrichment contract (TASK-062): provider/model shortlist, input/output, gating, timeout/retry/fallback, cost and prompt versioning | Accepted | docs/specs/ai-enrichment-contract.md; clear path to TASK-061, TASK-063–TASK-066; no runtime AI in this session |
| 2026-03-18 | AI governance rules documented in architecture (TASK-067) | Accepted | New section "AI governance (v4+)" in docs/architecture.md; model pinning, prompt versioning, failure behavior, cost, privacy |
| 2026-03-18 | Scheduler decision (TASK-068): custom in-process standard-library loop, daily digest at 09:00 UTC, queue remains on-demand | Accepted | docs/specs/scheduler.md; `roleforge/scheduler.py`; no APScheduler, no `schedule` dependency, no Postgres cron table |
| 2026-03-18 | HH.ru market monitoring block (TASK-084–TASK-092): public API first, registry + adapter + monitor_poll, kill-switch, legal envelope documented | Accepted | docs/specs/v6-market-monitoring.md; `config/monitors.yaml`; `roleforge/monitor_registry.py`; `roleforge/monitors/hh.py`; `roleforge/jobs/monitor_poll.py`; optional salary modeling remains deferred |
