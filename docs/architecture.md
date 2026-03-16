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


## Explicitly Deferred

- IMAP
- Outlook / Graph
- RSS / feeds
- Official ATS APIs
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
