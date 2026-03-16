## v2 Profiles, Queue UX, and Analytics (EPIC-10)

Status: Implemented and validated for TASK-044 and TASK-045 (v2 Enhancements).

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

Concretely, the repository now provides a small preset set via `scripts/seed_profiles_v2.py`:

- `default_mvp` — unchanged MVP baseline; minimal filters, `weights = DEFAULT_WEIGHTS`, `min_score = null`.
- `primary_search` — main profile: remote-first, EU-friendly:
  - intent: primary search: remote-first, EU-friendly,
  - hard_filters: `locations = ["remote", "europe", "eu", "europe/remote"]`, `exclude_titles = ["intern", "junior"]`,
  - weights: `DEFAULT_WEIGHTS`,
  - min_score: `0.5`.
- `stretch_geo` — stretch geography: remote + Americas / global:
  - intent: stretch geography: remote + Americas / global,
  - hard_filters: `locations = ["remote", "us", "americas", "global", "worldwide"]`, `exclude_titles = ["intern"]`,
  - weights: `DEFAULT_WEIGHTS`,
  - min_score: `0.35`.

Operator usage:

1. Run `scripts/seed_profiles_v2.py` after the MVP schema is applied and the DB is reachable to (re)seed these profiles.
2. Adjust `profiles.config` JSONB in-place for each profile (locations, excludes, min_score) as the real search intent becomes clearer.
3. Re-run `scripts/run_scoring_once.py` to refresh `profile_matches` and review ranks based on the new profiles.

Preset ideas (customize in DB or fork the seed script):

- **EU backend / remote-first:** `primary_search` as-is (locations: remote, europe, eu; exclude intern/junior; min_score 0.5).
- **Global IC / stretch:** `stretch_geo` as-is (locations: remote, us, americas, global, worldwide; exclude intern; min_score 0.35).
- For other intents (e.g. “US-only”, “Berlin on-site”), add a fourth profile in the seed script or insert manually and re-run scoring.

### 2. Queue UX improvements (TASK-045, part 1)

MVP queue behavior (see `telegram-interaction.md`) is intentionally minimal: one card at a time, fixed action set, simple text formatting. v2 improves ergonomics without changing core semantics:

- **Better navigation and context (implemented):**
  - queue cards now include an explicit queue position line such as `Queue: 1 of 5`, derived from `profile_matches.review_rank` and filtered by state (`ignored` / `applied` are excluded),
  - the active profile name is rendered on the card (`Profile: primary_search`), so multi-profile queues are easier to interpret.
- **Richer card content (still text-only, implemented):**
  - the card includes a compact “Why in queue” explanation based on the top positive explainability factors from the scoring engine (e.g. “Title match, Location match”),
  - basic score banding is reflected in the digest (see below), but the queue itself remains score-first by `review_rank`.
- **Non-destructive “back” or “undo” path (deferred):**
  - an explicit undo action is left for a later iteration; current v2 keeps the MVP state model and actions unchanged.

These improvements stay within Telegram’s basic text + inline button model; no carousels or multi-message threads per vacancy are introduced.

### 3. Summaries and digest refinements (TASK-045, part 2)

The MVP digest already groups by profile and shows aggregate counts plus a few highlights. v2 refines this without changing the underlying data:

- **Per-bucket counts (implemented):**
  - each profile line now includes both score bands and state counts, for example  
    `Backend: 10 total (bands: 4 high, 3 medium, 3 low; states: 5 new, 3 shortlisted, 2 later)`,
  - bands are derived from `profile_matches.score` with thresholds `>= 0.75` (high), `>= 0.5` (medium), `< 0.5` (low).
- **Per-profile streaks or trends (deferred):**
  - simple trend hints like “+3 vs yesterday” remain a possible follow-up; the current v2 iteration stops at static per-run bands and counts.

All of this is derived from existing `profile_matches` state; no new tables are required.

### 4. Basic analytics (TASK-045, part 3)

Analytics in v2 focuses on a few operator-centric questions that can be answered from Postgres:

- For a given time window:
  - how many new matches were created per profile?
  - how many items moved to `shortlisted`, `ignored`, `review_later`, `applied`?
  - what percentage of high-priority matches eventually became `applied`?
- For a given profile:
  - how long, on average, items stay in `new` before the first review action?

These queries are served in v2 via a minimal CLI/console script (no separate dashboard in v2). Any future UI can reuse the same queries.

Repository helper:

- `scripts/report_profile_stats.py`
  - connects to Postgres using the existing `connect_db` helper,
  - accepts either `--days N` (look back N days from now, UTC) or `--since 2026-03-15T00:00:00` (explicit ISO timestamp),
  - aggregates per-profile:
    - `matches_total`,
    - `state_counts` (counts by `profile_matches.state`, e.g. `new`, `shortlisted`, `ignored`, `applied`),
    - `high_score_matches` (score `>= 0.75`),
    - `new_in_window` (when `--days`/`--since` is set: matches with `created_at` in that window),
    - `high_score_applied` (count of matches with score `>= 0.75` and state `applied`).

Example:

```bash
python scripts/report_profile_stats.py --days 7
```

This prints a JSON summary with the effective `since` boundary and per-profile aggregates, suitable for quick operator checks or ad-hoc jq processing.

#### Ad-hoc SQL examples

Run against the same database as the app (e.g. `psql "$DATABASE_URL"` or `podman exec -i roleforge-pg psql -U roleforge -d roleforge`).

Matches per profile (all time):

```sql
SELECT p.name, pm.state, COUNT(*) AS cnt
FROM profile_matches pm
JOIN profiles p ON p.id = pm.profile_id
GROUP BY p.name, pm.state
ORDER BY p.name, pm.state;
```

High-score matches that became applied:

```sql
SELECT p.name, COUNT(*) AS high_applied
FROM profile_matches pm
JOIN profiles p ON p.id = pm.profile_id
WHERE pm.score >= 0.75 AND pm.state = 'applied'
GROUP BY p.name;
```

New matches in the last 7 days (UTC):

```sql
SELECT p.name, COUNT(*) AS new_in_window
FROM profile_matches pm
JOIN profiles p ON p.id = pm.profile_id
WHERE pm.created_at >= NOW() - INTERVAL '7 days'
GROUP BY p.name;
```
