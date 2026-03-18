# Inbox Classifier (TASK-073)

**Scope:** Deterministic rules for classifying stored Gmail messages as vacancy alerts, employer replies, or other. Feeds `gmail_messages.classified_as` (TASK-072). No AI in the rule-first path; ambiguous cases are deferred (TASK-074).

**Refs:** [v5 application lifecycle](v5-application-lifecycle.md), [Gmail intake spec](gmail-intake-spec.md), `schema/005_gmail_classified.sql`.

---

## 1. Purpose

- **Goal:** Label each stored message so the pipeline can route vacancy alerts into the existing intake path and employer replies into application-thread correlation (e.g. `employer_threads`).
- **Authority:** Classification is advisory. Operator confirmation and Telegram remain the control surface for application state; the classifier only populates a hint column and supports filtering.

---

## 2. Rule-first approach

Classification is **deterministic first**: rules based only on data we already have (headers, thread, labels, subject, body snippets). No LLM call in the core path.

### 2.1 Signals (in evaluation order)

| Signal | Source | Use |
|--------|--------|-----|
| **Thread** | `raw_metadata.threadId` | If the thread is already linked to an application (via `employer_threads.gmail_thread_id`), new messages in that thread are strong candidates for `employer_reply`. |
| **Label** | `raw_metadata.labelIds` | Messages under the configured **intake label** are typically vacancy-related. If the message has the intake label and no prior application thread, treat as `vacancy_alert` candidate. |
| **Subject** | Headers (Subject) | Keywords: `Re:`, `Fwd:`, “interview”, “offer”, “next step”, “thank you for applying”, “we’d like to invite” → bias toward `employer_reply`. Job-board or digest-like subject patterns → `vacancy_alert`. |
| **Domain / sender** | From/Reply-To headers | Compare sender domain to known vacancy sources (e.g. job boards, no-reply domains) vs. company domains from existing vacancies or applications. Company-domain reply in a thread → `employer_reply`. |
| **Recency and thread length** | `received_at`, thread message count | Single-message thread with intake label → `vacancy_alert`. Thread with multiple messages and reply-style subject → `employer_reply` candidate. |

### 2.2 Rule order and outcome

1. **Thread linked to application:** If `threadId` exists in `employer_threads.gmail_thread_id`, set `classified_as = 'employer_reply'` (no further rules).
2. **Intake label only, single-message thread:** Message has intake label and thread has no other stored messages in our DB → `vacancy_alert`.
3. **Subject/From heuristics:** If subject contains employer-reply markers (e.g. Re:, “interview”, “invite”, “thank you for applying”) and From domain is not a known bulk/no-reply sender → `employer_reply`; else if subject/body look like job alert (e.g. “new job match”, “position at”) → `vacancy_alert`.
4. **Default:** If no rule fires with sufficient confidence, leave `classified_as = NULL` or set `other`. Do not guess; ambiguous messages are handled later (e.g. AI fallback in TASK-074).

### 2.3 Confidence and ambiguity

- **High confidence:** Rule 1 (thread linked to application); rule 2 (intake label + single-message thread).
- **Medium confidence:** Rule 3 when subject/domain clearly match one pattern.
- **Low / ambiguous:** Multiple conflicting signals, or no clear pattern → do **not** set a non-null value in the first pass; leave `classified_as = NULL` and optionally store a small `classification_metadata` (e.g. `{"ambiguous": true}`) in a future extension. TASK-074 will define when to call AI for ambiguous cases.
- **Explicit contract:** The classifier must not overwrite an existing non-null `classified_as` unless we introduce a dedicated “reclassify” mode. First write wins for the deterministic path so replay and backfills stay idempotent.

---

## 3. Replay and idempotency

- **When classification runs:** After messages are stored in `gmail_messages`. A separate job or step (TASK-076) can run over stored messages and set `classified_as`. Replay (reprocess from `gmail_messages`) does **not** depend on `classified_as`; the replay path only needs `gmail_message_id`, `raw_metadata`, `body_plain`, `body_html` (see `roleforge/replay.py`). So adding `classified_as` does not break replay.
- **Backfill:** Existing rows with `classified_as = NULL` can be updated by the classifier job when it runs. New inserts from Gmail poll do not set `classified_as`; the classifier job fills it later.
- **Idempotency:** For a given message, the deterministic classifier should produce the same result on every run. Re-running the classifier on the same message must not flip the value unless the inputs change (e.g. a new `employer_threads` row linking the thread).

---

## 4. Output and schema

- **Column:** `gmail_messages.classified_as` — one of `vacancy_alert`, `employer_reply`, `other`, or `NULL`.
- **When to set `other`:** When we explicitly decide “not vacancy, not employer reply” (e.g. newsletter, marketing). Prefer `NULL` when undecided so that a later AI or manual pass can set a real value.
- **Indexing:** An index on `(classified_as)` is optional and can be added when the classifier job and queries are implemented; not required for the migration in TASK-072.

---

## 5. Implementation tasks (after this spec)

- **TASK-074:** Define when to call AI for ambiguous emails and how to merge AI result with `classified_as`.
- **TASK-075:** Implement the classifier module (deterministic rules only).
- **TASK-076:** Run classification as a job over stored messages and set `classified_as`.

---

## 6. Summary

| Item | Decision |
|------|----------|
| Approach | Rule-first; no AI in core path |
| Confidence | High (thread/label) → set; ambiguous → leave NULL or `other` |
| Replay | Safe; replay does not use `classified_as` |
| Idempotency | Same inputs → same output; no overwrite of existing non-null unless reclassify mode |
