# MVP Verification Guide

This guide matches the current repository state. It avoids REPL-only steps and uses the job/script entrypoints that exist in the repo today.

## Where to run commands

- **Host shell**: use for `podman ...`, keyring checks, editing `.env`, and all repo commands below.
- **Python environment**: activate the repo-local virtualenv before any `python ...` command:

```bash
cd /var/home/user/Projects/roleforge
source /var/home/user/Projects/roleforge/.venv/bin/activate
```

- **Working directory**: `/var/home/user/Projects/roleforge`
- **Toolbox**: optional, not required for the current MVP verification flow.

## 0. Readiness

### 0.1. Postgres container

Check container state:

```bash
cd /var/home/user/Projects/roleforge
podman ps -a --format '{{.Names}}\t{{.Status}}'
```

If `roleforge-pg` is not running:

```bash
cd /var/home/user/Projects/roleforge
podman start roleforge-pg
```

If the container does not exist yet:

```bash
cd /var/home/user/Projects/roleforge
podman run -d \
  --name roleforge-pg \
  -e POSTGRES_USER=roleforge \
  -e POSTGRES_PASSWORD=roleforge \
  -e POSTGRES_DB=roleforge \
  -p 5432:5432 \
  -v roleforge-pgdata:/var/lib/postgresql/data \
  docker.io/library/postgres:16
```

Apply schema:

```bash
cd /var/home/user/Projects/roleforge
podman exec -i roleforge-pg psql -U roleforge -d roleforge < /var/home/user/Projects/roleforge/schema/001_initial_mvp.sql
```

Optional (v3.1 feed intake): apply feed observations migration so feed_poll can persist feed-sourced vacancies:

```bash
podman exec -i roleforge-pg psql -U roleforge -d roleforge < /var/home/user/Projects/roleforge/schema/002_feed_observations.sql
```

### 0.2. Keyring

Check the current secret presence:

```bash
cd /var/home/user/Projects/roleforge
for d in 'google client_id' 'google client_secret' 'google refresh_token' 'telegram bot_token' 'openai api_key' 'anthropic api_key' 'db url'; do
  set -- $d
  printf '%s/%s=' "$1" "$2"
  /var/home/user/Projects/roleforge/scripts/roleforge-keyring.sh exists "$1" "$2"
done
```

Expected: `yes` for the secrets you actively use.

### 0.3. `.env`

`.env` is optional for secrets, but useful for non-secret config such as:

- `GMAIL_INTAKE_LABEL`
- `TELEGRAM_CHAT_ID`
- `TELEGRAM_ADMIN_CHAT_ID`
- `PRIMARY_AI_PROVIDER`

Bootstrap:

```bash
cd /var/home/user/Projects/roleforge
cp /var/home/user/Projects/roleforge/.env.example /var/home/user/Projects/roleforge/.env
```

## 1. Install Python dependencies

```bash
cd /var/home/user/Projects/roleforge
python -m pip install -r /var/home/user/Projects/roleforge/requirements.txt
```

## 2. Ensure the default MVP profile exists

Current repo state does not seed profiles automatically. Create `default_mvp` once:

```bash
cd /var/home/user/Projects/roleforge
python /var/home/user/Projects/roleforge/scripts/seed_default_profile.py
```

Expected: JSON with `name: "default_mvp"`.

**v2 optional:** To use multiple profiles (`primary_search`, `stretch_geo`), seed v2 presets and re-run scoring:

```bash
python /var/home/user/Projects/roleforge/scripts/seed_profiles_v2.py
python /var/home/user/Projects/roleforge/scripts/run_scoring_once.py
```

Analytics (e.g. last 7 days):

```bash
python /var/home/user/Projects/roleforge/scripts/report_profile_stats.py --days 7
```

## 3. Gmail -> Postgres

Run one Gmail polling cycle:

```bash
cd /var/home/user/Projects/roleforge
python -m roleforge.jobs.gmail_poll
```

Optional explicit label override:

```bash
cd /var/home/user/Projects/roleforge
python -m roleforge.jobs.gmail_poll --label 'JobAlerts/RoleForge'
```

Verify stored raw messages and job_runs:

```bash
cd /var/home/user/Projects/roleforge
podman exec roleforge-pg psql -U roleforge -d roleforge -c "SELECT COUNT(*) AS gmail_messages FROM gmail_messages;"
```

```bash
cd /var/home/user/Projects/roleforge
podman exec roleforge-pg psql -U roleforge -d roleforge -c "SELECT job_type, status, started_at, finished_at, summary FROM job_runs ORDER BY started_at DESC LIMIT 5;"
```

Expected:

- `gmail_messages > 0`
- latest `job_runs.job_type = 'gmail_poll'`
- latest `job_runs.status = 'success'`

If `messages_fetched = 0`, the job itself is healthy; it means there are currently no emails under the configured intake label. For a real E2E run, add the `roleforge-intake` label to one or more job emails in Gmail and rerun the poll.

## 4. Replay stored messages into vacancies

Replay everything currently stored:

```bash
cd /var/home/user/Projects/roleforge
python -m roleforge.jobs.replay --start-date 2026-01-01
```

Or replay one message:

```bash
cd /var/home/user/Projects/roleforge
python -m roleforge.jobs.replay --gmail-message-id YOUR_GMAIL_MESSAGE_ID
```

Verify normalized output:

