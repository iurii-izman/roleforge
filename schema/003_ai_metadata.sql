-- AI enrichment storage (TASK-061 / EPIC-15).
-- Enables vacancies to store AI-generated summary and provenance in JSONB.
-- See docs/specs/ai-enrichment-contract.md.

ALTER TABLE vacancies
  ADD COLUMN IF NOT EXISTS ai_metadata JSONB;
