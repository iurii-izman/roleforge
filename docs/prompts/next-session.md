# Cursor Autopilot: EPIC-13 Scoring Engine Enhancement

Use this prompt for the next implementation sprint in Cursor.

This prompt is intentionally operational, not just descriptive:
- implement the current block
- validate it
- update canonical docs/backlog
- close Linear first
- mirror GitHub second
- then generate the next prompt from the actual result of this session

## Core operating mode

Use this prompt together with:
- [cursor-autopilot-roleforge.md](/var/home/user/Projects/roleforge/docs/prompts/cursor-autopilot-roleforge.md)

Treat that file as the standing execution policy.
Treat this file as the current sprint brief.

## Repository and context

Project root:
`/var/home/user/Projects/roleforge`

Mandatory reading before coding:
- `/var/home/user/Projects/roleforge/AGENTS.md`
- `/var/home/user/Projects/roleforge/README.md`
- `/var/home/user/Projects/roleforge/docs/architecture.md`
- `/var/home/user/Projects/roleforge/docs/roadmap.md`
- `/var/home/user/Projects/roleforge/docs/research-v4-plus.md`
- `/var/home/user/Projects/roleforge/docs/manual-tasks.md`
- `/var/home/user/Projects/roleforge/docs/backlog/roleforge-backlog.json`
- `/var/home/user/Projects/roleforge/docs/prompts/cursor-autopilot-roleforge.md`

Current truth:
- v3.2 is complete
- V4+ backlog is already seeded into Linear and GitHub
- `EPIC-13` is the critical path
- no later v4 block should start until EPIC-13 is truly validated

## Canonical current block

Work only on:
- `EPIC-13`
- `TASK-050`
- `TASK-051`
- `TASK-052`
- `TASK-053`
- `TASK-054`
- `TASK-055`

Do not pull in `EPIC-14+` implementation unless it is required for validation and is tiny.

## Why this block matters

Current scoring is structurally placeholder-like:
- `_dimension_title_match` behaves like title presence, not real matching
- `_dimension_company_match` behaves like company presence, not preference
- `_dimension_keyword_bonus` is effectively dead

As a result:
- many vacancies collapse into nearly identical scores
- score bands are not meaningful
- near-real-time alerting in `v4` would be noisy and unreliable

`EPIC-13` must make scoring actually discriminative.

## Deliverables

### TASK-050

Implement real keyword overlap in `roleforge/scoring.py` for `_dimension_title_match`.

Target:
- tokenize vacancy title
- lowercase and normalize
- compare against `profile.config.keywords`
- return normalized overlap score in `0..1`
- if keywords are empty, keep neutral fallback only when needed and document it clearly

### TASK-051

Implement real `_dimension_company_match`.

Target:
- respect `preferred_companies`
- respect excluded companies consistently
- if no company preference exists, stay neutral rather than falsely positive

### TASK-052

Extend profile config shape.

Target fields:
- `keywords`
- `skills`
- `preferred_companies`

Update:
- `/var/home/user/Projects/roleforge/scripts/seed_profiles_v2.py`
- any profile config docs/specs touched by this change

### TASK-053

Implement real `_dimension_keyword_bonus`.

Target:
- use `profile.config.skills`
- reward actual relevant matches
- keep score deterministic and capped

### TASK-054

Calibrate on real data after the deterministic changes land.

Required:
- reseed profiles if needed
- rerun scoring
- inspect actual score distribution
- confirm high / medium / low bands are meaningfully separated
- document short calibration notes

### TASK-055

Update scoring docs.

At minimum update:
- `/var/home/user/Projects/roleforge/docs/specs/scoring-spec.md`

## Files that are expected to change

- `/var/home/user/Projects/roleforge/roleforge/scoring.py`
- `/var/home/user/Projects/roleforge/scripts/seed_profiles_v2.py`
- `/var/home/user/Projects/roleforge/tests/test_scoring.py`
- `/var/home/user/Projects/roleforge/docs/specs/scoring-spec.md`

Possibly also:
- `/var/home/user/Projects/roleforge/docs/architecture.md`
- `/var/home/user/Projects/roleforge/docs/manual-tasks.md`
- `/var/home/user/Projects/roleforge/docs/backlog/roleforge-backlog.json`

## What not to do

- do not implement `EPIC-14` delivery jobs in this sprint
- do not add AI to scoring
- do not add tables
- do not redesign the whole scoring architecture
- do not silently weaken explainability
- do not close tasks just because tests pass if real score differentiation is still poor

