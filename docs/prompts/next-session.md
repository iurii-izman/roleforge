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
- EPIC-19 is Done in the repo and in tracking systems; all child tasks including `TASK-100` are complete.
- Application workspace timeline view exists as a read-only web slice: `/applications` and `/applications/{id}` list applications and show chronological events over applications, employer threads, and interview events.
- `python -m pytest tests/ -q` passed with 243 tests.

## Done In This Session

- **TASK-100:** application workspace timeline view:
  - `/applications`: recent applications with vacancy, profile, status, and interview count.
  - `/applications/{id}`: read-only chronological timeline combining application events, employer thread activity, and interview events with vacancy and profile context.
  - Queries implemented in `roleforge/web/queries.py`; templates in `roleforge/web/templates/`; docs, backlog, and prompts updated; tests for queries added.

## Next Best Block

- The tracked roadmap backlog in `docs/backlog/roleforge-backlog.json` is now fully complete.
- The next session should be a structured close-out and next-phase planning pass:
  - audit what shipped across MVP through v7,
  - verify tracker hygiene across Linear and GitHub,
  - identify the next product phase or new epic set based on real gaps, not placeholder scope.

## User Prep

- none.

## First Actions

1. Audit the repository, docs, and trackers end-to-end and confirm that all existing roadmap epics are actually complete in code.
2. Produce a concise next-phase recommendation: what should come after the completed backlog, and why.
3. If a new phase is defined, turn it into concrete epics/tasks in docs first, then sync Linear and GitHub, then regenerate the next-session prompts.

## Constraints

- Gmail-only MVP, Postgres-first, Telegram digest + review queue, one primary AI provider, keyring-first secrets, AI only post-scoring. Keep Telegram as the primary action surface.

## On Completion

- Update Linear first, then GitHub; leave close-out comments; generate a new next-session prompt.
