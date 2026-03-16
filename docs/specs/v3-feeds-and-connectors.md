## v3.1 Feeds and v3.2 Connectors (EPIC-11, EPIC-12)

Status: TASK-046 and TASK-047 implemented (v3.1). TASK-048–TASK-049 (v3.2) placeholder.

These specs are explicitly post-MVP and build on the existing Gmail-only, Postgres-first pipeline. They do not change MVP behavior.

### 1. v3.1 Feed registry and kill-switch (TASK-046) — Implemented

Goal: introduce a registry of structured feed sources (e.g. RSS, Atom) while preserving the existing normalized vacancy schema and dedup path.

- **Source registry:** File-driven; no DB table. `config/feeds.yaml` lists feeds with `id`, `name`, `url`, `type` (rss|atom), `enabled`. Loaded by `roleforge.feed_registry.load_registry()` / `get_enabled_feeds()`.
- **Kill-switch:** Global env `FEED_INTAKE_ENABLED` (default false). Per-feed: `enabled: true/false` in YAML.
- **Constraints:** All feeds ingest into the same normalized schema and dedup path; no new vacancy schema; `vacancy_observations` extended with optional `feed_source_key` (schema 002).
- **Operational behavior:** Feeds enabled/disabled via YAML; feed_poll job reads registry from file.

### 2. v3.1 Feed intake via normalized schema (TASK-047) — Implemented

Goal: feed intake reuses the same normalization and dedup pipeline as Gmail.

- **Ingestion flow:** `python -m roleforge.jobs.feed_poll`. Loads enabled feeds from `config/feeds.yaml`, fetches RSS/Atom via `feedparser`, converts each entry to candidate shape with `feed_source_key = "{feed_id}:{entry_id}"`. New entries only (seen keys from `vacancy_observations.feed_source_key`). Runs `group_by_dedup_key` and `persist_deduped`; observations with `feed_source_key` use the same get-or-create vacancy path.
- **Idempotency:** Stable entry id from entry.id / link / title; duplicate entries skipped; dedup by URL/title/company unchanged.
- **No replay of feed body:** Feed item payload is not stored; only normalized vacancies and observation links. Re-run feed_poll to re-ingest; idempotent via observation unique.


### 3. v3.2 Connector contract (TASK-048)

Goal: define a selection contract for official connectors (e.g. ATS APIs) so that they are added only when maintenance cost and legal clarity justify them.

- **Connector evaluation dimensions:**
  - legal clarity (terms of use, rate limits, allowed use of data),
  - structured value (how much richer than email/feeds the data is),
  - maintenance burden (API stability, auth complexity),
  - overlap with existing sources (does it duplicate Gmail/feeds?).
- **Connector design rules:**
  - every connector must emit into the same normalized vacancy schema and dedup path,
  - connector-specific logic should be isolated to a small adapter layer,
  - connectors should be independently kill-switchable (similar to feeds).

No connector is implemented until the MVP and v2 pipeline are stable and there is a clear ROI case.

### 4. v3.2 First connector candidates (TASK-049)

Goal: when metrics and usage patterns are available, evaluate and rank first official connectors.

- **Inputs:**
  - real-world usage metrics from Gmail and, optionally, feeds,
  - operator feedback about missing sources or friction points.
- **Outputs:**
  - a ranked list of connector candidates with brief reasoning per candidate,
  - a decision about whether to proceed with any connector in the next phase.

This task is planning/decision work and stays explicitly blocked until after post-MVP data exists.

