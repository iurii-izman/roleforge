-- Feed-sourced observations (TASK-046 / EPIC-11).
-- Allows vacancy_observations to link to feed entries via feed_source_key instead of gmail_message_id.
-- No new tables; one source column must be set.

-- Allow NULL gmail_message_id when feed_source_key is set.
ALTER TABLE vacancy_observations
  ALTER COLUMN gmail_message_id DROP NOT NULL;

ALTER TABLE vacancy_observations
  ADD COLUMN IF NOT EXISTS feed_source_key TEXT;

-- Exactly one of gmail_message_id or feed_source_key must be set.
ALTER TABLE vacancy_observations
  DROP CONSTRAINT IF EXISTS vacancy_observations_source_check;

ALTER TABLE vacancy_observations
  ADD CONSTRAINT vacancy_observations_source_check
  CHECK (
    (gmail_message_id IS NOT NULL AND (feed_source_key IS NULL OR feed_source_key = ''))
    OR (feed_source_key IS NOT NULL AND feed_source_key != '' AND gmail_message_id IS NULL)
  );

-- Replace single-source unique with two partial uniques for ON CONFLICT target.
-- Constraint name may be truncated to 63 chars (vacancy_observations_vacancy_id_gmail_message_id_fragment_key_k).
ALTER TABLE vacancy_observations
  DROP CONSTRAINT IF EXISTS vacancy_observations_vacancy_id_gmail_message_id_fragment_key_key;
ALTER TABLE vacancy_observations
  DROP CONSTRAINT IF EXISTS vacancy_observations_vacancy_id_gmail_message_id_fragment_key_k;

CREATE UNIQUE INDEX IF NOT EXISTS idx_vacancy_observations_gmail_source
  ON vacancy_observations (vacancy_id, gmail_message_id, fragment_key)
  WHERE gmail_message_id IS NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS idx_vacancy_observations_feed_source
  ON vacancy_observations (vacancy_id, feed_source_key, fragment_key)
  WHERE feed_source_key IS NOT NULL AND feed_source_key != '';
