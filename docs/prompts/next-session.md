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
- Application state transitions: `roleforge.application_lifecycle` (apply_application_transition, is_allowed_transition); Telegram handlers call it with application_id and target status.
- EPIC-19 foundation slice is Done: TASK-094, TASK-095, TASK-096, TASK-097, TASK-098, TASK-099, TASK-101 are complete.
- EPIC-19 remains In Progress only because TASK-100 (application workspace timeline view) is still open.
- `python -m pytest tests/ -q` passed with 241 tests.

## Done In This Session

- **EPIC-19 web operator console:** analytics, system health, sources, queue browser, and profile editor implemented and covered by tests.

## Next Best Block

- **EPIC-19 next:** `TASK-100` application workspace timeline view. Do not close EPIC-19 yet.

## User Prep

- none.

## First Actions

1. Implement `TASK-100`: application workspace timeline view in the web console.
2. Reuse the existing v5 schema (`applications`, `employer_threads`, `interview_events`) and keep the view read-mostly first.
3. Run `python -m pytest tests/ -q`; update Linear then GitHub mirror; regenerate next prompts.

## Constraints

- Gmail-only MVP, Postgres-first, Telegram digest + review queue, one primary AI provider, keyring-first secrets, AI only post-scoring. Keep Telegram as the primary action surface.

## On Completion

- Update Linear first, then GitHub; leave close-out comments; generate a new next-session prompt.
