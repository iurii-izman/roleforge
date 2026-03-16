# Telegram Digest and Review Queue Interaction Model (TASK-027)

**Scope:** MVP Telegram behavior — digest plus pull-based queue only. No instant alert by default.

---

## 1. No instant alert default

- **MVP does not push** a Telegram message per vacancy or per match. No "new job" notification for each item.
- **Digest** is the primary delivery: one (or few) scheduled messages that summarize matches. User opens digest and chooses what to review.
- **Queue** is pull-based: user requests "next" (or opens queue) and receives one card at a time. No automatic push of each card.
- **Exceptional alerts** (e.g. critical failure, admin) are out of scope for default UX; see TASK-039 if needed later.

---

## 2. Digest flow

- **Trigger:** Scheduled (e.g. daily or configurable interval). Job runs, builds digest payload from `profile_matches` (state != 'ignored' and != 'applied'), grouped by profile.
- **Content:** Compact summary: per profile, count of new/shortlisted/review_later matches; optional top N highlights (title, company, score). Link or instruction to open queue.
- **One message per digest run** (or one per profile if we split; MVP can be one message with sections per profile). Message length bounded (e.g. Telegram limit 4096); truncate or "see N more in queue."
- **Outcome:** User sees what’s in the queue without opening each vacancy. Counts expose full queue size; highlights show high-priority subset.

---

## 3. Queue flow (pull-based)

- **Entry:** User taps link in digest or sends command (e.g. /queue) to open the review queue.
- **Next card:** Bot sends one match (vacancy + score, explainability snippet, actions: Open link, Shortlist, Later, Ignore, Applied, Next).
- **Actions:** Inline buttons or commands update `profile_matches.state` and append to `review_actions`; then bot sends next card or "queue empty."
- **Order:** Cards follow `review_rank` (ascending) for that profile; filtered by state not in (ignored, applied). Deterministic and reproducible.

---

## 4. Message outline (MVP)

| Message type | When | Content |
|--------------|------|---------|
| **Digest** | On schedule | Title "RoleForge digest". Per profile: "Profile X: N new, M shortlisted." Top 3–5 items (title, company, score). "Open queue: [link]". |
| **Queue card** | On user request (next) | One vacancy: title, company, location, score, link. Buttons: Open, Shortlist, Later, Ignore, Applied, Next. |
| **Queue empty** | After last card | "No more items in queue." |

---

## 5. Summary (acceptance)

- [x] **No instant alert default:** Digest and queue only; no per-vacancy push.
- [x] **Digest and queue flows are explicit:** Digest = scheduled summary grouped by profile; queue = pull-based, one card at a time, actions update state and advance to next.

---

*Ref: TASK-027, EPIC-06 Telegram Digest and Review Queue; TASK-028 (formatter), TASK-029 (queue cards and callbacks).*
