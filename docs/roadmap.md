# Roadmap

## MVP

- Seed canonical backlog in Linear and mirrored backlog in GitHub Projects
- Complete access and bootstrap for Gmail, Telegram, and one AI provider
- Implement Gmail-only polling intake
- Implement deterministic parsing, normalization, and dedup
- Implement Postgres-first match, score, and review state model
- Implement Telegram digest plus review queue
- Add minimal retries, replay, and runtime docs

## v2

- Richer multiple-profile behavior (see docs/specs/v2-profiles-and-queue.md)
- Better summaries and score calibration
- Better queue ergonomics (see docs/specs/v2-profiles-and-queue.md)
- Basic analytics and reporting (see docs/specs/v2-profiles-and-queue.md)
- Optional exceptional alert path if the digest-only model proves too slow

## v3.1

- Add RSS and structured feeds through the same normalized schema (see docs/specs/v3-feeds-and-connectors.md)
- Add source registry and kill-switch controls (see docs/specs/v3-feeds-and-connectors.md)

## v3.2

- Add official source connectors only after Gmail MVP is stable (see docs/specs/v3-feeds-and-connectors.md)
- Use legal clarity, structured value, and maintenance cost as gating criteria (see docs/specs/v3-feeds-and-connectors.md)

## v4 — Real scoring and delivery intelligence

**Prerequisite: EPIC-13 (scoring engine fix) must complete before any delivery work.**

- Fix scoring engine: real keyword-based `title_match`, `company_match`, `keyword_bonus` dimensions
- Add `keywords` and `skills` fields to `profiles.config`
- Add `delivery_mode` to `profiles.config` (alert threshold, batch threshold, batch interval)
- Implement threshold-triggered Telegram alert path (`roleforge/jobs/alert.py`; default off per profile)
- Optional: micro-batch delivery job (flush mid-band matches every N minutes)
- AI enrichment: vacancy summarizer for high-score items, stored in `vacancies.ai_metadata`
- Add JSON structured logging to stdout
- Add in-process scheduler (stdlib loop) as optional cron replacement
- See [research-v4-plus.md](research-v4-plus.md) §4.1 for full version research

**Gating criteria for v4 delivery features:** scoring must produce meaningfully differentiated
score bands (high-score ≥ 0.75 vacancies must be qualitatively better matches than low-score
< 0.5 ones) before alerting is enabled.

## v5 — Application lifecycle

**Depends on:** v4 complete (real scoring makes "applied" actions meaningful)

- Define application schema: `applications`, `employer_threads`, `interview_events` tables
- Inbox classifier job: detect employer replies vs new vacancy emails (thread + domain + subject signals)
- Application state machine: applied → hr_pinged → interview_scheduled → offer/rejected/ghosted
- AI classification for ambiguous employer replies; AI extraction of interview date and meeting link
- Telegram notifications for application status changes
- AI company briefer and prep checklist for interview events
- Lightweight interview reminder via Telegram (no Google Calendar sync in v5.0)
- See [research-v4-plus.md](research-v4-plus.md) §4.2 for full version research

## v6 — Active market monitoring

**Depends on:** v4 real scoring (monitor results need score differentiation to filter noise)

- Monitor registry: `config/monitors.yaml` (id, type, params, poll_interval_minutes, enabled)
- `MONITOR_INTAKE_ENABLED` global kill-switch
- HH.ru API adapter: `roleforge/monitors/hh.py`, emits standard candidate shape
- `monitor_poll` job: reads registry, runs enabled monitors, logs to `job_runs`
- Optional structured salary modeling: add `vacancies.salary_structured JSONB` only if salary-aware filtering becomes worth the extra schema
- Salary range filtering in hard_filters stays deferred until salary modeling is explicitly approved
- ToS review and rate-limit policy documented before implementation
- See [research-v4-plus.md](research-v4-plus.md) §4.3 for full version research

## v7 — Unified operator console

**Depends on:** v4 scoring (analytics), v5 applications (workspace); can start v7.0 after v4

- FastAPI + Jinja2 + HTMX web application (`roleforge/web/`)
- Bearer token auth (single operator, no OAuth)
- Analytics dashboard: match trends, score distribution, state funnel, source health
- Queue browser: full sortable table, multi-select bulk actions
- Profile editor: view/edit `profiles.config` (keywords, filters, delivery mode)
- System health panel: `job_runs` log, last-N per job type, status indicators
- Application tracking workspace (requires v5 schema)
- Source management: enable/disable feeds and monitors
- See [research-v4-plus.md](research-v4-plus.md) §4.4 for full version research
