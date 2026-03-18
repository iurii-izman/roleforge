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
- roleforge/jobs/inbox_classify.py (and tests/test_inbox_classify_job.py)
- roleforge/employer_thread_matching.py (and tests/test_employer_thread_matching.py)
- roleforge/jobs/employer_thread_match.py (and tests/test_employer_thread_match_job.py)
- any files changed in the previous session that are directly relevant

## Current State

- EPIC-17 remains In Progress in Linear and GitHub.
- TASK-071, TASK-072, TASK-073, TASK-074, TASK-075, TASK-076, TASK-077, and TASK-083 are Done in the repo.
- v5 lifecycle spec and schema 004/005 in place; inbox classifier + job exist; employer thread matching exists.
- `python -m pytest` passed with 201 tests.

## Done In This Session

- **TASK-077:** Implemented employer thread matching and `employer_threads` record creation.
  - New module: `roleforge/employer_thread_matching.py`
    - For `gmail_messages.classified_as = 'employer_reply'`, reads `raw_metadata.threadId`
    - Resolves an application by joining `applications` to `vacancy_observations` → `gmail_messages` by matching `threadId`
    - Creates/updates `employer_threads` via `INSERT ... ON CONFLICT (gmail_thread_id) DO UPDATE`
    - Idempotent behavior; also refreshes `last_message_at` for already-linked threads
  - New job entrypoint: `python -m roleforge.jobs.employer_thread_match` (job_runs `job_type=employer_thread_match`)
  - Tests: `tests/test_employer_thread_matching.py`, `tests/test_employer_thread_match_job.py`
  - Docs: updated `README.md` runtime entrypoints and `docs/manual-tasks.md` block F.

## Next Best Block

- **TASK-078:** Implement application state transitions via Telegram actions.
- Then TASK-079–TASK-082.

## User Prep

- none.

## First Actions

1. Update Linear: set TASK-076 and TASK-077 to Done; update GitHub mirror and leave close-out comments.
2. Start TASK-078: implement Telegram actions to transition `applications.status` with validation (state machine from `docs/specs/v5-application-lifecycle.md`).

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

- If drift between Linear and GitHub appears, reconcile and continue. No user input needed for TASK-078 unless Telegram bot access/secrets are missing.

## On Completion

- Update Linear first.
- Update GitHub mirror second.
- Leave close-out comments.
- Generate a new next-session prompt from the actual outcome.
