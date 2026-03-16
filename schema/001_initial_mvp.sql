-- RoleForge MVP schema (TASK-032)
-- Postgres 13+. All state is Postgres-only; no secondary hub in MVP.
-- Apply in order: 001_initial_mvp.sql

-- Profiles: multiple search profiles with filters and weights (one shared formula).
CREATE TABLE IF NOT EXISTS profiles (
  id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name       TEXT NOT NULL,
  config     JSONB NOT NULL DEFAULT '{}',  -- hard filters, weights, threshold
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Raw Gmail messages: source payload for audit and replay (gmail_reader output).
CREATE TABLE IF NOT EXISTS gmail_messages (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  gmail_message_id TEXT NOT NULL UNIQUE,  -- Gmail API message id (idempotency key)
  raw_metadata    JSONB,                 -- headers, labelIds, threadId, etc.
  body_html       TEXT,
  body_plain      TEXT,
  received_at     TIMESTAMPTZ,            -- from internalDate or Date header
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_gmail_messages_received_at ON gmail_messages (received_at);

-- Normalized vacancies (after parsing and dedup).
CREATE TABLE IF NOT EXISTS vacancies (
  id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  canonical_url    TEXT,
  company          TEXT,
  title            TEXT,
  location         TEXT,
  salary_raw       TEXT,
  parse_confidence NUMERIC(5,4),         -- 0..1
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Link vacancy to source fragments (one vacancy, many observations from messages/digests).
CREATE TABLE IF NOT EXISTS vacancy_observations (
  id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  vacancy_id       UUID NOT NULL REFERENCES vacancies (id) ON DELETE CASCADE,
  gmail_message_id TEXT NOT NULL REFERENCES gmail_messages (gmail_message_id) ON DELETE CASCADE,
  fragment_key     TEXT NOT NULL,         -- e.g. digest position or part index
  raw_snippet      TEXT,
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (vacancy_id, gmail_message_id, fragment_key)
);

CREATE INDEX IF NOT EXISTS idx_vacancy_observations_vacancy ON vacancy_observations (vacancy_id);

-- Profile match: one row per (profile, vacancy). State drives review queue.
CREATE TABLE IF NOT EXISTS profile_matches (
  id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  profile_id     UUID NOT NULL REFERENCES profiles (id) ON DELETE CASCADE,
  vacancy_id     UUID NOT NULL REFERENCES vacancies (id) ON DELETE CASCADE,
  score          NUMERIC NOT NULL,
  state          TEXT NOT NULL DEFAULT 'new' CHECK (state IN ('new', 'shortlisted', 'review_later', 'ignored', 'applied')),
  explainability JSONB,
  review_rank    INT,                    -- deterministic order in queue
  created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (profile_id, vacancy_id)
);

CREATE INDEX IF NOT EXISTS idx_profile_matches_profile_state ON profile_matches (profile_id, state);
CREATE INDEX IF NOT EXISTS idx_profile_matches_review_rank ON profile_matches (profile_id, review_rank) WHERE state != 'ignored' AND state != 'applied';

-- Telegram: digest and queue sends for audit.
CREATE TABLE IF NOT EXISTS telegram_deliveries (
  id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  delivery_type TEXT NOT NULL,           -- 'digest' | 'queue_card'
  payload      JSONB,
  sent_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Review actions: user actions on queue (Open, Shortlist, Later, Ignore, Applied, Next).
CREATE TABLE IF NOT EXISTS review_actions (
  id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  profile_match_id UUID NOT NULL REFERENCES profile_matches (id) ON DELETE CASCADE,
  action           TEXT NOT NULL CHECK (action IN ('open', 'shortlist', 'review_later', 'ignore', 'applied', 'next')),
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_review_actions_profile_match ON review_actions (profile_match_id);

-- Job runs: polling, digest, queue, replay outcomes.
CREATE TABLE IF NOT EXISTS job_runs (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  job_type    TEXT NOT NULL,             -- 'gmail_poll' | 'digest' | 'queue' | 'replay'
  started_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  finished_at TIMESTAMPTZ,
  status      TEXT NOT NULL DEFAULT 'running' CHECK (status IN ('running', 'success', 'failure')),
  summary     JSONB
);

CREATE INDEX IF NOT EXISTS idx_job_runs_type_started ON job_runs (job_type, started_at DESC);
