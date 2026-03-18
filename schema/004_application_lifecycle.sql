-- v5 application lifecycle (TASK-071 / TASK-083).
-- Additive only: same Postgres instance, no separate service.
-- Migration 004 follows 003_ai_metadata.sql.

CREATE TABLE IF NOT EXISTS applications (
  id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  profile_match_id UUID NOT NULL REFERENCES profile_matches (id) ON DELETE CASCADE,
  vacancy_id       UUID NOT NULL REFERENCES vacancies (id) ON DELETE CASCADE,
  status           TEXT NOT NULL DEFAULT 'applied'
                   CHECK (status IN (
                     'applied',
                     'hr_pinged',
                     'interview_scheduled',
                     'offer',
                     'rejected',
                     'ghosted',
                     'accepted',
                     'declined'
                   )),
  applied_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  notes            JSONB,
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (profile_match_id)
);

CREATE TABLE IF NOT EXISTS employer_threads (
  id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  application_id   UUID NOT NULL REFERENCES applications (id) ON DELETE CASCADE,
  gmail_thread_id  TEXT,
  company_domain   TEXT,
  last_message_at  TIMESTAMPTZ,
  classification   JSONB,
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (gmail_thread_id)
);

CREATE TABLE IF NOT EXISTS interview_events (
  id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  application_id   UUID NOT NULL REFERENCES applications (id) ON DELETE CASCADE,
  event_type       TEXT NOT NULL
                   CHECK (event_type IN (
                     'hr_call',
                     'technical',
                     'panel',
                     'offer',
                     'assessment',
                     'reference',
                     'other'
                   )),
  scheduled_at     TIMESTAMPTZ,
  notes            JSONB,
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_applications_profile_match ON applications (profile_match_id);
CREATE INDEX IF NOT EXISTS idx_applications_status ON applications (status);
CREATE INDEX IF NOT EXISTS idx_employer_threads_application ON employer_threads (application_id);
CREATE INDEX IF NOT EXISTS idx_employer_threads_gmail ON employer_threads (gmail_thread_id);
CREATE INDEX IF NOT EXISTS idx_interview_events_application ON interview_events (application_id);
CREATE INDEX IF NOT EXISTS idx_interview_events_scheduled_at ON interview_events (scheduled_at);
