# Telegram Digest and Review Queue Interaction Model (TASK-027)

**Scope:** MVP Telegram behavior — digest plus pull-based queue. Optional threshold-triggered alert and micro-batch (v4). No instant alert by default.

---

## 1. Delivery modes and coexistence (digest, queue, alert, batch, application updates)

Five delivery paths can run independently; all use the same Telegram chat and `telegram_deliveries` audit log.

| Mode | Trigger | Content | When to use |
| --- | --- | --- | --- |
| **Digest** | Scheduled (e.g. daily) | Summary by profile, counts, top highlights | Primary low-noise view; default. |
| **Queue** | User request (/queue, Next) | One card at a time, actions update state | Pull-based review; no auto-push. |
| **Alert** | Job run (`python -m roleforge.jobs.alert`) | One message per high-score match (score ≥ `immediate_threshold`) | Optional near-real-time for top matches; per-profile `alert_enabled`. |
| **Batch** | Job run (`python -m roleforge.jobs.batch`) | One message per profile with mid-band matches (score in `[batch_threshold, immediate_threshold)`) | Optional middle path between alert and digest; per-profile `batch_enabled`. |
| **Application updates** | Job run (`python -m roleforge.jobs.application_notify`) | Employer reply detected / interview event created | Optional v5 lifecycle updates; disabled by default (digest-first). |

- **No instant alert by default:** Digest and queue are the baseline. Alert and batch are **opt-in per profile** via `profiles.config.delivery_mode` (see [Profile schema](profile-schema.md)).
- **Idempotency:** Alert and batch jobs only send for matches that have not already been sent as that type; sends are logged in `telegram_deliveries` with `delivery_type='alert'` or `delivery_type='batch'` and `payload.profile_match_id` (or list of ids for batch).
- **Application update notifications (v5):** Disabled by default. When enabled (`APPLICATION_NOTIFY_ENABLED=true`), the notify job sends only first-time updates and logs to `telegram_deliveries` with `delivery_type='application_update'`.
- **Admin path:** Operational failures use `delivery_type='admin_alert'` (TASK-039, TASK-103); see [Admin alert path](admin-alert-path.md).

---

## 2. No instant alert default (MVP baseline)

- **MVP does not push** a Telegram message per vacancy unless the operator enables alert or batch per profile.
- **Digest** is the primary delivery: one (or few) scheduled messages that summarize matches. User opens digest and chooses what to review.
- **Queue** is pull-based: user requests "next" (or opens queue) and receives one card at a time.
- **Threshold-triggered alert (v4):** When `delivery_mode.alert_enabled` is true, matches with score ≥ `immediate_threshold` can trigger an immediate message. Run `python -m roleforge.jobs.alert` (or `--dry-run`). Only unsent matches are eligible; logged as `delivery_type='alert'`.
- **Micro-batch (v4):** When `delivery_mode.batch_enabled` is true, matches in the band `[batch_threshold, immediate_threshold)` can be sent in a short-cadence batch. Run `python -m roleforge.jobs.batch` (or `--dry-run`). Logged as `delivery_type='batch'`.

---

## 3. Digest flow

- **Trigger:** Scheduled (e.g. daily or configurable interval). Job runs, builds digest payload from `profile_matches` (state != 'ignored' and != 'applied'), grouped by profile.
- **Content:** Compact summary: per profile, count of new/shortlisted/review_later matches; optional top N highlights (title, company, score). Link or instruction to open queue.
- **One message per digest run** (or one per profile if we split; MVP can be one message with sections per profile). Message length bounded (e.g. Telegram limit 4096); truncate or "see N more in queue."
- **Outcome:** User sees what’s in the queue without opening each vacancy. Counts expose full queue size; highlights show high-priority subset.

---

## 4. Queue flow (pull-based)

- **Entry:** User taps link in digest or sends command (e.g. /queue) to open the review queue.
- **Next card:** Bot sends one match (vacancy + score, explainability snippet, actions: Open link, Shortlist, Later, Ignore, Applied, Next).
- **Actions:** Inline buttons or commands update `profile_matches.state` and append to `review_actions`; then bot sends next card or "queue empty."
- **Order:** Cards follow `review_rank` (ascending) for that profile; filtered by state not in (ignored, applied). Deterministic and reproducible.

---

## 5. Message outline (MVP + v4)

| Message type | When | Content |
| --- | --- | --- |
| **Digest** | On schedule | Title "RoleForge digest". Per profile: "Profile X: N new, M shortlisted." Top 3–5 items (title, company, score). "Open queue: [link]". |
| **Queue card** | On user request (next) | One vacancy: title, company, location, score, link. Buttons: Open, Shortlist, Later, Ignore, Applied, Next. |
| **Queue empty** | After last card | "No more items in queue." |
| **Alert** | Alert job (alert_enabled, score ≥ immediate_threshold) | One message per match: title, company, score, profile, link. |
| **Batch** | Batch job (batch_enabled, score in [batch_threshold, immediate_threshold)) | One message per profile: "RoleForge batch (Profile X)" and list of items (title, company, score, link). |

---

## 6. Summary (acceptance)

- [x] **No instant alert default:** Digest and queue are baseline; alert and batch are opt-in per profile.
- [x] **Digest and queue flows are explicit:** Digest = scheduled summary grouped by profile; queue = pull-based, one card at a time, actions update state and advance to next.
- [x] **Alert and batch coexistence:** Alert mode and micro-batch are documented; both are low-noise and auditable via `telegram_deliveries`.

---

*Ref: TASK-027, EPIC-06 Telegram Digest and Review Queue; TASK-028 (formatter), TASK-029 (queue cards and callbacks).*
