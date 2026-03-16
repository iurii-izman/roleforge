## v3.1 Feeds and v3.2 Connectors (EPIC-11, EPIC-12)

Status: TASK-046 and TASK-047 implemented (v3.1). TASK-048 and TASK-049 (v3.2) defined below; no connector implementation yet.

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

Goal: define a **minimal** selection and integration contract for official connectors (e.g. ATS APIs) so that they are added only when maintenance cost and legal clarity justify them. Contract is reuse-first: no new tables; same candidate → normalize → dedup → scoring pipeline.

#### 3.1 Output contract (ingestion shape)

Every connector **must** emit the same **candidate shape** as Gmail and feeds:

- **Vacancy fields:** `canonical_url`, `company`, `title`, `location`, `salary_raw`, `parse_confidence` (see [vacancy-schema](vacancy-schema.md)).
- **Source linkage:** exactly one of:
  - `gmail_message_id` (Gmail only), or
  - `feed_source_key` (feeds and connectors).
- **Observation metadata:** `fragment_key`, `raw_snippet` (optional but recommended).

For connectors, **reuse** `vacancy_observations.feed_source_key` with a reserved prefix so that no schema change is required:

- **Convention:** `feed_source_key = "connector:{connector_id}:{stable_external_id}"`.
- Examples: `connector:greenhouse:12345`, `connector:lever:abc-def`.
- Existing code: `group_by_dedup_key` and `persist_deduped` already accept any `feed_source_key`; the unique index on `(vacancy_id, feed_source_key, fragment_key)` applies. No migration needed.

Connector adapters are responsible for mapping external API/UI payloads into this candidate dict; normalization and dedup remain shared.

#### 3.2 Connector evaluation dimensions (selection contract)

Before adding any official connector, evaluate:

- **Legal clarity:** terms of use, rate limits, allowed use of data (scraping vs API).
- **Structured value:** how much richer than email/feeds the data is (e.g. structured salary, location, seniority).
- **Maintenance burden:** API stability, auth complexity, deprecation risk.
- **Overlap:** does it duplicate Gmail or feeds for the same jobs? Prefer complementary sources.

#### 3.3 Design rules

- Every connector emits into the **same** normalized vacancy schema and dedup path (no per-connector pipeline).
- Connector-specific logic is isolated to a **small adapter layer** (e.g. `roleforge.connectors.<name>.to_candidates()`).
- Connectors are **independently kill-switchable**: global env + per-connector enabled flag (see §4).

No connector is implemented until the MVP and v2 pipeline are stable and there is a clear ROI case.

---

### 4. v3.2 Enable/disable model for connectors

- **Global kill-switch:** env `CONNECTOR_INTAKE_ENABLED` (default `false`). When false, no connector job or connector branch runs.
- **Per-connector:** registry entry has `enabled: true/false` (e.g. in `config/connectors.yaml` when introduced). Only enabled connectors are polled.
- **Registry shape (future):** file-driven, like feeds; no DB table. Suggested keys: `id`, `name`, `type`, `enabled`, plus connector-specific config (e.g. API base URL, credentials reference). Implement registry and job when the first connector is added.

This mirrors the feed model (FEED_INTAKE_ENABLED + per-feed `enabled`) for consistency.

---

### 5. v3.2 First connector candidates (TASK-049)

Goal: choose 1–2 first official connector candidates for when metrics and product go-ahead exist. No implementation until then.

**Selected candidates (ranked):**

1. **Greenhouse (ATS)**  
   - **Why:** Widely used ATS; public Job Board API; structured job posts (title, location, company, application URL). Clear ToS for job listing aggregation.  
   - **Risks:** API key or no auth for public boards; rate limits; per-customer board URLs.  
   - **Fit:** High structured value; complements Gmail/feeds for companies that post on Greenhouse.

2. **Lever (ATS)**  
   - **Why:** Common ATS; Postings API; similar structured value to Greenhouse.  
   - **Risks:** Auth and rate limits; some boards require discovery.  
   - **Fit:** Alternative or second ATS if we want two ATS connectors; slightly more discovery friction than Greenhouse.

**Decision:** Proceed with **one** ATS first (Greenhouse preferred) once MVP metrics and operator demand justify it. Add Lever only if a second ATS is clearly needed. No job boards or other connectors in the first wave to avoid sprawl.

**Inputs for go/no-go (when unblocking):** real-world usage metrics from Gmail/feeds, operator feedback on missing sources.

---

### 6. Risks, limitations, rollout path

**Risks**

- **Legal:** Each connector must comply with provider ToS and rate limits; operator responsibility to obtain API access and stay within terms.
- **Data quality:** Connector-specific bugs can inject bad or duplicate data; monitoring and kill-switch are essential.
- **Scope creep:** Adding many connectors increases maintenance; strict gating (one at a time, clear ROI) required.

**Limitations**

- **No new tables in v3.2:** Connectors reuse `feed_source_key` and existing vacancy/observation tables.
- **Replay:** Connector-sourced observations do not store raw API payload by default (same as feeds); re-run connector poll for re-ingestion. If audit requires raw payload, a future optional store can be added per connector.
- **Auth:** Connector credentials (API keys, etc.) are out of scope in this contract; use keyring or env per existing patterns when implementing.

**Rollout path**

1. **Now:** Contract and candidates documented; no code beyond docs.
2. **When unblocked:** Add file registry (e.g. `config/connectors.yaml`), `CONNECTOR_INTAKE_ENABLED`, and a single connector job (or branch in a unified “sources” job) that calls only enabled connectors.
3. **First connector:** Implement Greenhouse adapter (or chosen candidate); emit candidates with `feed_source_key = "connector:greenhouse:{id}"`; run through existing normalize/dedup/persist.
4. **Validate:** Run in parallel with Gmail/feeds; compare duplicate rate and quality; then enable by default if acceptable.

