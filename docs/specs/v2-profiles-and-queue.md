## v2 Profiles, Queue UX, and Analytics (EPIC-10)

Status: Placeholder spec for TASK-044 and TASK-045 (v2 Enhancements).

This spec refines the MVP behavior for profiles, queue UX, summaries, and basic analytics after the Gmail-only pipeline is stable.

### 1. Profiles beyond MVP minimum (TASK-044)

MVP uses a single `default_mvp` profile with minimal hard filters and shared scoring. v2 can safely expand profile behavior without changing the underlying schema:

- Multiple named profiles for distinct intents, for example:
  - `primary_search` — main profile used in MVP today.
  - `stretch_geo` — same stack, but looser location filters (e.g. more countries or time zones).
  - `experimental` — captures borderline or exploratory vacancies (new domains, stacks).
- Profile configuration still lives in `profiles.config` JSONB and reuses the existing shape:
  - `hard_filters` — location, exclude titles/companies, min_parse_confidence.
  - `weights` — per-dimension weights for the shared scoring formula.
  - optional `min_score` — per-profile floor for digest/queue inclusion.

v2 does **not** add new tables for profiles; it only:

- introduces a small number (2–4) of well-defined additional profiles,
- documents their intent and approximate filters (e.g. “Remote-only senior backend”, “EU-friendly time zones”),
- wires them into the same scoring and queue paths used by `default_mvp`.

### 2. Queue UX improvements (TASK-045, part 1)

MVP queue behavior (see `telegram-interaction.md`) is intentionally minimal: one card at a time, fixed action set, simple text formatting. v2 improves ergonomics without changing core semantics:

- **Better navigation and context:**
  - show the position in queue for the current match (e.g. “3 of 15”),
  - optional command to jump to the next profile or back to digest summary.
- **Richer card content (still text-only):**
  - include a one-line “reason” summary from explainability (e.g. top 1–2 positive factors),
  - optionally show a compact salary/location hint if available (e.g. “~$X, Remote EU-friendly”).
- **Non-destructive “back” or “undo” path:**
  - v2 may add a short-lived “undo last action” command that reverts the last `review_actions` entry and restores the previous state for a single match.

These improvements stay within Telegram’s basic text + inline button model; no carousels or multi-message threads per vacancy are introduced.

### 3. Summaries and digest refinements (TASK-045, part 2)

The MVP digest already groups by profile and shows aggregate counts plus a few highlights. v2 can refine this without changing the underlying data:

- **Per-profile streaks or trends:**
  - show simple trend hints like “+3 vs yesterday” for new matches in the digest header per profile.
- **Per-bucket counts:**
  - explicitly distinguish high-priority vs medium-priority counts (e.g. “5 high, 8 medium, 12 low”).

All of this can be derived from existing `profile_matches` state and `review_actions` history; no new tables are required.

### 4. Basic analytics (TASK-045, part 3)

Analytics in v2 focuses on a few operator-centric questions that can be answered from Postgres:

- For a given time window:
  - how many new matches were created per profile?
  - how many items moved to `shortlisted`, `ignored`, `review_later`, `applied`?
  - what percentage of high-priority matches eventually became `applied`?
- For a given profile:
  - how long, on average, items stay in `new` before the first review action?

These queries can be served initially via ad-hoc SQL or a minimal CLI/console script (no separate dashboard in v2). Any future UI can reuse the same queries.

