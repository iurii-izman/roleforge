# RoleForge schema

Minimal Postgres MVP schema (TASK-032). Postgres is the only source of truth.

## Tables

| Table                 | Purpose |
|-----------------------|---------|
| `profiles`            | Search profiles (filters, weights, threshold) |
| `gmail_messages`      | Raw Gmail payload; idempotency by `gmail_message_id` |
| `vacancies`           | Normalized vacancy records (after parse + dedup) |
| `vacancy_observations`| Links vacancy to source message fragments |
| `profile_matches`     | Score and review state per (profile, vacancy) |
| `telegram_deliveries` | Digest and queue sends for audit |
| `review_actions`      | User actions (open, shortlist, ignore, applied, etc.) |
| `job_runs`            | Polling, digest, queue, replay run outcomes |

## Applying

Run migrations in order against your Postgres database. No migration framework in MVP; apply manually or via a simple script.

```bash
psql "$DATABASE_URL" -f schema/001_initial_mvp.sql
psql "$DATABASE_URL" -f schema/002_feed_observations.sql   # for v3.1 feed intake
psql "$DATABASE_URL" -f schema/003_ai_metadata.sql         # for v4 AI enrichment
```

## State transitions

Review states for `profile_matches.state`: see [State transitions spec](../docs/specs/state-transitions.md) (TASK-033).

## Runtime requirements and backups (EPIC-09)

- **Version**: Postgres ≥ 13; recommended ≥ 15 to match common managed offerings.
- **Topology (MVP)**: single primary instance, one database `roleforge`, UTC timezone, UTF8 encoding.
- **Backups**:
  - Automated daily backups enabled.
  - Retention at least 7 days (14 preferred).
  - Point-in-time recovery (PITR) enabled if the managed provider supports it; otherwise rely on snapshots.
- **Connection string**:
  - Local development: see `docs/bootstrap-access.md` for Podman-based Postgres and the `db` / `url` keyring entry.
  - Hosted runtime: `DATABASE_URL` environment variable (injected from the hosting provider’s secret store).

