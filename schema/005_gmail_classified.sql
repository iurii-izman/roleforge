-- TASK-072: Add classified_as to gmail_messages for inbox classification (v5).
-- Nullable: NULL = not yet classified; preserves replay and existing intake.
-- Apply after 004_application_lifecycle.sql.

ALTER TABLE gmail_messages
  ADD COLUMN IF NOT EXISTS classified_as TEXT
  CHECK (classified_as IS NULL OR classified_as IN (
    'vacancy_alert',   -- job/vacancy notification (intake path)
    'employer_reply',  -- reply from employer (application thread)
    'other'            -- noise, spam, or unclassified
  ));

COMMENT ON COLUMN gmail_messages.classified_as IS
  'Inbox classification: vacancy_alert (job alert), employer_reply (employer response), other (noise/unclassified). NULL until classified.';
