# RoleForge

RoleForge is an AI-assisted job intelligence pipeline focused on Gmail-first intake, deterministic parsing and scoring, Postgres-first state, and low-noise Telegram delivery.

## Current Direction

- MVP intake source: Gmail only
- System of record: Postgres
- Delivery UX: Telegram digest plus review queue
- AI usage: one primary provider in MVP, narrow ROI-only usage
- Backlog canon: Linear project `RoleForge MVP`
- GitHub Projects: execution mirror for repo-linked work
- Local secret storage: keyring-first under `service=roleforge`

## Repository Layout

- `.github/` GitHub ownership and issue templates
- `docs/` product, architecture, roadmap, backlog, and specs (e.g. `docs/specs/gmail-intake-spec.md`)
- `docs/backlog/` canonical backlog seed and placement guides
- `docs/prompts/` reusable operating prompts for external agents such as Cursor Autopilot
- `roleforge/` Python package (`gmail_reader` for Gmail API intake; `parser` for deterministic vacancy extraction)
- `schema/` Postgres MVP schema and migrations (see `schema/README.md`)
- `scripts/` helper scripts for keyring and GitHub backlog seeding
- `tests/` unit tests and fixtures (e.g. `tests/test_gmail_reader.py`)
- `AGENTS.md` repository-specific guidance for AI coding agents
- `.env.example` bootstrap-only local environment template
- `sonar-project.properties` SonarQube/SonarCloud config; [Code quality and trackers](docs/code-quality-and-trackers.md)

## Development

