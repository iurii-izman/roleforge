## v3.1 Feeds and v3.2 Connectors (EPIC-11, EPIC-12)

Status: Placeholder spec for TASK-046–TASK-047 (v3.1) and TASK-048–TASK-049 (v3.2).

These specs are explicitly post-MVP and build on the existing Gmail-only, Postgres-first pipeline. They do not change MVP behavior.

### 1. v3.1 Feed registry and kill-switch (TASK-046)

Goal: introduce a registry of structured feed sources (e.g. RSS, JSON APIs) while preserving the existing normalized vacancy schema and dedup path.

- **Source registry table** (conceptual; details to be defined later):
  - stores feed identifier, human-readable name, URL, type (RSS/Atom/JSON), and status,
  - contains a per-source kill-switch flag that can disable intake from that source without code changes.
- **Constraints:**
  - all feeds ingest into the same normalized schema and dedup path used by Gmail,
  - no new per-source vacancy schema; feeds map onto the existing vacancy fields.
- **Operational behavior:**
  - feeds can be enabled/disabled individually,
  - config is stored in Postgres and used by a feed-polling job; there is no separate configuration store.

Implementation of this registry remains blocked until MVP metrics are available and Gmail intake is stable.

### 2. v3.1 Feed intake via normalized schema (TASK-047)

Goal: any future feed intake must reuse the same normalization and dedup pipeline, not create a parallel system.

- **Ingestion flow (high level):**
  - a feed polling job fetches new feed entries per source,
  - entries are converted to the same internal candidate representation used by Gmail parsing,
  - normalization and dedup logic remains unchanged; only the source adapter is different.
- **Idempotency and replay:**
  - feed entries must carry a stable identifier per source (e.g. entry URL or GUID),
  - the existing idempotency rules (no duplicate vacancies) apply across all sources.

The actual feed connectors (code and schemas) are deferred until Gmail intake’s effectiveness is measured.

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

