# State Transitions and Source-of-Truth Boundaries (TASK-033)

**Status:** Draft for implementation  
**Scope:** RoleForge MVP — review states and Postgres-only boundaries.

---

## 1. Review states (profile_matches.state)

A **profile match** is one (profile, vacancy) pair with a score. Its `state` drives the review queue and lifecycle.

| State           | Meaning |
|-----------------|--------|
| `new`           | Match created; not yet shown in queue or acted on. Default for new matches. |
| `shortlisted`   | User shortlisted this vacancy for this profile. |
| `review_later`  | User deferred review (e.g. "Later"). |
| `ignored`       | User chose to ignore this match; no further queue exposure. |
| `applied`       | User marked as applied; no further queue exposure. |

**Rules:**

- Only one state per profile match; no secondary state store. Postgres is the source of truth.
- Transitions are driven by **review actions** (see below). Each action may update `profile_matches.state` and append a row to `review_actions`.
- Queue ordering uses `review_rank` and filters out `ignored` and `applied` for normal queue flow.
- `new` → any other state is valid. `shortlisted` / `review_later` can move to `ignored` or `applied`. Once `ignored` or `applied`, the match is considered terminal for the queue (no automatic transition back in MVP).

---

## 2. Review actions (review_actions.action)

User actions that update state and are persisted in `review_actions`:

| Action         | Typical effect on state |
|----------------|--------------------------|
| `open`         | User opened link; state may stay `new` or move to `shortlisted` / `review_later` depending on product rules. |
| `shortlist`    | Set state to `shortlisted`. |
| `review_later` | Set state to `review_later`. |
| `ignore`       | Set state to `ignored`. |
| `applied`      | Set state to `applied`. |
| `next`         | Navigate to next item; no state change by itself (optional: record that user saw this item). |

---

## 3. Source-of-truth boundaries

- **MVP has no secondary hub.** All message metadata, vacancies, matches, deliveries, and review state live only in Postgres. No duplicate state in Telegram, Gmail, or an external queue system.
- **Idempotency:** Gmail intake is idempotent by `gmail_message_id`. Duplicate message IDs are not inserted into `gmail_messages`.
- **Replay:** Stored `gmail_messages` (raw payload) allow reprocessing without re-reading Gmail. Replay entrypoints (TASK-038) use Postgres as the source for message and run data.

---

## 4. Summary (acceptance checklist)

- [x] **new, shortlisted, review_later, ignored, applied** are defined and used in schema.
- [x] **No secondary hub in MVP:** Postgres-only for messages, vacancies, matches, deliveries, and review state.
- [x] State transitions are driven by review actions and recorded in `review_actions`.

---

*Ref: TASK-033, EPIC-07 Postgres Audit Trail and State.*