- **Gmail intake:** See [Gmail intake spec](docs/specs/gmail-intake-spec.md). Reader: `roleforge.gmail_reader.GmailReader`. Persistence: `roleforge.gmail_reader.store.persist_messages`. Retry: `roleforge.gmail_reader.retry.with_retry`; [gmail-retry-policy.md](docs/specs/gmail-retry-policy.md). Run logging: `roleforge.job_runs.log_job_start` / `log_job_finish`.
- **Parser:** [Parser behavior](docs/specs/parser-behavior.md), [Vacancy schema](docs/specs/vacancy-schema.md). Extraction: `roleforge.parser.extract_candidates`; validation: `roleforge.parser.validate_candidate`. Deterministic, no LLM.
- **Normalize & dedup:** `roleforge.normalize`, `roleforge.dedup`. [Idempotency and replay](docs/specs/idempotency-and-replay.md).
- **Profiles & scoring:** [Profile schema](docs/specs/profile-schema.md), [Scoring spec](docs/specs/scoring-spec.md). `roleforge.scoring`, `roleforge.review_ordering` (assign_review_ranks, update_review_ranks_for_profile). Explainability includes positive_factors, negative_factors. v2 presets and queue/digest refinements: [v2 profiles, queue, and analytics](docs/specs/v2-profiles-and-queue.md).
- **Telegram:** [Telegram interaction spec](docs/specs/telegram-interaction.md). `roleforge.digest`, `roleforge.queue`, `roleforge.delivery_log` (log_telegram_delivery for digest/queue_card). Review actions in queue.apply_review_action. Digest and queue UX in v2 include score bands, queue position, and short “why in queue” explanations.
- **Job runs:** [Job runs logging](docs/specs/job-runs-logging.md). `roleforge.job_runs`: log_job_start, log_job_finish. Every scheduled job records start/finish and summary.
- **Retry:** [Retry and fallback policy](docs/specs/retry-and-fallback-policy.md). Gmail: `roleforge.gmail_reader.retry`. Telegram/AI: `roleforge.retry` (generic with_retry, is_transient_telegram/ai, is_permanent_telegram/ai).
- **Replay:** `roleforge.replay`: replay_one_message(conn, gmail_message_id), replay_date_window(conn, start_date, end_date) — read from gmail_messages, parse, dedup, job_runs logged.
- **Feed intake (v3.1):** [v3 feeds spec](docs/specs/v3-feeds-and-connectors.md). File registry: `config/feeds.yaml`. Kill-switch: `FEED_INTAKE_ENABLED` (default off). `roleforge.feed_registry`, `roleforge.feed_reader`; feed entries go through the same normalize/dedup path as Gmail; observations use `feed_source_key` in `vacancy_observations`.
- **Runtime entrypoints:** `python -m roleforge.jobs.gmail_poll`, `python -m roleforge.jobs.feed_poll`, `python -m roleforge.jobs.replay`, `python -m roleforge.jobs.digest --dry-run`, `python -m roleforge.jobs.queue --dry-run`. Helpers: `scripts/seed_default_profile.py`, `scripts/run_scoring_once.py`, `scripts/inspect_gmail_message.py`.
- **Analytics:** Minimal operator reporting via `scripts/report_profile_stats.py` (per-profile match counts, state distribution, high-score matches, `new_in_window` and `high_score_applied` when using `--days`/`--since`). v2 profile seeding: `scripts/seed_profiles_v2.py`. SQL examples: [v2 spec](docs/specs/v2-profiles-and-queue.md#ad-hoc-sql-examples).
- **Tests:** `python -m pytest tests/ -v` or `PYTHONPATH=. python -m unittest discover -s tests -p "test_*.py" -v`
- **Coverage (optional):** `pip install -r requirements-dev.txt` then `PYTHONPATH=. coverage run -m unittest discover -s tests -p "test_*.py"` and `coverage xml -o coverage.xml` for Sonar.
- **Dependencies:** `pip install -r requirements.txt` (psycopg2, Google API client for Gmail, feedparser, PyYAML for feed intake).

## MVP Verification

For the current, repo-native verification flow, see [docs/mvp-verification.md](docs/mvp-verification.md). It covers:

- local readiness checks (Podman Postgres, keyring, env),
- one Gmail -> Postgres -> replay -> scoring -> Telegram dry-run path,
- parser fixture review against real messages (TASK-021),
- schema/operator SQL checks (TASK-035).

## Bootstrap Path

Follow the ordered sequence in [Bootstrap: Access and Secrets](docs/bootstrap-access.md):

1. GitHub auth (`gh auth refresh -s project`).
2. Linear API key (keyring: `linear` / `api_key`).
3. Google Cloud project + Gmail OAuth → keyring (`google`: `client_id`, `client_secret`, `refresh_token`).
4. Telegram bot token → keyring (`telegram` / `bot_token`).
5. One primary AI provider → keyring (`openai` or `anthropic` / `api_key`).
6. Seed backlog into Linear and GitHub when access is ready.

After each secret is in the keyring, remove plaintext copies (see bootstrap doc).

## Local Secrets

- Keyring name: **roleforge** (create/use a keyring named `roleforge` in your system keyring).
- Preferred local secret namespace: `service=roleforge` via `scripts/roleforge-keyring.sh`.
- See [Bootstrap: Access and Secrets](docs/bootstrap-access.md) for gh auth, Linear token path, and keyring usage.
- `.env` is a last-resort bootstrap fallback, not the preferred long-term source.

## Backlog Seeding

- Canonical backlog source: `docs/backlog/roleforge-backlog.json`
- GitHub seeding helper: `scripts/seed_github_backlog.py`
- Linear seeding guide: `docs/backlog/linear-seeding.md`

## Notes

- Project close-out, profile calibration, and next-phase notes: [docs/manual-tasks.md](docs/manual-tasks.md).
- v3.1 adds optional RSS/Atom feed intake via file registry and kill-switch; Gmail remains the primary MVP path. No official connectors (ATS APIs, Notion, etc.) until v3.2.
- **Code quality:** SonarQube/SonarCloud config in repo; CI runs tests and coverage and can run Sonar when `SONAR_TOKEN` is set. See [docs/code-quality-and-trackers.md](docs/code-quality-and-trackers.md) for Quality Gate and tracker setup.
