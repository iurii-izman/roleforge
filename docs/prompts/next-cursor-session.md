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
- TASK-071, TASK-072, TASK-073, TASK-074, TASK-075, and TASK-083 are Done (Linear and GitHub updated).
- v5 lifecycle spec and schema 004/005 in place; inbox classifier spec (TASK-073), AI inbox classification contract (TASK-074), and `roleforge.inbox_classifier` (TASK-075) implemented.
- docs/architecture.md, README.md, schema/README.md, and docs/manual-tasks.md are updated.
- `python -m pytest` passed with 186 tests.

## Done In This Session

- **Linear/GitHub sync:** Marked TASK-072 and TASK-073 Done in Linear; closed GitHub issues #76 and #77 with close-out comments.
- **TASK-074:** Wrote docs/specs/ai-inbox-classification-contract.md: when to call AI (only when `classified_as` NULL, cap per run), input (subject, snippet, from_domain), output (vacancy_alert | employer_reply | other), merge rule, timeout/retry/fallback, cost in job summary.
- **TASK-075:** Implemented `roleforge/inbox_classifier.py`: deterministic rules (thread linked → employer_reply; intake label + single-message thread → vacancy_alert; subject/from heuristics; else ambiguous). Added `tests/test_inbox_classifier.py` (8 tests).
- **TASK-083:** Wrote docs/specs/v5-application-lifecycle.md and aligned README / architecture / schema docs.
- **Linear/GitHub:** Marked TASK-074, TASK-075, and TASK-083 Done in Linear; closed GitHub issues #78, #79, and #87 with close-out comments.

## Next Best Block

- **TASK-076:** Implement `roleforge/jobs/inbox_classify.py` — run the inbox classifier on stored unclassified messages and set `gmail_messages.classified_as`. Use `roleforge.inbox_classifier.classify_message`; only update rows where `classified_as IS NULL`; pass intake label IDs from config/env. Log job_runs; optional: ai_cost_usd when AI fallback is added later.
- Then TASK-077 (employer thread matching), TASK-078 (state transitions via Telegram), etc.

## User Prep

- none.

## First Actions

1. Continue with TASK-076: add `roleforge/jobs/inbox_classify.py` that selects unclassified messages from `gmail_messages`, calls `inbox_classifier.classify_message` for each (with conn and intake_label_ids), and updates `classified_as` where result is not None and current value is NULL.
2. Resolve intake label IDs (e.g. from Gmail reader config or env); document in job or deployment contract.
3. Run pytest after code changes; update Linear/GitHub when TASK-076 is done.

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
