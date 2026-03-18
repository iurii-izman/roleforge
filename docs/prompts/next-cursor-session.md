# RoleForge Next Session Prompt

## Read First

- docs/prompts/cursor-autopilot-roleforge.md
- AGENTS.md
- README.md
- docs/architecture.md
- docs/product-brief.md
- docs/roadmap.md
- docs/backlog/roleforge-backlog.json
- docs/backlog/README.md
- docs/bootstrap-access.md
- docs/specs/v5-application-lifecycle.md
- docs/specs/inbox-classifier.md
- docs/specs/ai-inbox-classification-contract.md
- schema/004_application_lifecycle.sql
- schema/005_gmail_classified.sql
- docs/manual-tasks.md
- roleforge/application_lifecycle.py (and tests/test_application_lifecycle.py)
- any files changed in the previous session that are directly relevant

## Current State

- EPIC-17 is Done in Linear and GitHub (repo-confirmed).
- TASK-071 through TASK-083 are Done in the repo.
- EPIC-18 is resolved by product decision: keep `salary_raw` only; no `salary_structured` in the current roadmap.
- TASK-093 is Done as a scope decision in `docs/specs/v7-web-ui.md`.
- v5 lifecycle spec and schema 004/005 in place; inbox classifier + job; employer thread matching; application state transitions via `roleforge.application_lifecycle` (apply_application_transition, is_allowed_transition).
- Interview event extraction exists as a deterministic job: `python -m roleforge.jobs.interview_event_extract` (writes to `interview_events`).
- Application update notifications exist as an optional job: `python -m roleforge.jobs.application_notify` (disabled by default).
- Interview AI enrichment exists as an optional job: `python -m roleforge.jobs.interview_event_ai_enrich` (disabled by default).
- EPIC-19 web foundation exists: `roleforge/web/` (FastAPI+Jinja2+HTMX) with Bearer auth, and pages `/analytics`, `/system-health`, `/sources`.
- Web queue browser exists: `/queue-browser` (bulk actions via existing `queue.apply_review_action`).
- Web profile editor exists: `/profiles` + `/profiles/{id}` with guardrails and audit via `job_runs` (job_type `web_profile_edit`).
- `python -m pytest tests/ -q` passed with 241 tests.

## Done In This Session

- **TASK-096 / TASK-099 / TASK-101:** web-first operator console value:
  - `/analytics`: query-backed analytics (score bands, per-profile counts, sources, funnel, recent runs)
  - `/system-health`: query-backed job_runs panel (last 5 per job type)
  - `/sources`: feeds/monitors registry view + HTMX enable/disable toggles (edits YAML)
  - tests added; Linear updated first; GitHub mirror issues closed.
- **TASK-097:** queue browser:
  - `/queue-browser`: table view over `profile_matches` + bulk actions via existing `roleforge.queue.apply_review_action` (auditable through `review_actions`)
- **TASK-098:** profile editor:
  - `/profiles`: list
  - `/profiles/{id}`: view/edit `profiles.config` JSON with allowlist validation; audit via `job_runs` entry `web_profile_edit`

## Next Best Block

- **EPIC-19 next (later wave):**
  - `TASK-100` application workspace timeline view (browse applications/employer_threads/interview_events)
  - EPIC-19 remains In Progress until application workspace is delivered (do not close yet)

## User Prep

- none.

## First Actions

1. Read `docs/specs/v7-web-ui.md` and keep constraints strict: single-user, Bearer token auth, FastAPI + Jinja2 + HTMX, no SPA, Telegram remains primary.
2. Implement `TASK-100` as read-only timeline views first; keep it small and auditable (no new state machine logic).
3. Run `python -m pytest tests/ -q`; update Linear first, GitHub mirror second; regenerate next prompts.

## Constraints

- Gmail-only MVP
- Postgres-first
- Telegram digest + review queue
- one primary AI provider in MVP
- keyring-first secrets under service=roleforge
- AI only post-scoring
- Do not reopen salary modeling unless a new explicit product decision changes the scope

## If Blocked

- If extraction scope is unclear, implement a minimal deterministic path first (e.g. date/link regex) and defer AI to a follow-up task.

## On Completion

- Update Linear first.
- Update GitHub mirror second.
- Leave close-out comments.
- Generate a new next-session prompt from the actual outcome.
