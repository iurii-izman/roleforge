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

- EPIC-17 remains In Progress in Linear and GitHub.
- TASK-071, TASK-072, TASK-073, TASK-074, TASK-075, TASK-076, TASK-077, TASK-078, and TASK-083 are Done in the repo.
- EPIC-18 is resolved by product decision: keep `salary_raw` only; no `salary_structured` in the current roadmap.
- TASK-093 is Done as a scope decision in `docs/specs/v7-web-ui.md`.
- v5 lifecycle spec and schema 004/005 in place; inbox classifier + job; employer thread matching; application state transitions via `roleforge.application_lifecycle` (apply_application_transition, is_allowed_transition).
- docs/architecture.md, README.md, schema/README.md, docs/manual-tasks.md, and docs/specs/v5-application-lifecycle.md updated.
- `python -m pytest` passed with 217 tests.

## Done In This Session

- **TASK-078:** Implemented application state transitions for Telegram actions. Added `roleforge/application_lifecycle.py`: APPLICATION_STATUSES, TERMINAL_STATUSES, is_allowed_transition (validates from→to per v5 spec), get_current_status, apply_application_transition (updates applications.status and updated_at; rejects invalid/missing). Added tests in tests/test_application_lifecycle.py (16 tests). Documented Telegram contract in v5 spec and README: handlers call apply_application_transition(conn, application_id, status) with callback data.
- **EPIC-18 / TASK-089 / TASK-090:** Closed by explicit product decision: keep `salary_raw` only, do not add `salary_structured` or salary-aware scoring in the current roadmap.
- **TASK-093:** Web UI scope fixed in `docs/specs/v7-web-ui.md`.

## Next Best Block

- **TASK-079:** Implement interview event extraction from employer emails.
- Then TASK-080 (application update notifications to Telegram).

## User Prep

- none for TASK-079 by default. If extraction requires AI, follow ai-inbox-classification-contract and cost governance.

## First Actions

1. Start TASK-079: extract interview events (dates, links, details) from employer threads into interview_events; align with docs/specs/v5-application-lifecycle.md and employer_threads data.
2. Keep the first pass deterministic where possible; AI remains a bounded fallback.
3. Run pytest after code changes; update Linear/GitHub when the block is done.

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
