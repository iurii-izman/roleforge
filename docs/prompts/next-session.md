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
- TASK-071 through TASK-078 and TASK-083 are Done in the repo.
- EPIC-18 is resolved by product decision: keep `salary_raw` only; no `salary_structured` in the current roadmap.
- TASK-093 is Done as a scope decision in `docs/specs/v7-web-ui.md`.
- Application state transitions: `roleforge.application_lifecycle` (apply_application_transition, is_allowed_transition); Telegram handlers call it with application_id and target status.
- `python -m pytest` passed with 217 tests.

## Done In This Session

- **TASK-078:** Application state transitions via Telegram actions. Module `roleforge/application_lifecycle.py` with state machine (allowed transitions per v5), apply_application_transition, get_current_status; 16 tests; v5 spec and README updated with Telegram contract.
- **EPIC-18 / TASK-089 / TASK-090:** Closed by explicit product decision: keep `salary_raw` only, do not add `salary_structured` or salary-aware scoring in the current roadmap.
- **TASK-093:** Web UI scope fixed in `docs/specs/v7-web-ui.md`.

## Next Best Block

- **TASK-079:** Interview event extraction from employer emails.
- Then TASK-080 (application update notifications).

## User Prep

- none for TASK-079 by default.

## First Actions

1. Start TASK-079: interview event extraction from employer threads.
2. Prefer a deterministic first pass for extracting datetime / meeting link / short notes into `interview_events`.
3. Run pytest after changes; update Linear/GitHub when done.

## Constraints

- Gmail-only MVP, Postgres-first, Telegram digest + review queue, one primary AI provider, keyring-first secrets, AI only post-scoring. Keep Telegram as the primary action surface.

## On Completion

- Update Linear first, then GitHub; leave close-out comments; generate a new next-session prompt.
