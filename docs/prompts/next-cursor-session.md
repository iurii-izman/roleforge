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
- EPIC-19 is now Done in the repo and trackers; the application workspace later wave (`TASK-100`) is implemented.
- v5 lifecycle spec and schema 004/005 in place; inbox classifier + job; employer thread matching; application state transitions via `roleforge.application_lifecycle` (apply_application_transition, is_allowed_transition).
- Interview event extraction exists as a deterministic job: `python -m roleforge.jobs.interview_event_extract` (writes to `interview_events`).
- Application update notifications exist as an optional job: `python -m roleforge.jobs.application_notify` (disabled by default).
- Interview AI enrichment exists as an optional job: `python -m roleforge.jobs.interview_event_ai_enrich` (disabled by default).
- Web operator console exists: `roleforge/web/` (FastAPI+Jinja2+HTMX) with Bearer auth and pages `/analytics`, `/system-health`, `/sources`, `/queue-browser`, `/profiles`, `/applications`, `/applications/{id}`.
- `python -m pytest tests/ -q` passed with 243 tests.

## Done In This Session

- **TASK-100:** application workspace later wave:
  - `/applications`: recent applications with vacancy/profile/status/interview counts
  - `/applications/{id}`: read-only chronological timeline view over application state, employer thread activity, and interview events
  - query helpers, templates, tests, docs, backlog, and prompts updated

## Next Best Block

- The tracked roadmap backlog is now complete.
- The next session should focus on project close-out hygiene and next-phase definition:
  - audit remaining product gaps from actual usage,
  - define the next roadmap wave,
  - seed any new epics/tasks into docs first, then sync Linear and GitHub.

## User Prep

- none.

## First Actions

1. Read the completed roadmap, architecture, and current prompts to understand the shipped system as a whole.
2. Perform a deep audit of what is implemented versus what is still only implicit or rough-edged in docs/product flow.
3. Propose the next product phase as concrete epics/tasks; once grounded, sync docs first, then Linear, then GitHub; regenerate prompts.

## Constraints

- Gmail-only MVP
- Postgres-first
- Telegram digest + review queue
- one primary AI provider in MVP
- keyring-first secrets under service=roleforge
- AI only post-scoring
- Do not reopen salary modeling unless a new explicit product decision changes the scope

## On Completion

- Update Linear first.
- Update GitHub mirror second.
- Leave close-out comments.
- Generate a new next-session prompt from the actual outcome.
