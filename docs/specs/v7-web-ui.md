# v7 Web UI Scope (TASK-093)

**Scope:** Define the first approved scope for a RoleForge web interface without changing the product's Telegram-first operating model.

**Refs:** `docs/research-v4-plus.md` §4.4, `docs/architecture.md`, `docs/roadmap.md`, `docs/specs/v5-application-lifecycle.md`.

---

## 1. Decision summary

- The web UI is **single-user only**.
- Authentication is **Bearer token only**; no OAuth, no local account system, no multi-user permissions.
- Telegram remains the **primary delivery and action surface** for alerts, queue flow, and low-latency operator interaction.
- The web UI is an **operator console**, not a replacement for Telegram.
- Initial web value is visibility and control, not a second full workflow engine.

---

## 2. What stays Telegram-first

These flows remain centered in Telegram:

- digest delivery
- alert delivery
- queue review
- quick state actions where low friction matters
- application status updates when a fast button-based flow is enough

Reason: these are already working, low-noise, and aligned with the single-operator usage model.

---

## 3. What moves to web

The first approved web scope is:

1. **Analytics dashboard**
   - score distribution
   - source counts
   - match/state funnel
   - recent activity

2. **System health**
   - `job_runs` visibility
   - recent failures
   - source/job status indicators

3. **Source management**
   - inspect feeds and monitors
   - enable/disable sources
   - view source configuration status

4. **Queue browser**
   - sortable/filterable table view
   - bulk actions where web is more efficient than Telegram

5. **Profile inspection/editing**
   - inspect `profiles.config`
   - edit scoring and filter settings in a controlled way

6. **Application workspace (later wave, EPIC-19 second slice)**
   - read-only applications list and detail views (`/applications`, `/applications/{id}`)
   - chronological workspace timeline over applications, employer threads, and interview events
   - vacancy, profile, and company context visible alongside the timeline

---

## 4. Deferred from the first web slice

These are explicitly **not required** for the first web implementation:

- multi-user auth
- OAuth / SSO
- a full Telegram replacement
- rich visual design system work
- calendar sync UI

The complex application workspace was intentionally deferred from the very first v7 milestone and is now implemented as a focused read-mostly slice (`TASK-100`) without changing the Telegram-first model.

The **application workspace** is allowed later inside EPIC-19, but it is a second-wave feature after analytics, health, source management, and queue browsing are stable.

---

## 5. Technical direction

- **Backend/UI stack:** FastAPI + Jinja2 + HTMX
- **Auth:** Bearer token from env or keyring
- **Data source:** existing Postgres only
- **No SPA build system**
- **No new service boundary**

This keeps the web layer consistent with the repository's current philosophy: Postgres-first, reversible changes, minimum operational overhead.

---

## 6. Acceptance for TASK-093

TASK-093 is complete when:

- Telegram vs web boundaries are explicit
- auth model is explicit
- initial web modules are explicit
- deferred scope is explicit
- EPIC-19 can start from this contract without another product-decision round

---

## 7. Consequences for EPIC-19

The recommended order inside EPIC-19 becomes:

1. `TASK-094` scaffold
2. `TASK-095` auth
3. `TASK-096` analytics dashboard
4. `TASK-099` system health
5. `TASK-101` source management
6. `TASK-097` queue browser
7. `TASK-098` profile editor
8. `TASK-100` application workspace later

This preserves the strongest near-term value and avoids overbuilding the UI before the v5 lifecycle is mature.