```bash
cd /var/home/user/Projects/roleforge
podman exec roleforge-pg psql -U roleforge -d roleforge -c "SELECT COUNT(*) AS vacancies FROM vacancies;"
```

```bash
cd /var/home/user/Projects/roleforge
podman exec roleforge-pg psql -U roleforge -d roleforge -c "SELECT COUNT(*) AS observations FROM vacancy_observations;"
```

Expected:

- `vacancies > 0`
- `vacancy_observations > 0`

## 5. Score vacancies into `profile_matches`

```bash
cd /var/home/user/Projects/roleforge
python /var/home/user/Projects/roleforge/scripts/run_scoring_once.py
```

Verify:

```bash
cd /var/home/user/Projects/roleforge
podman exec roleforge-pg psql -U roleforge -d roleforge -c "SELECT state, COUNT(*) FROM profile_matches GROUP BY state ORDER BY state;"
```

```bash
cd /var/home/user/Projects/roleforge
podman exec roleforge-pg psql -U roleforge -d roleforge -c "SELECT p.name, COUNT(*) FROM profile_matches pm JOIN profiles p ON p.id = pm.profile_id GROUP BY p.name ORDER BY p.name;"
```

Expected: at least one `new` match for `default_mvp` (or for `primary_search`/`stretch_geo` if you ran `seed_profiles_v2.py`).

## 6. Telegram digest

Dry-run first:

```bash
cd /var/home/user/Projects/roleforge
python -m roleforge.jobs.digest --dry-run
```

Expected: text preview with `RoleForge digest` and `Open queue: /queue`.

Real send:

```bash
cd /var/home/user/Projects/roleforge
python -m roleforge.jobs.digest
```

Verify:

```bash
cd /var/home/user/Projects/roleforge
podman exec roleforge-pg psql -U roleforge -d roleforge -c "SELECT delivery_type, sent_at, payload->>'chat_id' AS chat_id FROM telegram_deliveries ORDER BY sent_at DESC LIMIT 5;"
```

Expected:

- a Telegram message arrived in `TELEGRAM_CHAT_ID`
- a `telegram_deliveries` row exists with `delivery_type = 'digest'`
- a `job_runs` row exists with `job_type = 'digest'`

## 6.1 Queue card preview

Preview the next queue item without sending:

```bash
cd /var/home/user/Projects/roleforge
python -m roleforge.jobs.queue --dry-run --profile-name default_mvp
```

Expected:

- if matches exist, you see one formatted vacancy card
- if the queue is empty, the JSON summary returns `"queue_empty": true`

## 7. TASK-021: real-message parser verification

List candidate message IDs:

```bash
cd /var/home/user/Projects/roleforge
podman exec roleforge-pg psql -U roleforge -d roleforge -c "SELECT gmail_message_id, received_at FROM gmail_messages ORDER BY received_at DESC NULLS LAST LIMIT 10;"
```

Inspect one message plus extracted candidates:

```bash
cd /var/home/user/Projects/roleforge
python /var/home/user/Projects/roleforge/scripts/inspect_gmail_message.py YOUR_GMAIL_MESSAGE_ID
```

Use this for 5-10 representative real emails and note:

- expected vacancy count vs extracted count,
- missing `title` / `company` / `location`,
- digest emails where boundaries are wrong,
- HTML-heavy templates that degrade extraction.

`TASK-021` is human-complete when you have a short list of concrete parser gaps from real mail.

## 8. TASK-035: schema/operator query verification

Run the main operator queries directly against Postgres.

New matches in the last 7 days:

```bash
cd /var/home/user/Projects/roleforge
podman exec roleforge-pg psql -U roleforge -d roleforge -c "SELECT COUNT(*) FROM profile_matches WHERE created_at >= now() - interval '7 days';"
```

High-score applied matches in the last 7 days:

```bash
cd /var/home/user/Projects/roleforge
podman exec roleforge-pg psql -U roleforge -d roleforge -c "SELECT COUNT(*) FROM profile_matches WHERE state = 'applied' AND score >= 0.6 AND updated_at >= now() - interval '7 days';"
```

Ignored matches in the last 30 days:

```bash
cd /var/home/user/Projects/roleforge
podman exec roleforge-pg psql -U roleforge -d roleforge -c "SELECT COUNT(*) FROM profile_matches WHERE state = 'ignored' AND updated_at >= now() - interval '30 days';"
```

Latest job outcomes:

```bash
cd /var/home/user/Projects/roleforge
podman exec roleforge-pg psql -U roleforge -d roleforge -c "SELECT job_type, status, started_at, finished_at, summary FROM job_runs ORDER BY started_at DESC LIMIT 20;"
```

If a real operator question still feels awkward to answer in SQL, record it as a schema gap.

## 9. Current repo status that affects verification

Already implemented:

- Gmail reader, raw message persistence, retry policy, job_runs helpers
- deterministic parser, normalization, dedup, replay helpers
- scoring engine, review ordering, digest formatter, queue state transitions
- telegram delivery log and review action persistence
- runtime entrypoints for `gmail_poll`, `replay`, and `digest`
- runtime entrypoints for `gmail_poll`, `replay`, `digest`, and queue-card preview
- helper scripts for `default_mvp` profile, scoring, and message inspection

Still human/manual:

- choosing the real Gmail intake label
- confirming real Telegram chat IDs
- reviewing parser quality against real mail samples (`TASK-021`)
- deciding whether any schema gaps found during operator-query review (`TASK-035`) should change MVP schema or move to v2
