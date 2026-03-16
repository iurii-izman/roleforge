# Gmail-Only Intake Spec (MVP)

**Status:** Accepted (TASK-011 Done)  
**Scope:** RoleForge MVP — single intake path via Gmail API.  
**Out of scope in MVP:** Gmail push (watch/history), IMAP, other mailboxes.

---

## 1. Label-first behavior

- **Single intake label:** All messages to be processed by RoleForge MUST be under one Gmail label chosen for intake (e.g. `JobAlerts/RoleForge` or a user-defined name). The label name is configuration (env or keyring-backed config); default is documented but not hardcoded.
- **Query shape:** The reader uses Gmail API `messages.list` with `labelIds=[INTAKE_LABEL_ID]`. Only messages that currently have that label are considered. No whole-inbox scan.
- **Exclusions:** Messages that are in the intake label but also in Trash or Spam are excluded (Gmail API behavior: list by label does not return trashed messages when querying by label; Spam is a separate label — we do not include `SPAM` or `TRASH` in the intake label list, so effectively only INBOX + intake label or custom label space is read). Explicit rule: **do not** add `INBOX` to the list of labels if the chosen intake strategy is “label on existing mailbox”; the API call uses only the single intake label ID.
- **Folder vs label:** MVP treats the intake target as a **label**. A dedicated mailbox (separate account) can be represented as “all messages in that account under one label” if desired; the implementation still uses one `labelIds` filter. No separate “mailbox vs label” code path in MVP.

---

## 2. Polling cadence

- **Mechanism:** Polling only. The job runs on a schedule (e.g. every N minutes), calls `messages.list` for the intake label, then `messages.get` for each new message ID not yet seen (idempotency is enforced by the caller/store, e.g. Postgres).
- **Cadence:** Configurable (e.g. `GMAIL_POLL_INTERVAL_MINUTES` or equivalent). Recommended default for MVP: **15 minutes**. Minimum practical value: 1 minute (to avoid rate limits and unnecessary load). No sub-minute polling in MVP.
- **No push in MVP:** Gmail push notifications (watch/push) and History API are **not** used in MVP. No webhook endpoint for Gmail. Polling is the only trigger.

---

## 3. Whole-inbox and scope exclusions

- **No whole-inbox read:** The reader never lists or iterates over the entire mailbox. It only lists messages with the single intake label.
- **Pagination:** `messages.list` is paginated (max 500 per request). The reader follows `nextPageToken` until no more pages. All message IDs from the intake label in the current run are collected, then filtered by “already seen” (e.g. stored `gmail_message_id` set) so that only new IDs are hydrated.
- **Hydration:** Only messages that pass the “new” check get `messages.get` (format=full or metadata+body as needed). This keeps traffic and processing deterministic and minimal.

---

## 4. Configuration contract

| Source | Key / convention | Purpose |
|--------|------------------|--------|
| Keyring `google` | `client_id`, `client_secret`, `refresh_token` | OAuth for Gmail API |
| Config / env | Intake label name or ID | Single label for `messages.list`; if name is given, resolve to ID once per run or at startup |

Label resolution: Gmail API uses label IDs. If the user provides a label name (e.g. `JobAlerts/RoleForge`), the reader must resolve name → ID via `users.labels.list` and cache the ID for the run. If the user provides an ID, use it directly.

---

## 5. Idempotency and “new” messages

- **Caller responsibility:** The reader returns message IDs and, when requested, full message payloads. It does not persist. The **caller** (or a separate persistence layer) is responsible for:
  - Storing seen `gmail_message_id` values (e.g. in Postgres).
  - Passing “already seen” IDs into the reader so that only new IDs are hydrated.
- **Reader contract:** The reader accepts an optional set (or list) of “already seen” message IDs. It returns:
  - All message IDs from the intake label (current page or full list),
  - A subset “new” = IDs not in “already seen”,
  - On request, full message bodies/metadata only for “new” IDs (to keep hydration deterministic and minimal).

---

## 6. No watch/history hot path in MVP

- **Watch (push):** Not implemented. No `users.watch` or webhook URL.
- **History API:** Not used for intake. Polling + `messages.list` + “already seen” filtering is the only path.
- **Rationale:** Keeps MVP simple, avoids webhook infrastructure and History pagination complexity. Can be revisited post-MVP.

---

## 7. Summary (acceptance checklist)

- [x] **Label-first behavior is explicit:** Single intake label; `messages.list` with that label only; no whole-inbox.
- [x] **Polling cadence is explicit:** Configurable interval (default 15 min); polling only; no watch/history in MVP.
- [x] **Whole-inbox exclusions:** Reader never lists full inbox; only intake-label list + hydrate new IDs.
- [x] **No watch/history hot path in MVP:** Documented and out of scope.

---

*Ref: TASK-011, EPIC-03 Gmail Intake.*
