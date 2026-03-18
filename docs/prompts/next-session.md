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
- roleforge/inbox_classifier.py (and tests/test_inbox_classifier.py)
- any files changed in the previous session that are directly relevant

## Current State

- EPIC-17 remains In Progress in Linear and GitHub.
- TASK-071, TASK-072, TASK-073, TASK-074, TASK-075, TASK-076, TASK-077, and TASK-083 are Done in the repo.
- v5 lifecycle spec and schema 004/005 in place; inbox classifier + job exist; employer thread matching exists.
- docs/architecture.md, README.md, schema/README.md, and docs/manual-tasks.md are updated.
- `python -m pytest` passed with 201 tests.

## Done In This Session

- **Linear/GitHub sync:** Marked TASK-072 and TASK-073 Done in Linear; closed GitHub issues #76 and #77 with close-out comments.
- **TASK-074:** Wrote docs/specs/ai-inbox-classification-contract.md: when to call AI (only when `classified_as` NULL, cap per run), input (subject, snippet, from_domain), output (vacancy_alert | employer_reply | other), merge rule, timeout/retry/fallback, cost in job summary.
- **TASK-075:** Implemented `roleforge/inbox_classifier.py`: deterministic rules (thread linked → employer_reply; intake label + single-message thread → vacancy_alert; subject/from heuristics; else ambiguous). Added `tests/test_inbox_classifier.py` (8 tests).
- **TASK-076:** Implemented `roleforge/jobs/inbox_classify.py`: selects `classified_as IS NULL`, resolves intake label IDs from config/env, runs deterministic classifier, updates rows idempotently, and writes `job_runs`.
- **TASK-077:** Implemented employer thread matching and `employer_threads` record creation.
- **Linear/GitHub:** Mark TASK-076 and TASK-077 Done in Linear and close GitHub issues #80 and #81 with close-out comments.

## Next Best Block

- **TASK-078:** Implement application state transitions via Telegram actions.
- Then TASK-079 (interview event extraction) and TASK-080 (application update notifications).

## User Prep

- none for TASK-078 by default. If transition UX gets ambiguous, choose the smallest Telegram-first action model that matches the approved lifecycle states.

## First Actions

1. Start TASK-078: wire Telegram actions to the `applications.status` state machine from `schema/004_application_lifecycle.sql`.
2. Keep transitions explicit and auditable; reject invalid jumps.
3. Run pytest after code changes; update Linear/GitHub when TASK-078 is done.

## Constraints

- Gmail-only MVP
- Postgres-first
- Telegram digest + review queue
- one primary AI provider in MVP
- keyring-first secrets under service=roleforge
- AI only post-scoring
- Do not close EPIC-18 until TASK-089 and TASK-090 are done
- Do not move into full classifier or interview automation before the lifecycle state machine is approved

## If Blocked

- No user input needed for this block. If drift appears, reconcile Linear/GitHub and continue.

## On Completion

- Update Linear first.
- Update GitHub mirror second.
- Leave close-out comments.
- Generate a new next-session prompt from the actual outcome.
