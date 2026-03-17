# v6 Market Monitoring (TASK-084–TASK-092)

**Scope:** Add active market monitoring starting from HH.ru public vacancy search while preserving the same normalized vacancy pipeline used by Gmail and feeds. This is a post-v4, post-scoring extension; monitor results are only useful once scoring is differentiating meaningfully.

**Refs:** docs/research-v4-plus.md §4.3, §6.7; [v3 feeds and connectors](v3-feeds-and-connectors.md); [Job runs logging](job-runs-logging.md); [Cost governance](cost-governance.md).

---

## 1. Decision summary

- **First source:** HH.ru public API.
- **First adapter:** `roleforge.monitors.hh.fetch_candidates(...)`.
- **Registry:** file-driven `config/monitors.yaml`.
- **Kill-switch:** `MONITOR_INTAKE_ENABLED` (default false).
- **Pipeline:** monitor results feed the same normalize/dedup/persist path as Gmail and feeds.
- **No new tables:** reuse `vacancy_observations.feed_source_key` with prefix `monitor:hh:{vacancy_id}`.

---

## 2. HH.ru source contract

### 2.1 Public search endpoint

Use the public vacancy search endpoint:

```text
GET https://api.hh.ru/vacancies
```

**Input parameters (minimal MVP set):**

- `text` - search keywords (e.g. `python backend`)
- `area` - region id
- `schedule` - e.g. `remote`
- `per_page` - capped to 100
- `page` - pagination index
- `date_from` - optional lower bound for incremental polling

### 2.2 Response fields used

The adapter reads the vacancy payload and maps these fields:

- `id` - stable external vacancy id
- `name` - vacancy title
- `employer.name` - company name
- `area.name` - location
- `alternate_url` - canonical vacancy URL
- `salary.from`, `salary.to`, `salary.currency`, `salary.gross` - structured salary, folded into `salary_raw`
- `published_at` - included in raw snippet for operator context

### 2.3 Output contract

The adapter emits the same candidate shape as Gmail/feed candidates:

- `canonical_url`
- `company`
- `title`
- `location`
- `salary_raw`
- `parse_confidence`
- `fragment_key`
- `feed_source_key` (monitor prefix)
- `raw_snippet`

`parse_confidence` is high because the source is structured; the adapter uses `1.0` by default.

---

## 3. Registry contract

`config/monitors.yaml` contains a `monitors:` list.

Each monitor entry supports:

| Field | Type | Notes |
| --- | --- | --- |
| `id` | string | stable registry id |
| `name` | string | display name |
| `type` | string | `hh_api` in v6 |
| `enabled` | boolean | per-monitor enable flag |
| `poll_interval_minutes` | number | registry metadata for cadence/orchestration |
| `params` | object | source-specific search params |

**Global kill-switch:** if `MONITOR_INTAKE_ENABLED` is false, `monitor_poll` no-ops.

---

## 4. Job behavior

### 4.1 Entry point

- `python -m roleforge.jobs.monitor_poll`

### 4.2 What the job does

- Reads the registry
- Filters to enabled monitors when the global kill-switch is on
- Fetches HH.ru candidates
- Dedups and persists via the shared vacancy pipeline
- Writes a `job_runs` row for the sweep, including per-monitor summaries

### 4.3 Failure behavior

- A failure in one monitor does not block other monitors in the same sweep.
- If every enabled monitor fails, the job run is marked failure.
- Monitor errors are summarized in `job_runs.summary.monitor_results`.

---

## 5. Legal and operational guardrails

- HH.ru search is used for personal market monitoring only.
- Do not redistribute HH.ru data outside the operator’s local Postgres.
- Respect HH.ru terms of service and rate limits.
- Identify the application with a clear User-Agent string.
- Use conservative paging and backoff; do not crawl aggressively.

The repository’s research found the API registration and usage rules in the official HH.ru developer agreement and API docs. The docs also expose `alternate_url` and structured `salary` fields for vacancies.

---

## 6. Implementation path

| Task | Notes |
| --- | --- |
| TASK-084 | HH.ru API / ToS / field mapping research (this spec) |
| TASK-085 | Monitor registry contract (`config/monitors.yaml`, `roleforge/monitor_registry.py`) |
| TASK-086 | HH.ru adapter (`roleforge/monitors/hh.py`) |
| TASK-087 | Monitor poll job (`roleforge/jobs/monitor_poll.py`) |
| TASK-088 | Global kill-switch and per-monitor enable flag |
| TASK-091 | Document ToS / rate limit policy in `docs/architecture.md` |
| TASK-092 | Publish the market monitoring spec |

---

*Ref: TASK-084–TASK-092, EPIC-18; docs/research-v4-plus.md §4.3.*