## Validation requirements

Run from host:

```bash
cd /var/home/user/Projects/roleforge
source /var/home/user/Projects/roleforge/.venv/bin/activate
python -m pytest tests/ -v
python /var/home/user/Projects/roleforge/scripts/seed_profiles_v2.py
python /var/home/user/Projects/roleforge/scripts/run_scoring_once.py
```

Then inspect score distribution using SQL:

```bash
cd /var/home/user/Projects/roleforge
podman exec roleforge-pg psql -U roleforge -d roleforge -c "SELECT p.name, CASE WHEN pm.score >= 0.75 THEN 'high' WHEN pm.score >= 0.5 THEN 'medium' ELSE 'low' END AS band, COUNT(*) AS cnt, ROUND(AVG(pm.score)::numeric, 3) AS avg_score FROM profile_matches pm JOIN profiles p ON p.id = pm.profile_id GROUP BY p.name, band ORDER BY p.name, band;"
```

Minimum acceptance:
- tests pass
- scores are no longer collapsed into one flat band
- queue explainability still makes sense
- docs match code

## Tracker discipline

Linear is canonical.
GitHub is mirror.

### Start of session

Set the current block to `In Progress` in Linear first:

```bash
cd /var/home/user/Projects/roleforge
python /var/home/user/Projects/roleforge/scripts/linear_update_issues.py --issue-ids EPIC-13,TASK-050,TASK-051,TASK-052,TASK-053,TASK-054,TASK-055 --state "In Progress"
```

Then mirror in GitHub:
- move the project items to active execution state if practical
- or at minimum leave a short start comment on the epic / key task issue

Use issue prefixes as stable keys:
- `EPIC-13`
- `TASK-050`
- `TASK-051`
- `TASK-052`
- `TASK-053`
- `TASK-054`
- `TASK-055`

### End of session

Only after code is implemented and validated:

1. Update canonical docs/backlog status in repo if the work is actually complete.
2. Mark the completed issues `Done` in Linear first.
3. Mirror completion in GitHub second.
4. Leave close-out comments in both systems.

If the whole block is fully done, run:

```bash
cd /var/home/user/Projects/roleforge
python /var/home/user/Projects/roleforge/scripts/linear_update_issues.py --issue-ids TASK-050,TASK-051,TASK-052,TASK-053,TASK-054,TASK-055,EPIC-13 --state "Done"
```

If only part of the block is done:
- close only the tasks actually completed
- keep the rest `In Progress` or move back to `Ready` / `Blocked`
- do not close the epic early

For GitHub mirror:
- close the matching task issues only after Linear is updated
- if all child tasks under `EPIC-13` are truly done, close the epic issue too
- leave a short comment with:
  - what shipped
  - what was validated
  - what remains, if anything

## Mandatory next-iteration handoff

Before ending the session, Cursor must generate the next sprint prompt from the actual post-session repo state.

Required outputs:

1. Update:
- `/var/home/user/Projects/roleforge/docs/prompts/next-session.md`

It must no longer describe the old plan. It must describe the actual next best block based on:
- what was finished now
- what remains open in Linear
- what is now unblocked
- any new blockers discovered during implementation

2. Update if needed:
- `/var/home/user/Projects/roleforge/docs/manual-tasks.md`

Use it to keep the manual decision list honest.

3. Update if needed:
- `/var/home/user/Projects/roleforge/docs/backlog/roleforge-backlog.json`

Only if task statuses or readiness materially changed.

## Rule for choosing the next prompt

When generating the next prompt, use this order:

1. If `EPIC-13` is incomplete:
   - write the next prompt as a continuation / finish pass for `EPIC-13`
2. If `EPIC-13` is complete:
   - the next prompt should target `EPIC-20` quick wins and/or `TASK-056` decision preparation
3. Only after a real product decision on `TASK-056`:
   - write the next implementation prompt for `EPIC-14`

The next prompt must include:
- exact backlog IDs
- exact files likely to change
- validation commands
- tracker update expectations
- what must not be done in that sprint

## Close-out standard

Do not finish the session until all of the following are true:

- code is implemented or blocker is explicit
- tests are run
- calibration / validation is run where required
- docs are updated
- Linear is updated first
- GitHub is mirrored second
- `docs/prompts/next-session.md` is rewritten for the next real iteration

## Short execution summary format

At the end, return a short handoff containing:
- completed backlog IDs
- still-open backlog IDs
- validation result
- tracker updates made
- next sprint selected
