# Scheduler Decision Record (TASK-068, EPIC-16)

**Scope:** Choose the lightest way to coordinate approved job entrypoints from one place without adding queue infrastructure or a dedicated scheduler service.

**Result:** Use a small in-process scheduler in `roleforge/scheduler.py` backed by the Python standard library. Each job keeps its own `job_runs` logging; the scheduler only coordinates cadence and emits structured stdout logs.

---

## 1. Options considered

| Option | Pros | Cons | Decision |
| --- | --- | --- | --- |
| **APScheduler** | Rich trigger model, misfire handling, job stores | More moving parts than MVP needs, extra dependency, more operational surface | Rejected for MVP |
| **`schedule` package** | Small and easy to read | Still adds a dependency, fewer controls than needed, no persistence | Rejected in favor of stdlib |
| **Postgres cron table** | Durable, visible in DB, multi-worker friendly | Adds schema, locking, and coordination complexity that the single-operator MVP does not need | Rejected for MVP |
| **Custom in-process loop** | No extra dependency, easy to inspect, fits single-process MVP | No persistence across restarts; relies on process uptime | **Chosen** |

The chosen path is the simplest option that still keeps job orchestration understandable.

---

## 2. Scheduler shape

- **Entry point:** `python -m roleforge.scheduler`
- **Implementation:** `roleforge/scheduler.py`
- **Scheduling model:** in-process loop with per-job cadence tracking
- **State source of truth:** Postgres remains the source of truth for business data; scheduler state lives only in memory
- **Visibility:** underlying jobs write to `job_runs`; scheduler emits structured stdout logs only

### Scheduled jobs

| Job | Default cadence | Startup behavior | Notes |
| --- | --- | --- | --- |
| `gmail_poll` | every 15 minutes | run on startup | Poll Gmail label, persist new messages |
| `feed_poll` | every 60 minutes | run on startup | No-op when feed intake is disabled |
| `alert` | every 5 minutes | run on startup | Optional; idempotent by delivery log |
| `batch` | every 15 minutes | run on startup | Optional; idempotent by delivery log |
| `digest` | daily at `DIGEST_AT_UTC` (default `09:00` UTC) | do not run on startup | Primary low-noise digest path |

`queue` remains on-demand and is not part of the scheduler loop.

---

## 3. Failure behavior

- One job failure must not stop the loop or block other jobs.
- Each job keeps its own retry/fallback policy inside the job module.
- After a run attempt, the scheduler advances that job to its next cadence.
- If the process restarts, only in-memory cadence state is lost; the underlying jobs remain idempotent where needed.

---

## 4. Path to implementation

| Task | Notes |
| --- | --- |
| TASK-068 | Research and decision record (this file) |
| TASK-069 | Implement `roleforge/scheduler.py` |
| TASK-070 | Document scheduler setup in `docs/architecture.md`, `README.md`, and runtime docs |

---

*Ref: TASK-068, EPIC-16; docs/research-v4-plus.md §6.2; docs/specs/deployment-runtime.md.*
