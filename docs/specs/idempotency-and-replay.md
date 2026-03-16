# Uniqueness, Idempotency, and Replayable Source Links (TASK-034)

**Scope:** Prevent duplicate ingestion; merge canonical duplicates; allow replay from stored source.

---

## 1. Duplicate Gmail messages blocked

- **Table:** `gmail_messages`.
- **Constraint:** `gmail_message_id` is UNIQUE. The same Gmail API message id cannot be inserted twice.
- **Flow:** Persistence layer (e.g. `gmail_reader.store.persist_messages`) uses `ON CONFLICT (gmail_message_id) DO NOTHING`. So duplicate messages are blocked at insert; no duplicate rows for the same message.

---

## 2. Canonical duplicates merged

- **Dedup key:** Normalized URL (primary), then normalized title + company. See `roleforge.normalize.dedup_key` and `roleforge.dedup.group_by_dedup_key`.
- **Persistence:** When persisting grouped candidates, we **get-or-create** vacancy by `canonical_url`: if a vacancy with that URL already exists, we reuse its id and only add new `vacancy_observations`. So the same job link from different emails or digest fragments maps to one vacancy row and many observation rows.
- **Table:** `vacancy_observations` has UNIQUE `(vacancy_id, gmail_message_id, fragment_key)`. The same fragment is not linked twice; insert uses `ON CONFLICT ... DO NOTHING`.

---

## 3. Replay from stored source

- **Source of truth:** `gmail_messages` stores `body_plain`, `body_html`, and `raw_metadata` (including headers). So the full input to the parser is available for replay.
- **Replay path:** 1) Read message(s) from `gmail_messages` by `gmail_message_id` (or by date range). 2) Re-run parser (`extract_candidates`) on body and subject. 3) Re-run normalize + dedup. 4) Persist; get-or-create and observation conflict handling make the run idempotent.
- **Use case:** Fix parser or dedup logic and re-process stored messages without re-fetching from Gmail API.

---

## 4. Summary (acceptance)

- [x] **Duplicate Gmail messages are blocked:** UNIQUE on `gmail_message_id`; insert with ON CONFLICT DO NOTHING.
- [x] **Canonical duplicates are merged:** Dedup by normalized URL/title/company; get-or-create vacancy by canonical_url; one vacancy, many observations.
- [x] **Replay from stored source is possible:** Bodies and metadata in `gmail_messages`; replay = read → parse → normalize → dedup → persist.

---

*Ref: TASK-034, EPIC-07; schema/001_initial_mvp.sql; roleforge/dedup.py, roleforge/normalize.py.*
