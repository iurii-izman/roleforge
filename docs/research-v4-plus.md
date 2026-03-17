# RoleForge v4+ Strategic Research

**Date:** 2026-03-17
**Scope:** Research-heavy audit of current state + strategic direction for v4, v5, v6, v7
**Mode:** Architecture-first, tradeoff-driven, no implementation

---

## Table of Contents

1. [Current-State Audit](#1-current-state-audit)
2. [Strategic Product Diagnosis](#2-strategic-product-diagnosis)
3. [Future Product Map](#3-future-product-map)
4. [Version Research: v4, v5, v6, v7](#4-version-research)
5. [Alternatives and Tradeoffs](#5-alternatives-and-tradeoffs)
6. [Cross-Cutting Workstreams](#6-cross-cutting-workstreams)
7. [Proposed Backlog Structure](#7-proposed-backlog-structure)
8. [Architecture Recommendation](#8-architecture-recommendation)

---

## 1. Current-State Audit

### 1.1 What already works

**Ingestion pipeline (Gmail-first):**
`gmail_poll` fetches messages via label-scoped `messages.list`, resolves label ID per run,
loads seen IDs from `gmail_messages`, hydrates only new IDs. Idempotency is enforced at two
levels: `gmail_messages.gmail_message_id UNIQUE` (DB) and the seen-IDs set (in-memory per
run). This is solid. No silent drops, no duplicate rows.

**Normalize/dedup/persist chain:**
`normalize_candidate` → `group_by_dedup_key` → `persist_deduped` is the cleanest piece of
the codebase. The vacancy observation pattern (one vacancy row, N observation rows linking
to source messages) is the right data model. The dedup key hierarchy (canonical_url primary,
title+company fallback) handles the most common real-world cases. The `ON CONFLICT DO NOTHING`
pattern at all insertion points makes every run idempotent.

**Feed intake (v3.1):**
`feed_poll` reuses the exact same normalize/dedup/persist chain as Gmail. The
`feed_source_key` convention (`{feed_id}:{entry_id}`) in `vacancy_observations` is
architecturally clean and already extensible to connectors (`connector:{id}:{ext_id}`) and
future monitors (`monitor:{id}:{ext_id}`) without schema changes.

**Profile system:**
Multiple profiles with per-profile `hard_filters` and `weights` in `profiles.config` JSONB.
One shared formula. No schema duplication for profiles. The `min_score` floor per profile,
the score bands (high ≥ 0.75, medium ≥ 0.5, low < 0.5), and the `review_rank` ordering
are correctly separated: hard filters gate eligibility, score+rank govern ordering.

**Delivery (Telegram):**
Digest is low-noise by design: one scheduled message per profile group, grouped by score
band, top-N highlights. Queue is pull-based: one card per `review_rank`, with position
counter and "why in queue" explainability snippet. Actions (`shortlist`, `review_later`,
`ignore`, `applied`) write to `review_actions` and update `profile_matches.state` atomically.

**Audit trail:**
`job_runs` captures start, finish, status, and structured JSON summary for every scheduled
job. `telegram_deliveries` captures every sent digest or queue card payload. `review_actions`
captures every operator interaction. Everything is in Postgres and queryable.

**Replay:**
`replay_one_message` and `replay_date_window` re-run the full parse/normalize/dedup/persist
chain from stored `gmail_messages` without re-fetching from Gmail API. This is correctly
implemented and valuable for parser iteration.

**Kill-switch governance:**
`FEED_INTAKE_ENABLED` (global) + per-feed `enabled` in `feeds.yaml` is the right pattern.
Simple, orthogonal, consistent. This pattern can be replicated for monitors and connectors
without architectural change.

**Retry policy:**
Three-tier: Gmail (implemented in `gmail_reader.retry`), Telegram (generic helper with
classifier), AI (generic helper with classifier). Transient vs permanent distinction is
explicit. No DLQ complexity. Permanent failures surface via `job_runs.status = 'failure'`
+ `error_type: 'permanent'` in summary.

---

### 1.2 Strongest foundation

The observation pattern and the JSONB config model are the two decisions that age best.

**Observation pattern:** Every vacancy can have multiple source observations. A job posted
on LinkedIn, picked up by an RSS feed, and also sent as a Gmail alert becomes one `vacancies`
row with three `vacancy_observations` rows. Dedup is handled at the source key level. This
model will hold through v6 (monitor sources) without schema pressure.

**JSONB config model:** `profiles.config`, `profile_matches.explainability`, and
`job_runs.summary` use JSONB deliberately. This avoids the premature column explosion that
typically happens when profile behavior or job summary fields evolve. New keys (e.g.
`delivery_mode`, `keywords`, `ai_metadata`) can be added without migrations. The trade-off
(less strict typing) is acceptable because these fields are read by controlled application
code, not ad-hoc queries.

---

### 1.3 Bottlenecks

**Bottleneck 1 — Scoring is non-differentiating (critical):**
The scoring engine's architecture is correct, but the actual dimension implementations are
placeholders. From `roleforge/scoring.py`:

```python
def _dimension_title_match(vacancy, _profile):
    return 0.5 if (vacancy.get("title") or "").strip() else 0.0

def _dimension_company_match(vacancy, _profile):
    return 0.5 if (vacancy.get("company") or "").strip() else 0.0

def _dimension_keyword_bonus(_vacancy, _profile):
    return 0.0   # always zero
```

With default weights (title 1.0, company 0.8, location 0.6, keyword 0.5) and a vacancy
that has title + company + location, the score is:

```
(1.0 × 0.5 + 0.8 × 0.5 + 0.6 × 1.0 + 0.5 × 0.0) / (1.0 + 0.8 + 0.6 + 0.5)
= (0.5 + 0.4 + 0.6 + 0.0) / 2.9 ≈ 0.517
```

This means virtually all vacancies that pass hard filters score between 0.34 and 0.52.
Score bands (`high ≥ 0.75`, `medium ≥ 0.5`) are populated at the boundary but not
meaningfully differentiated. The digest "4 high, 3 medium" labels are currently unreliable
as signal. Threshold-triggered alerting (v4) would fire for everything or nothing.

**This is the #1 blocker for the entire v4 roadmap.** Real keyword matching must be
implemented before delivery intelligence is meaningful.

**Bottleneck 2 — Parser quality ceiling:**
The deterministic parser handles single-job and multi-job digests via regex/structure
detection. This works for well-formatted emails but degrades on HTML-heavy templates,
non-standard digest layouts, or unusual subject formatting. `parse_confidence` is produced
but there's no feedback mechanism. The MVP verification guide (TASK-021) explicitly notes
this as a human review task. This is acceptable for now but becomes a ceiling as source
diversity grows in v3.2/v6.

**Bottleneck 3 — No urgency differentiation in delivery:**
Even if a very high-signal vacancy arrives, it goes through the same digest path as a
low-signal one. If the operator receives one daily digest, a time-sensitive opportunity
(offer deadline, fast-moving startup) may sit unseen. This is by design for MVP, but
becomes a product gap once real scoring works.

**Bottleneck 4 — No scheduler in code:**
Job orchestration relies on external cron. This is fine for a single machine but creates
friction when moving to a hosted runtime: cron must be configured separately, there's no
in-process coordination between jobs (e.g. "run scoring after feed_poll finishes"), and
there's no visibility into "when is the next run scheduled" from the job_runs log.

---

### 1.4 Proven architectural decisions

| Decision | Evidence of value |
|----------|------------------|
| Postgres-only source of truth | Zero sync issues; replay just works; operator SQL queries have no joins to external systems |
| `vacancy_observations` indirection | Feed integration (v3.1) added with one migration and zero changes to vacancy/scoring code |
| `ON CONFLICT DO NOTHING` everywhere | Re-running any job twice produces no side effects |
| JSONB for config/explainability/summary | Profile config evolved from MVP to v2 presets without schema migrations |
| Per-job `job_runs` logging | Operators can diagnose failures without external logging platform |
| Kill-switch env vars | Feed intake is in code but safely off by default |

---

### 1.5 Fragility points

**Label resolution per-run:** `gmail_poll` resolves label name → ID on every run via
`users.labels.list`. If the label is renamed or permissions change, the run fails with a
confusing error. Low probability but worth caching or validating at startup.

**Dedup by title+company fallback:** When `canonical_url` is absent, the dedup falls back
to exact title+company string matching after normalization. Slight variation in company name
("Acme Corp" vs "Acme") or title ("Senior Backend Engineer" vs "Backend Engineer, Senior")
creates duplicate vacancies. This is a real risk with multi-job digests where URL extraction
fails. Currently, normalization handles basic cases, but edge cases exist.

**Parser confidence is advisory:** Downstream code doesn't hard-filter on
`parse_confidence`. A vacancy with confidence 0.1 goes through full scoring and can appear
in the queue. This is intentional for recall, but can produce noise. In v4, AI-assisted
re-extraction for low-confidence items would address this cleanly.

**No raw feed payload storage:** Feed entries are normalized immediately; raw payload is
not stored. This means feed replay isn't possible: if feed_poll logic has a bug, you must
re-run `feed_poll` and hope the feed still has the same entries (RSS feeds often drop old
items within 30 days). This is a deliberate trade-off (no storage bloat), but it is
different from Gmail's full replay capability.

**Scorer assumes all profiles every time:** `scripts/run_scoring_once.py` and the scoring
engine re-score all unscored vacancies against all profiles on every run. As the number of
vacancies and profiles grows (v5: dozens of companies, v6: hundreds of monitor results),
this O(vacancies × profiles) scan could become slow. The `ON CONFLICT DO UPDATE` upsert
handles this, but performance should be monitored.

---

### 1.6 Outdated or maturing assumptions

**"AI only where ROI is explicit" — still correct, but the explicit ROI cases are now
clearer:** Post-v3.1, the pipeline is stable enough to define exactly where AI adds value:
vacancy summarization (post-scoring, high-score items only), field extraction from low-parse-
confidence emails, employer reply classification (v5). These are bounded, measurable, and
reversible. The assumption itself is correct; the list of approved use cases can now grow.

**"Digest-only is sufficient" — ready to revisit:** The daily digest model was correct
for MVP to avoid notification fatigue. With real scoring (v4), threshold-triggered alerts
for genuinely high-signal matches become viable. The question is not whether to add alerts,
but whether to make them opt-in or opt-out per profile.

**"No analytics dashboard in MVP" — becoming a gap:** `scripts/report_profile_stats.py`
and ad-hoc SQL queries are the current analytics path. As the operator's job search produces
more data (matches, actions, applications), the gap between "Postgres + SQL" and "a readable
view" grows. A minimal read-only analytics view is a reasonable v4.5/v5 deliverable before
the full v7 web UI.

**Product-brief still lists RSS as non-goal:** The product-brief's non-goals section says
"No IMAP, Outlook, RSS, ATS APIs, or scraping in MVP." RSS is now v3.1 (done). The brief
should be updated to reflect what the product has become.

---

## 2. Strategic Product Diagnosis

### 2.1 What RoleForge is today

RoleForge is a **personal job intelligence triage system** for a single operator who receives
job alerts by email. Its job is to:

1. Ingest job emails deterministically (no silent drops, no duplicates)
2. Normalize vacancy data to a canonical form
3. Score matches against the operator's multiple search profiles
4. Deliver only a low-noise Telegram summary (digest + queue) instead of raw inbox
5. Preserve a complete, queryable audit trail of everything

The system has achieved its MVP goal: it is deterministic, replayable, explainable, and
low-noise. It is also modular: adding RSS feeds in v3.1 required no changes to vacancy,
scoring, or delivery code.

What it is **not** yet: an intelligent system. Scoring is placeholder-level. There is no
urgency differentiation. There is no feedback loop. The operator's review actions (shortlist,
ignore) are logged but never used to improve future scoring.

---

### 2.2 What RoleForge must not become

**A multi-user SaaS platform.** The system is designed for single-operator precision. Multi-
tenancy would require auth, data isolation, billing, rate limiting — all of which are
orthogonal to the product's value. If the operator wants to share, copy the repo.

**A generic workflow automation tool.** n8n, Zapier, Make — these are horizontal tools.
RoleForge's value is domain specificity: it knows what a vacancy is, what a profile is,
what a review action means. Generalizing this to "any webhook" would destroy that.

**A job board aggregator.** Connecting every job source is the wrong goal. The right goal
is connecting the sources that have the highest signal-to-noise ratio for this operator's
specific search. Quality of signal > quantity of sources.

**An AI-first system.** AI is a tool, not an architecture. Scoring must remain deterministic
and explainable. If the operator can't understand why a vacancy scored 0.8, the system has
failed its core promise of operator trust. AI assists; rules decide.

**A full CRM.** Application tracking, interview scheduling, and employer communication are
valuable add-ons (v5), but they must not grow to dominate the system. The core is still
job intelligence and triage.

---

### 2.3 Unique product logic

Three properties together make RoleForge's product logic distinctive:

1. **Deterministic-first:** The same input always produces the same output. Bugs are
   reproducible. History is replayable. The operator can trust the system to behave
   consistently without "AI hallucination" in the critical path.

2. **Operator-first explainability:** Every score comes with `positive_factors` and
   `negative_factors`. The queue card shows "why in queue." The operator is never left
   wondering "why did this show up?" This is non-negotiable.

3. **Single source of truth with audit trail:** Everything lives in Postgres. Every
   job run, every review action, every delivery is logged. The operator can query the
   full history at any time. This is what allows safe evolution — you can change the
   scoring logic and replay the full history to see how rankings would change.

---

### 2.4 Core loop today

```
Gmail (15-min poll) → raw message stored
→ replay/parse → vacancy candidates
→ normalize → dedup → vacancies + observations
→ score against profiles → profile_matches
→ digest (daily) → Telegram → operator reviews queue
→ review actions update state
```

The loop is complete but slow and non-differentiating. Every step works, but the operator
gets the same experience regardless of whether a vacancy is a perfect match or a distant
stretch.

---

### 2.5 Core loop in v4+

```
Sources (Gmail 5-min + feeds + monitors)
→ raw intake + store (Gmail stores body; feeds/monitors store normalized only)
→ parse → normalize → dedup → vacancies
→ AI enrichment (optional, high-score items only)
→ score (real keyword matching) → profile_matches
→ delivery router:
    score ≥ high_threshold → immediate Telegram alert (if opted in)
    score in mid-band → micro-batch queue (flush every N min)
    score below threshold → digest (daily, unchanged)
→ operator: alert → immediate action
             queue → review cards with application context
             digest → full picture of the week
→ review actions + application tracking (v5) → feedback data
→ (future) scoring calibration from action history
```

The key additions are: **real scoring**, **threshold-aware delivery routing**, and eventually
**application lifecycle** that connects review → apply → response → interview.

---

## 3. Future Product Map

### 3.1 Evolution path

```
Today (v3.2)                v4                    v5                   v6                  v7
─────────────────────────────────────────────────────────────────────────────────────────────
Gmail + RSS intake     Real scoring          Application            HH.ru + monitor      Web UI
                       keyword-based         lifecycle              sources              console

Digest-only           Threshold delivery    Employer reply         Parametrized         Profile
delivery              + micro-batch         matching               search queries       editor

Placeholder           AI enrichment         Interview              Monitor              Analytics
scoring               for high-score        prep (AI-              registry             dashboard
                      items                 assisted)

3 profiles, queue,    delivery_mode         applications,          monitors.yaml        Source
review actions        per profile           employer_threads,      + kill-switch        management
                                            interview_events
```

### 3.2 Stage gates and dependencies

```
v4 requires:
  ✓ Scoring EPIC-13 (mandatory prerequisite — everything else depends on it)
  ✓ Delivery mode config in profiles.config
  ✓ Alert path job (threshold check + send)
  ○ AI enrichment (optional, can be v4.1)

v5 requires:
  ✓ v4 complete (application tracking is most useful when matches are high quality)
  ✓ Application schema (new tables)
  ✓ Inbox classifier (employer reply detection)
  ✓ Application state machine
  ○ Interview prep AI (can be v5.1)

v6 requires:
  ✓ v3.2 connector contract (done — TASK-048/049)
  ✓ v4 real scoring (monitor results need meaningful scoring to filter noise)
  ✓ Monitor registry design (monitors.yaml)
  ✓ HH.ru adapter
  ○ Second monitor (can wait for v6.1)

v7 requires:
  ✓ v4 (analytics need real scores)
  ✓ Some v5 data (application workspace is only valuable with applications)
  ✓ FastAPI scaffold
  ✓ Auth (simple)
  ○ Full interview workspace (v7.1)
```

---

## 4. Version Research

### 4.1 v4 — Real scoring + delivery intelligence

**Goal:**
Transform RoleForge from a "collect-and-batch-deliver" system to an "intelligently score and
route" system. The operator should receive immediate or near-immediate signal for high-
confidence matches, while low-signal items still accumulate in the digest.

**Operator value:**
High-signal vacancies surface within minutes, not the next daily digest. The operator can
act on a time-sensitive opportunity without waiting 24 hours. Low-signal items don't
increase notification noise.

**Workflow:**
1. `gmail_poll` runs every 5 minutes (configurable, reduced from 15)
2. After each poll + normalize/dedup/score cycle, a delivery router checks new matches
3. Matches above `profile.config.delivery_mode.immediate_threshold` (e.g. 0.80) trigger
   an immediate Telegram alert (if `alert_enabled: true` for that profile)
4. Matches above `batch_threshold` (e.g. 0.55) but below immediate threshold are queued
   for micro-batch delivery every `batch_interval_minutes` (e.g. 30)
5. All remaining matches accumulate in the daily digest (unchanged behavior)
6. Separately, post-scoring AI enrichment generates a short summary for high-score matches
   and stores it in `vacancies.ai_metadata`

**Architectural impact:**
No new tables required for v4 core. Changes are:
- `roleforge/scoring.py`: real `_dimension_title_match` (keyword overlap), real
  `_dimension_keyword_bonus`, real `_dimension_company_match` (allowlist or presence)
- `profiles.config` extended with `keywords: [...]`, `skills: [...]`, `delivery_mode: {...}`
- New job `roleforge/jobs/alert.py`: reads recent profile_matches, checks threshold,
  sends immediate alerts for new high-score items, marks as alerted in delivery_log
- `telegram_deliveries.delivery_type` extended with `'alert'` value
- Optional: `roleforge/jobs/batch_delivery.py` (micro-batch flush)

**Data model impact:**

Schema addition:
```sql
ALTER TABLE vacancies ADD COLUMN IF NOT EXISTS ai_metadata JSONB;
-- ai_metadata shape: {summary: str, model: str, prompt_hash: str, enriched_at: str}
```

Profile config extension (no migration, JSONB):
```json
{
  "hard_filters": { ... },
  "weights": { ... },
  "keywords": ["python", "backend", "distributed systems"],
  "skills": ["PostgreSQL", "Kubernetes", "Rust"],
  "delivery_mode": {
    "alert_enabled": false,
    "immediate_threshold": 0.80,
    "batch_enabled": false,
    "batch_threshold": 0.55,
    "batch_interval_minutes": 30
  }
}
```

`alert_enabled` and `batch_enabled` default to false, preserving existing digest-only
behavior for all existing profiles.

**AI role in v4:**
- **Not** in the scoring path. Scoring stays deterministic.
- Post-scoring enrichment: for matches with `score >= immediate_threshold`, call AI to
  generate a 2–3 sentence summary of the vacancy and store in `vacancies.ai_metadata`.
- Low-confidence items (`parse_confidence < 0.5`): optional AI-assisted field extraction
  to fill missing title/company/location. This is additive, not replacing deterministic
  parser.

**Deterministic role:**
All scoring dimensions are keyword-based rules. Hard filters remain fully deterministic.
Score → delivery routing threshold check is deterministic. AI only writes to advisory
fields (summary, confidence calibration) that do not affect score.

**Ops impact:**
- `gmail_poll` cadence reduced (configurable). More runs = more `job_runs` rows. At 5-min
  cadence that's ~288 rows/day for gmail_poll alone. Still fine for single-operator scale.
- AI enrichment calls: bounded by `score >= immediate_threshold` matches. In practice, a
  few per day. Cost is negligible.
- Alert job should be idempotent: use a `delivery_log` check or `telegram_deliveries`
  lookup to avoid re-sending alerts for the same match.

**Main risks:**
1. If scoring thresholds are miscalibrated, operator gets flooded with "immediate" alerts
   for average matches, destroying the low-noise property. Mitigation: both
   `alert_enabled` and `batch_enabled` default to false. Operator opts in explicitly.
2. `keyword` matching is case-insensitive substring by default. This can produce false
   positives ("Python" matches "Python Developer" but also "Monty Python Productions").
   Mitigation: define keyword matching as whole-word or weighted phrase matching, not
   bare substring. Profile config can specify this.
3. AI enrichment adds latency to the post-scoring path. Mitigation: run enrichment as a
   separate async step after match is committed to DB. Alert job reads `ai_metadata` if
   present, sends without it if enrichment isn't ready.

**What unlocks v4:**
EPIC-13 (scoring engine fix). Nothing else in v4 is meaningful without real score
differentiation.

**What to defer:**
- Gmail push/watch API (too much infra complexity for marginal latency gain over 5-min polling)
- Dual-AI-provider hot path (single provider is correct)
- AI in scoring path (deterministic scoring is non-negotiable)
- Adaptive scoring calibration from review actions (v4.1 or later)

---

### 4.2 v5 — Application lifecycle

**Goal:**
Close the loop between "match reviewed → applied" and "employer responds." The system should
recognize employer reply emails, link them to the known vacancy/company, and help the
operator track their application pipeline without managing a separate spreadsheet.

**Operator value:**
When an HR person emails about an interview, the system should surface this as an action
item with context (which job, what was the original vacancy text, what is the company).
The operator shouldn't have to mentally track "which email from recruiter@company.com
was about which job I applied to two weeks ago."

**Workflow:**
1. Operator marks `profile_matches.state = 'applied'` (existing)
2. `application` record is created (manually or automatically on state change) with
   `applied_at`, `status = 'applied'`, linked to `profile_match_id`
3. `gmail_poll` continues to store all new messages as before
4. New job `inbox_classifier` runs after each `gmail_poll`, reads new `gmail_messages`
   that haven't been classified yet, uses three signals to determine message type:
   - **Thread signal:** `raw_metadata.threadId` matches a thread containing a known
     vacancy message
   - **Domain signal:** `From:` header domain matches `vacancies.company` (normalized)
   - **Subject signal:** subject contains keywords ("Re: your application", "interview",
     "next steps", "offer", "assessment") using a deterministic rule set first
5. High-confidence employer replies (thread + domain match) are auto-linked
6. Ambiguous cases (domain match only, or subject keyword only) are surfaced to operator
   as "possible employer reply" Telegram message
7. Once linked, `employer_thread` records track the conversation thread and `interview_events`
   records track calendar events extracted from the email

**Application state machine:**
```
applied
  → hr_pinged       (HR sends initial ping or acknowledgement)
  → ghosted         (30+ days with no response, operator or auto-marks)
hr_pinged
  → interview_scheduled
  → rejected
interview_scheduled
  → offer
  → rejected
offer
  → accepted
  → declined
```

**Employer reply classification — AI role:**
Deterministic rules handle the clearest cases (thread_id match + "Re:" subject prefix).
AI classification handles the ambiguous middle cases:
- Input: email subject, sender domain, body excerpt (first 500 chars)
- Output: `{ type: 'employer_reply' | 'new_vacancy' | 'spam' | 'ambiguous', confidence: float,
           next_action: str | null, date_hint: str | null }`
- AI is used here because the signal space is too large for exhaustive rules (email
  subjects are highly varied; "Exciting opportunity at Acme" could be spam or a follow-up)
- The classification result is advisory: operator confirms ambiguous cases

**Schema additions for v5:**
```sql
-- Applications: one row per operator's application action
CREATE TABLE IF NOT EXISTS applications (
  id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  profile_match_id UUID NOT NULL REFERENCES profile_matches (id) ON DELETE CASCADE,
  vacancy_id       UUID NOT NULL REFERENCES vacancies (id) ON DELETE CASCADE,
  status           TEXT NOT NULL DEFAULT 'applied'
                   CHECK (status IN ('applied', 'hr_pinged', 'interview_scheduled',
                                     'offer', 'rejected', 'ghosted', 'accepted', 'declined')),
  applied_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  notes            JSONB,  -- operator notes, AI-extracted summaries
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Employer threads: conversation tracking
CREATE TABLE IF NOT EXISTS employer_threads (
  id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  application_id   UUID NOT NULL REFERENCES applications (id) ON DELETE CASCADE,
  gmail_thread_id  TEXT,           -- Gmail threadId for correlation
  company_domain   TEXT,           -- sender domain (for fallback matching)
  last_message_at  TIMESTAMPTZ,
  classification   JSONB,          -- {type, confidence, last_classified_at}
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Interview events: timeline entries
CREATE TABLE IF NOT EXISTS interview_events (
  id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  application_id   UUID NOT NULL REFERENCES applications (id) ON DELETE CASCADE,
  event_type       TEXT NOT NULL
                   CHECK (event_type IN ('hr_call', 'technical', 'panel', 'offer',
                                         'assessment', 'reference', 'other')),
  scheduled_at     TIMESTAMPTZ,    -- extracted or operator-entered
  notes            JSONB,          -- {interviewer, meeting_link, prep_checklist, ai_briefing}
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_applications_profile_match ON applications (profile_match_id);
CREATE INDEX IF NOT EXISTS idx_applications_status ON applications (status);
CREATE INDEX IF NOT EXISTS idx_employer_threads_application ON employer_threads (application_id);
CREATE INDEX IF NOT EXISTS idx_employer_threads_gmail ON employer_threads (gmail_thread_id);
```

**AI role in v5 (highest ROI in the product):**
1. `inbox_classifier`: classify employer reply vs new vacancy vs spam (discussed above)
2. `next_action_extractor`: extract date/time of interview, meeting link, interviewer name
   from employer email body → populate `interview_events.scheduled_at` and `notes.meeting_link`
3. `company_briefer`: given `vacancy.company` and `vacancy.title`, generate a short
   background on the company (founded, HQ, tech stack, recent news) for pre-interview prep.
   Stored in `interview_events.notes.ai_briefing`. This is an explicitly bounded, high-ROI
   use: the operator gets 5 minutes of research condensed into 200 words.
4. `prep_checklist`: generate interview preparation checklist based on job title and role
   description. Stored in `interview_events.notes.prep_checklist`.

**Deterministic role:**
- Thread_id matching (Gmail API) is deterministic and preferred
- Domain normalization (sender domain extraction) is deterministic
- Status state transitions are deterministic (no AI gates a state change)
- Calendar reminder timing rules (e.g. "remind 24h before `scheduled_at`") are deterministic

**Ops impact:**
- New `inbox_classifier` job runs after each `gmail_poll`. Reads recent `gmail_messages`
  not yet classified. Writes to `employer_threads`. Adds AI calls per unclassified message.
- At typical volume (operator checks email daily, 5-20 new messages per day), AI cost is
  minimal (cents per day).
- `applications` table grows slowly: one row per application. At 50 applications/month,
  this is never a performance concern.

**Main risks:**
1. Employer reply matching false positive: the system matches an email to the wrong
   application. Mitigation: require thread_id match for auto-linking; domain-only matches
   are always surfaced for operator confirmation.
2. Application tracking becomes a burden: the system adds friction instead of removing it
   if the operator must manually manage application status. Mitigation: auto-advance status
   where signals are clear (thread with "offer" keyword + domain match → offer signal →
   surface notification, but don't auto-set status; require operator tap to confirm).
3. Gmail thread_id reliability: thread_id is stable in Gmail API for a given conversation.
   But if the operator sends an application from a different email client (e.g. a job portal's
   apply button), there may be no thread_id linking the employer reply back. Mitigation:
   domain + subject matching as fallback.

**What unlocks v5:**
v4 complete (particularly real scoring, which makes "applied" actions more meaningful —
you want to apply to high-confidence matches, not random ones). Then: application schema
decision, inbox classifier design.

**What to defer:**
- Google Calendar sync (add calendar event for interviews) — real-time sync is complex;
  store dates in DB and deliver reminders via Telegram instead
- LinkedIn integration for company research — too much auth/API complexity; AI generation
  from public info is sufficient and simpler
- Full email drafting assistant — scope creep into CRM territory

---

### 4.3 v6 — Active market monitoring

**Goal:**
Move beyond reactive (waiting for emails to arrive) to proactive: RoleForge actively
queries job platforms on a schedule and surfaces new matches even if the operator hasn't
set up email alerts for that source.

**Operator value:**
The operator finds opportunities on HH.ru (or other monitored platforms) that they wouldn't
have seen via email alone. The system does the daily search for them and delivers only
relevant results.

**Source class analysis:**

| Source class | Structure | Legal clarity | Maintenance | First candidate |
|-------------|-----------|--------------|-------------|----------------|
| Official APIs | High (JSON) | High | Low | HH.ru |
| RSS/Atom feeds | Medium | High | Low | Already in v3.1 |
| ATS connectors | High (JSON) | Medium | Medium | Greenhouse (v3.2) |
| Search result pages (HTML) | Low (scraping) | Low | High | Not recommended |
| Job board deep crawl | None (scraping) | Very low | Very high | Never |

**HH.ru as v6 first monitor:**
HH.ru (hh.ru) is the dominant job platform in Russia and broader CIS. It provides a
well-documented public REST API with no authentication required for vacancy search:

```
GET https://api.hh.ru/vacancies
  ?text=python+backend
  &area=1               (Moscow region ID)
  &schedule=remote
  &per_page=100
  &page=0
  &date_from=2026-03-16  (ISO date, filter by publication date)
```

Response fields of interest: `id`, `name` (title), `employer.name`, `area.name`,
`alternate_url` (canonical job URL), `salary` (structured: from, to, currency, gross),
`published_at`.

Key properties:
- No auth for public search (acceptable use per ToS for personal automation)
- `alternate_url` is stable (suitable as `canonical_url` for dedup)
- `salary` is structured (unlike Gmail-parsed `salary_raw`) — this is a significant
  data quality upgrade
- Rate limit: approximately 7 requests/second; 2000 results max per search query
- `date_from` parameter allows incremental polling without re-processing old results

**Monitor abstraction design (Monitor ≠ Feed):**
The current `feeds.yaml` model maps one entry to one URL polled via `feedparser`. A monitor
is different: it has parametrized search query, custom adapter logic, and potentially
multiple API pages per poll. The registry should be separate:

```yaml
# config/monitors.yaml
monitors:
  - id: hh_python_remote
    name: HH.ru Python Remote
    type: hh_api
    enabled: true
    params:
      text: "python backend"
      area: 1
      schedule: remote
      per_page: 100
    poll_interval_minutes: 60

  - id: hh_go_remote
    name: HH.ru Go Remote
    type: hh_api
    enabled: false
    params:
      text: "golang backend"
      schedule: remote
      per_page: 100
    poll_interval_minutes: 120
```

Adapter interface (`roleforge/monitors/hh.py`):
```python
def fetch_candidates(
    monitor_id: str,
    params: dict,
    seen_source_keys: set[str],
    *,
    date_from: str | None = None,
) -> list[dict]:
    """
    Returns candidates in standard shape.
    Source key: f"monitor:hh:{vacancy_id}"
    salary_raw: f"{salary['from']}–{salary['to']} {salary['currency']}" if present
    """
```

This reuses the exact same `group_by_dedup_key` → `persist_deduped` → `score_vacancy_for_profiles`
chain. No new pipeline logic. Only a new adapter and a new registry loader.

**Source governance model:**
- `MONITOR_INTAKE_ENABLED` (global kill-switch, default false) — mirrors `FEED_INTAKE_ENABLED`
- Per-monitor `enabled: true/false` in YAML
- `monitor_poll` job logs to `job_runs` with `job_type = 'monitor_poll'` and
  `summary.monitor_id` for per-source health tracking
- Source key prefix `monitor:hh:{id}` distinguishes monitor observations from feed
  observations (`{feed_id}:{entry_id}`) without schema change

**Data model impact:**
No new tables. Source key convention extended:
- Gmail: `gmail_message_id` in `vacancy_observations.gmail_message_id`
- Feeds: `{feed_id}:{entry_id}` in `vacancy_observations.feed_source_key`
- Connectors: `connector:{id}:{ext_id}` in `vacancy_observations.feed_source_key`
- Monitors: `monitor:{type}:{ext_id}` in `vacancy_observations.feed_source_key`

Optional enhancement: add `source_class TEXT` to `vacancy_observations` to make querying
by source type easier. This avoids `LIKE 'monitor:%'` pattern matching. Low priority.

**Dedup benefit with monitor data:**
HH.ru provides stable `alternate_url` for every vacancy. This dramatically improves dedup
quality compared to Gmail-parsed emails where `canonical_url` may be absent. Monitor-
sourced vacancies will almost always dedup correctly by URL.

**Salary data upgrade:**
HH.ru returns structured salary (`from`, `to`, `currency`, `gross`). The current schema
has `salary_raw TEXT`. In v6, it's worth adding `salary_structured JSONB` to `vacancies`
to store structured salary data, enabling salary-range filters in scoring.

**Legal/compliance notes for HH.ru:**
- Terms of Service: HH.ru permits access to public vacancy data for personal use; mass
  indexing or commercial redistribution requires partnership agreement
- Rate limiting: must respect API rate limits (~7 req/s); implement exponential backoff
- `User-Agent` header: should identify the application (e.g. "RoleForge/1.0 personal job search")
- Data retention: storing normalized vacancy data locally is acceptable for personal search
  use; do not re-distribute HH.ru data

**Main risks:**
1. API changes: HH.ru may change API shape or authentication requirements. Monitor adapter
   is isolated (`roleforge/monitors/hh.py`) so changes are contained.
2. Search quality: poor query parameters yield noisy results that pass hard filters and
   flood the queue. Mitigation: real scoring (v4) must be in place first; otherwise monitors
   produce unfiltered noise.
3. Volume: a broad HH.ru query (e.g. "python") with no `area` filter returns 2000+ results
   per poll. With `date_from` incremental polling and a narrow query, this is manageable.
   Document recommended query constraints in the registry template.

**What unlocks v6:**
v4 scoring (critical — without real scoring, monitor results are unfiltered noise).
Then: monitor registry design, HH.ru adapter, `monitor_poll` job.

**What to defer:**
- LinkedIn monitoring (API access too restricted for personal use)
- Indeed monitoring (API deprecated; RSS viable but limited)
- HTML scraping of any platform (never in RoleForge core)
- Second monitor type until HH.ru adapter is validated

---

### 4.4 v7 — Unified operator console

**Goal:**
A web interface that gives the operator a complete, readable view of the system state —
profiles, analytics, queue, applications, source health — without SQL or CLI.

**Operator value:**
The operator can view and manage their job search pipeline without opening a terminal.
Telegram stays for notifications and quick actions; the web console handles configuration,
review of large queues, and application tracking.

**Telegram stays for:**
- Digest delivery (primary push notification)
- Immediate alerts (high-score matches)
- Quick review actions (shortlist, ignore, applied) via inline buttons
- Application update notifications (employer pinged, interview scheduled)
- Queue navigation for mobile quick-review

**Web UI handles:**
- Profile configuration: edit `profiles.config` (keywords, filters, thresholds, delivery mode)
- Full queue: sortable table with multi-select bulk actions (unlike Telegram's one-at-a-time)
- Analytics: match trends over time, score distribution, state funnel (new → applied →
  interview → offer), source quality comparison
- Application workspace: timeline view of each application, notes, prep checklist, interview
  events, company briefing
- System health: job runs log (last N, success/failure, summary), source registry status
  (last poll time, entries/run for each feed/monitor)
- Source management: enable/disable feeds and monitors; add new entries

**Technology recommendation: FastAPI + Jinja2 + HTMX**

Why:
- **No build system**: no npm, no node_modules, no webpack. Single Python process serves
  everything.
- **Minimal dependencies**: FastAPI (already in proximity to the stack), Jinja2 (included
  with FastAPI), HTMX (one CDN script include, no install)
- **HTMX for dynamic interactions**: inline list updates, form submissions, tab switching
  without full-page reloads — without writing JavaScript
- **Natural fit for single-operator tool**: server-side rendering is simpler to debug and
  audit than a React SPA
- **No auth complexity**: HTTP Bearer token (one static token in keyring) or HTTP Basic Auth

Why not React/Vue/Next.js:
- Build system overhead for a single-operator internal tool is unjustifiable
- Separate frontend repo would need its own deployment, CORS config, API versioning
- Operator would need to run two processes (API + frontend)

Why not Streamlit/Datasette:
- Streamlit: good for analytics-only dashboards; limited for forms/actions/configuration
- Datasette: excellent for read-only data exploration; insufficient for queue actions or
  profile editing

**Authentication strategy:**
Single-operator, assumed to run on a private server or localhost:
- Development/localhost: no auth
- Hosted: HTTP Bearer token (one token in keyring, injected via env) checked as middleware
- If exposed publicly: require HTTPS (use Caddy or nginx as reverse proxy)
- No multi-user auth, no OAuth, no session management

**Backend API layer:**
FastAPI naturally produces an API layer (`/api/profiles`, `/api/matches`, `/api/applications`).
This can serve both the web UI (HTMX requests) and future programmatic access. No explicit
versioning in v7.0 — add when there's a reason.

**MVP scope for v7.0:**
1. Analytics dashboard (read-only): match counts by profile/week, score distribution,
   state funnel chart, source health table
2. Queue browser: full queue table, sortable, with multi-select → bulk state update
3. Profile editor: view/edit profile.config JSONB (keywords, filters, min_score, delivery_mode)
4. System health: job_runs log, last N runs per job type, status indicators
5. Authentication: Bearer token middleware

**Deferred to v7.1+:**
- Application tracking workspace (requires v5 schema)
- Source management UI (add/remove feeds/monitors; write to YAML)
- Interview prep module
- Mobile-optimized responsive design (functional but not polished in v7.0)

**Ops impact:**
One additional process (FastAPI app) alongside the existing jobs. Shares Postgres connection
pool. Adds `uvicorn` or `gunicorn` dependency. No new infrastructure.

**Main risks:**
1. The web UI becomes the "real" interface and Telegram becomes secondary. Risk: operator
   stops using Telegram delivery, and the low-noise property degrades because they switch
   to web-based full-queue review (which is more like inbox than queue). Mitigation: keep
   Telegram as the primary push channel; web UI is supplement not replacement.
2. Scope creep: the web UI makes it easy to add "just one more feature" (bulk edit, filters,
   exports). Maintain strict MVP scope.

**What unlocks v7:**
v4 scoring (analytics need real scores), v5 applications (workspace needs data). Then:
FastAPI scaffold, auth, basic templates.

---

## 5. Alternatives and Tradeoffs

### 5.1 Digest-first vs near-real-time alerting

**Digest-first (current):**
Pros: zero notification noise; operator reviews on their schedule; all matches visible in
one summary; no risk of "I saw this pop up and forgot about it"
Cons: 24-hour latency for all matches; time-sensitive opportunities (fast-moving startups,
offer deadlines) may be missed; scoring differentiation has no delivery impact
Hidden cost: if the digest grows large (many sources, many profiles), the single message
becomes overwhelming and loses its low-noise property

**Near-real-time (all matches immediately):**
Pros: maximum immediacy
Cons: notification fatigue is virtually guaranteed; Telegram becomes another inbox;
completely defeats the purpose of RoleForge
Hidden cost: the operator would mute notifications, defeating the system entirely

**Threshold-triggered hybrid:**
Pros: immediacy only for genuinely high-signal matches; digest still covers everything;
operator opts in per profile; preserves low-noise for all other traffic
Cons: requires real scoring (v4 prerequisite); miscalibrated threshold = flooding; adds
scheduling complexity (alert job + batch job + digest job)
Hidden cost: threshold calibration is ongoing work; what's "high signal" changes over time

**Recommendation: threshold-triggered hybrid, with alerts default-off.**
Keep digest as primary. Add alert path in v4 with `alert_enabled: false` default. Operator
enables per-profile when they trust their scoring thresholds. This makes the feature
progressive: opt-in, no disruption to existing behavior.

---

### 5.2 Unified source job vs per-source jobs

**Unified ("sources_poll" runs all sources in one job):**
Pros: single cron entry; simpler orchestration; one job_runs row per cycle
Cons: one source failure can block others; harder to kill-switch one source; harder to tune
per-source cadence; per-source telemetry is muddled
Hidden cost: when adding a new source type, the unified job grows in complexity

**Per-source jobs (current approach: gmail_poll, feed_poll, future monitor_poll):**
Pros: each source has independent error isolation; independent kill-switches; independent
cadence (feeds every 1hr, Gmail every 5min, HH.ru every 30min); each job_run is clearly
attributable to one source
Cons: multiple cron entries; need a scheduler or orchestration layer to coordinate them;
potential for resource contention if they all run simultaneously

**Recommendation: per-source jobs (keep current approach).**
The per-source isolation is valuable. The orchestration complexity is manageable at small
scale. Add a simple scheduler abstraction in v4 (APScheduler or a cron table in Postgres)
to coordinate them without external cron, but keep the job separation.

---

### 5.3 Web UI later (v7) vs earlier (v4/v5)

**Web UI earlier:**
Pros: helps operator visualize scoring quality during calibration (v4); analytics visible
sooner; product direction feedback earlier
Cons: building UI before the data model is stable means frequent UI changes; v4 scoring
changes may reshape what analytics are meaningful; engineering investment before product
value is proven
Hidden cost: web UI pulls focus from pipeline improvements that produce more operator value

**Web UI later (v7, recommended):**
Pros: wait until v5 data model (applications) is stable; UI is built once on a known
foundation; operator gets years of data to actually display
Cons: longer time without a visual interface; analytics requires SQL until v7
Hidden cost: intermediate state (v4–v6) with CLI/SQL analytics may frustrate the operator

**Compromise: Streamlit analytics dashboard in v5 (pre-v7):**
Streamlit can render charts from Postgres queries in ~100 lines of Python. It's not a full
UI, but it removes the "query the DB manually" step for analytics. Read-only, no auth
needed, minimal maintenance. Can be replaced by v7 FastAPI UI later.

**Recommendation: v7 for full web UI, but consider a Streamlit analytics view in v5 as
an intermediate step.** Label it clearly as "temporary analytics view" to prevent it from
growing into a full UI.

---

### 5.4 Connector-first vs market-monitor-first

**Connector-first (Greenhouse/Lever ATS):**
Pros: high data quality (structured, complete); covers companies that list on Greenhouse
Cons: coverage is limited to companies using those specific ATSes; requires API key or
public board URL discovery; overlap with Gmail (many Greenhouse listings also send emails)
Hidden cost: ATS platforms change their APIs; Greenhouse and Lever have had API deprecations

**Market monitor-first (HH.ru):**
Pros: broad coverage of the target market (RU/CIS); no auth required; structured salary
data; adds qualitatively new source coverage that Gmail can't provide
Cons: needs adapter development; HH.ru is regional (not useful for non-RU job search)
Hidden cost: broader coverage = more noise if scoring isn't good; v4 real scoring is prerequisite

**Recommendation: market monitor first (HH.ru in v6), then connectors if needed.**
HH.ru provides genuinely new coverage. Greenhouse/Lever largely overlap with email
notifications. If the operator primarily applies to companies that use Greenhouse, add it
as a v6.1 connector after HH.ru is validated.

---

### 5.5 Application tracking: inside core DB vs separate bounded context

**Inside core DB (same Postgres, new tables):**
Pros: no new infrastructure; JOIN queries across vacancies, matches, and applications are
trivial; same connection pool; same backup; same audit trail
Cons: schema grows larger; "job intelligence" and "application lifecycle" concerns are mixed
in one DB
Hidden cost: schema migrations must be coordinated; drop a column carelessly and you may
lose application history

**Separate bounded context (separate DB or service):**
Pros: clean separation; schema changes in applications don't risk vacancy schema
Cons: cross-context queries require API calls or data sync; dual DB = dual backup = dual
operational complexity; for single-operator tool, the complexity is not justified
Hidden cost: "separate service" mindset often leads to premature microservices

**Recommendation: inside core DB, additive tables.**
New tables `applications`, `employer_threads`, `interview_events` are additive to the
existing schema. Foreign keys to `profile_matches` and `vacancies`. Same Postgres, same
backup, same operational model. The "mixing concerns" objection is a premature purity
concern at this scale.

---

### 5.6 Calendar sync: lightweight date storage vs full integration

**Lightweight (store dates in DB, remind via Telegram):**
Pros: no new API dependencies; no OAuth complexity; dates are queryable; reminders as
Telegram messages are natural for the existing UX
Cons: no calendar entry in Google Calendar; operator must manually add to their calendar
if they want it there
Hidden cost: "I want it in my calendar" is often the first thing an operator asks; this
may feel incomplete

**Full Google Calendar sync:**
Pros: interview events appear in Google Calendar automatically; native calendar UX
Cons: requires additional Google API scope (calendar.events); OAuth flow is more complex;
calendar sync is its own error surface (conflicts, time zones, recurring events); if the
operator deletes the calendar event, the DB may become stale
Hidden cost: calendar integration is always harder than it looks; time zone handling alone
is a significant source of bugs

**Recommendation: lightweight first (v5), full calendar sync as v5.1 opt-in.**
Store `interview_events.scheduled_at`, send Telegram reminders at configurable lead times
(e.g. 24h and 2h before). If the operator specifically requests Google Calendar sync,
add it as an explicit v5.1 feature with its own EPIC.

---

## 6. Cross-Cutting Workstreams

### 6.1 Data model evolution

The schema will evolve additively across versions. Key principle: never drop or repurpose
an existing column. New versions add new tables or new nullable/JSONB-extended columns.

| Version | Schema changes |
|---------|---------------|
| v4 | `ALTER TABLE vacancies ADD COLUMN ai_metadata JSONB` |
| v4 | `profiles.config` extended with `keywords`, `skills`, `delivery_mode` (JSONB, no migration) |
| v4 | `telegram_deliveries.delivery_type` extended with `'alert'` value (requires constraint change) |
| v5 | New tables: `applications`, `employer_threads`, `interview_events` (migration 003) |
| v5 | `gmail_messages`: add `classified_as TEXT` (nullable: 'vacancy' | 'employer_reply' | 'spam') |
| v6 | `vacancies`: add `salary_structured JSONB` (nullable, populated by HH.ru adapter only) |
| v6 | No new tables; monitor source keys reuse `vacancy_observations.feed_source_key` convention |
| v7 | No schema changes (web UI reads existing schema) |

Schema files should continue the migration numbering: `003_applications.sql`,
`004_salary_structured.sql`.

---

### 6.2 Runtime/orchestration

Current state: 5 job entrypoints, external cron, no coordination.

Evolution path:
- **v4**: Add APScheduler or a simple in-process scheduler (schedule library) so jobs can
  be run from one `roleforge/scheduler.py` entrypoint without external cron. Each job keeps
  its own `__main__` entry for manual invocation.
- **v4**: Add an `alert` job (post-scoring threshold check + immediate Telegram send). This
  needs to run after each `gmail_poll` completes. Currently this requires chaining in the
  cron; with an in-process scheduler, it can be `on_completion` of gmail_poll.
- **v5**: Add `inbox_classifier` job, runs after each `gmail_poll`.
- **v6**: Add `monitor_poll` job with per-monitor cadence.
- **v7**: Scheduler status visible in web UI health panel.

The scheduler should not be Airflow, Celery, or any distributed task queue. APScheduler or
`schedule` (PyPI) is sufficient for single-process, single-machine operation. The complexity
budget must stay minimal.

---

### 6.3 Observability

Current state: `job_runs` in Postgres + stdout prints. Adequate for MVP.

Gaps as the system grows:
- No structured logging (print statements are not machine-parseable in hosted environments)
- No per-source health metrics (which feed/monitor last succeeded, entries per run)
- No alerting on consecutive failures (e.g. gmail_poll failing for 3 consecutive runs)

Evolution:
- **v4**: Add JSON structured logging to stdout (`{"ts": ..., "job": ..., "level": ..., "msg": ...}`)
  using Python's `logging` module with a JSON formatter. Hosted environments can route to
  a log aggregator.
- **v4**: Add `consecutive_failures` field to `job_runs` query (window function). Admin
  alert if a job fails 3+ times consecutively.
- **v6**: `job_runs.summary` extended with `monitor_id` and `entries_per_source` breakdowns
  for per-source health visibility.
- **v7**: Web UI health panel reads `job_runs` and renders last-N status per job type.

No external observability platform (Datadog, Grafana Cloud) in scope for single-operator.
Postgres + structured stdout is sufficient.

---

### 6.4 Security and privacy

Current state: Gmail OAuth in keyring, all data local, no external data sharing.

Considerations as system grows:
- **Employer reply emails** (v5): these contain personal job search data and employer
  communications. Must remain local. Never sync to cloud. The `employer_threads` and
  `interview_events` tables are stored in the same local Postgres.
- **AI calls** (v4/v5): vacancy text and email excerpts are sent to an AI provider. The
  operator should be aware of this. Mitigation: use the AI only for content already seen
  in vacancy listings (public job descriptions); do not send raw employer email body to AI
  without operator awareness. For employer reply classification, send only subject +
  first 500 chars, not full body.
- **Web UI** (v7): if exposed on a network, requires authentication. HTTP Basic or Bearer
  token. Never expose without auth on a public IP.
- **HH.ru API** (v6): no personal data is sent to HH.ru. Only search query parameters
  (keywords, location) are sent. No credentials are provided. No operator PII is exposed.

Privacy principle: **all personal job search data stays in the operator's Postgres**. AI
providers receive only public vacancy text, not personal communications.

---

### 6.5 AI governance

Current state: no AI in the production pipeline.

When AI is introduced (v4), governance must address:

**Prompt versioning:** Prompts are code. Store them in `roleforge/prompts/*.py` as
versioned string constants. Each prompt has a `PROMPT_VERSION` string (e.g. `"summary_v1"`).
When a prompt changes, the version string changes, and the hash changes.

**Model pinning:** Always specify the exact model version (e.g. `claude-opus-4-6`,
`gpt-4o-2024-05-13`). Never use "latest" aliases in production. Model updates can silently
change output shape.

**Output tracking:** `vacancies.ai_metadata` should include:
```json
{
  "summary": "...",
  "model": "claude-opus-4-6",
  "prompt_hash": "sha256:abc123",
  "enriched_at": "2026-03-17T12:00:00Z"
}
```
This allows querying which vacancies were enriched with which model/prompt, and re-enriching
when prompts change.

**Cost tracking:** Add `ai_cost_usd` (float, nullable) to `job_runs.summary` when AI is
used. Accumulate per-run cost estimates. Monthly cost visible via simple SQL:
```sql
SELECT date_trunc('month', started_at) AS month,
       SUM((summary->>'ai_cost_usd')::float) AS monthly_ai_cost_usd
FROM job_runs WHERE summary->>'ai_cost_usd' IS NOT NULL
GROUP BY 1 ORDER BY 1;
```

**Degradation policy:** If AI call fails (rate limit, model unavailable), the job continues
without AI enrichment. The match is still delivered; the summary field is absent. AI
enrichment is always additive, never blocking.

---

### 6.6 Cost governance

Current state: no external API costs (Gmail API is free within quota, feedparser has no cost).

Cost surfaces as the system grows:
- **AI enrichment** (v4): per vacancy enriched. At 5-10 high-score matches/day × $0.01–0.03
  per summary = $0.05–0.30/day. Negligible. Track it anyway.
- **AI inbox classification** (v5): per new email processed. At 20 emails/day × $0.005 per
  classification = $0.10/day. Negligible. Track it.
- **HH.ru API** (v6): free for public search. No cost.
- **Postgres hosting**: dominant cost. Single small instance ($5–20/month).

Cost governance rules:
1. Every AI call logs its estimated cost to `job_runs.summary.ai_cost_usd`
2. Monthly cost is queryable via SQL (see above)
3. Hard rate limit on AI calls per run (e.g. max 20 enrichments per gmail_poll cycle)
   to prevent runaway cost if scoring is misconfigured
4. No expensive AI operations (fine-tuning, embeddings index, vector DB) in scope

---

### 6.7 Legal and compliance

| Source | Legal status | Risk | Notes |
|--------|-------------|------|-------|
| Gmail (personal OAuth) | Clear — personal automation | Low | Don't exceed OAuth scopes; keep tokens secure |
| RSS/Atom feeds | Clear — public data | Low | No redistribution |
| HH.ru public API | Clear — personal search | Low | Respect rate limits; add User-Agent; no bulk re-distribution |
| Greenhouse/Lever public boards | Generally clear | Low-medium | Review ToS per board; no commercial redistribution |
| HTML scraping | Legally grey | High | Never in RoleForge core |
| Employer reply emails | Personal communication | Medium | Never sync to cloud; local Postgres only |
| AI provider (OpenAI/Anthropic) | Covered by ToS for API use | Low | Don't send PII unless needed; vacancy text is public |

**Action items before each new source:**
1. Read and document ToS acceptance in `docs/architecture.md` decision log
2. Document rate limits and implement adherence
3. Confirm data may be stored locally for personal use

---

### 6.8 UX consistency

Two channels: Telegram (primary, async push) and future web UI (secondary, on-demand review).

**Consistency principles:**
1. Postgres is the single source of truth. Both channels read from the same DB.
2. Actions taken in Telegram are immediately visible in web UI, and vice versa.
3. Score bands (high/medium/low), state labels, and action names must be identical across
   channels. Define them as constants in `roleforge/constants.py` shared by both.
4. The digest's "top N highlights" should match what the queue shows as highest-priority.
   This is already true (both use `review_rank`); maintain this invariant.

**Telegram UX ceiling:**
Telegram has a 4096-char message limit and inline-button-based interaction. This is right
for:
- Short notifications (alert, digest, application update)
- Simple binary actions (shortlist/ignore, confirm/reject)
- Sequential review (one card at a time)

It is wrong for:
- Bulk operations (select 20 items at once)
- Complex form entry (editing profile config)
- Charting and trend visualization

This is the UX split between Telegram and web UI: single-item / real-time / mobile vs
multi-item / configuration / analytical.

---

### 6.9 Analytics and learning loops

Current state: `scripts/report_profile_stats.py` provides per-profile aggregates. `job_runs`
provides pipeline health. No feedback from review actions to scoring.

Evolution:

**v4 — Scoring calibration analytics:**
After scoring is real (EPIC-13), add a calibration report showing score distribution per
profile, score band breakdown over time, and correlation between score and review actions
(do high-scoring matches get shortlisted more often?). This is pure SQL:
```sql
SELECT
  score_band,
  state,
  COUNT(*) AS cnt,
  ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (PARTITION BY score_band), 1) AS pct
FROM (
  SELECT
    CASE WHEN score >= 0.75 THEN 'high' WHEN score >= 0.5 THEN 'medium' ELSE 'low' END AS score_band,
    state
  FROM profile_matches
) x
GROUP BY score_band, state
ORDER BY score_band, state;
```
This reveals whether the high-score band correlates with actual shortlisting. If high-score
matches are frequently ignored, the keyword weights need recalibration.

**v5 — Application funnel:**
With `applications` table, track conversion:
```
matched → applied: {pct}
applied → hr_pinged: {pct}
hr_pinged → interview_scheduled: {pct}
interview_scheduled → offer: {pct}
```
This is the job search funnel. The operator can see where they're converting and where
they're losing. High match count but low application rate → improve profile calibration.
High application rate but low response rate → improve targeting or application quality.

**Future — Active scoring calibration:**
Use review action history to tune keyword weights. If vacancies with keyword "Python" are
consistently shortlisted and vacancies with "JavaScript" are consistently ignored, the
scoring should reflect this. This can be implemented as a simple frequency analysis:
```
for each profile, for each keyword in profile.keywords:
    shortlist_rate = shortlisted_matches_with_keyword / total_matches_with_keyword
```
Adjust weights based on shortlist_rate quartiles. This is deterministic, auditable, and
reversible. It is not v4 — it requires a meaningful history of review actions first (v5+).

---

## 7. Proposed Backlog Structure

### EPIC-13: Scoring Engine Enhancement (v4 prerequisite, CRITICAL PATH)

| Task | Description | Status |
|------|-------------|--------|
| TASK-050 | Implement real keyword overlap in `_dimension_title_match`: tokenize vacancy title, count overlapping terms with `profile.config.keywords`; normalize to 0–1 | implementation-ready |
| TASK-051 | Implement real `_dimension_company_match`: 1.0 if company in profile allowlist, 0.5 if allowlist empty, 0.0 if explicitly excluded | implementation-ready |
| TASK-052 | Add `keywords: []` and `skills: []` to `profiles.config` shape; update seed scripts and profile schema doc | implementation-ready |
| TASK-053 | Implement `_dimension_keyword_bonus`: bonus for keywords appearing in title + any parsed body/location; cap at 1.0 | implementation-ready |
| TASK-054 | Score calibration: run scoring on real data, compare score distribution before/after, verify bands are differentiated | implementation-ready (needs real data) |
| TASK-055 | Update `docs/specs/scoring-spec.md` to reflect real dimension implementations | implementation-ready |

---

### EPIC-14: Delivery Intelligence (v4, depends on EPIC-13)

| Task | Description | Status |
|------|-------------|--------|
| TASK-056 | Add `delivery_mode` to `profiles.config` schema: `alert_enabled`, `immediate_threshold`, `batch_enabled`, `batch_threshold`, `batch_interval_minutes` | blocked-by-product-decision (threshold values to decide) |
| TASK-057 | Implement `roleforge/jobs/alert.py`: read new profile_matches above threshold, send Telegram alert, log to `telegram_deliveries` with type `'alert'`, mark as alerted | blocked-by: EPIC-13, TASK-056 |
| TASK-058 | Add `'alert'` to `telegram_deliveries.delivery_type` check constraint | implementation-ready |
| TASK-059 | Implement micro-batch delivery job (optional v4.1): flush mid-band matches every N minutes | blocked-by-product-decision |
| TASK-060 | Update `docs/specs/telegram-interaction.md` to document alert mode | blocked-by: TASK-056 |

---

### EPIC-15: AI Enrichment (v4, can be v4.1)

| Task | Description | Status |
|------|-------------|--------|
| TASK-061 | Add `ai_metadata JSONB` column to `vacancies` table (migration 003 or inline) | implementation-ready |
| TASK-062 | Define AI enrichment contract: which model, which prompt, input shape, output shape | blocked-by-product-decision |
| TASK-063 | Implement `roleforge/enrichment.py`: vacancy summarizer; pin model; hash prompt; store in `ai_metadata` | blocked-by: TASK-062 |
| TASK-064 | Add enrichment step to post-scoring pipeline (high-score items only); degrade gracefully on AI failure | blocked-by: TASK-063 |
| TASK-065 | Add `ai_cost_usd` to `job_runs.summary` when enrichment runs | blocked-by: TASK-063 |
| TASK-066 | Add prompt versioning pattern: `roleforge/prompts/enrichment.py` with `PROMPT_VERSION` constant | blocked-by: TASK-062 |
| TASK-067 | Document AI governance rules in `docs/architecture.md` | implementation-ready |

---

### EPIC-16: Scheduler (v4, improves ops)

| Task | Description | Status |
|------|-------------|--------|
| TASK-068 | Evaluate APScheduler vs `schedule` (PyPI) vs Postgres-based cron table | research-only |
| TASK-069 | Implement `roleforge/scheduler.py`: runs all jobs at configured cadences from one entrypoint | blocked-by: TASK-068 |
| TASK-070 | Document scheduler setup in `docs/architecture.md` and `README.md` | blocked-by: TASK-069 |

---

### EPIC-17: Application Lifecycle (v5)

| Task | Description | Status |
|------|-------------|--------|
| TASK-071 | Define application schema: `applications`, `employer_threads`, `interview_events`; write `schema/003_applications.sql` | blocked-by-product-decision (state machine to finalize) |
| TASK-072 | Add `classified_as` column to `gmail_messages` | blocked-by: TASK-071 |
| TASK-073 | Design inbox classifier algorithm: thread signal + domain signal + subject keyword rules | research-only |
| TASK-074 | Define AI classification contract for ambiguous emails | blocked-by: TASK-073 |
| TASK-075 | Implement `roleforge/inbox_classifier.py`: classify new messages as vacancy / employer_reply / spam | blocked-by: TASK-073, TASK-074 |
| TASK-076 | Implement `roleforge/jobs/inbox_classify.py`: run classifier on new unclassified messages | blocked-by: TASK-075 |
| TASK-077 | Implement employer thread matching and `employer_threads` record creation | blocked-by: TASK-075 |
| TASK-078 | Implement application state transitions via Telegram actions | blocked-by: TASK-071 |
| TASK-079 | Implement interview event extraction (date, meeting link) from employer emails | blocked-by: TASK-077, AI contract |
| TASK-080 | Telegram UX for application update notifications (employer pinged, interview scheduled) | blocked-by: TASK-078 |
| TASK-081 | AI: company briefer prompt + storage in `interview_events.notes.ai_briefing` | blocked-by: TASK-071, AI contract |
| TASK-082 | AI: prep checklist prompt + storage in `interview_events.notes.prep_checklist` | blocked-by: TASK-071, AI contract |
| TASK-083 | Document application lifecycle spec: `docs/specs/v5-application-lifecycle.md` | blocked-by-product-decision |

---

### EPIC-18: Market Monitoring (v6, depends on EPIC-13)

| Task | Description | Status |
|------|-------------|--------|
| TASK-084 | Research HH.ru API: confirm endpoints, rate limits, ToS, field mapping | research-only |
| TASK-085 | Design monitor registry model: `config/monitors.yaml` schema + `roleforge/monitor_registry.py` | blocked-by: TASK-084 |
| TASK-086 | Implement HH.ru adapter: `roleforge/monitors/hh.py` → fetches, paginates, emits standard candidates | blocked-by: TASK-085 |
| TASK-087 | Implement `roleforge/jobs/monitor_poll.py`: reads registry, runs enabled monitors, logs to job_runs | blocked-by: TASK-086 |
| TASK-088 | Add `MONITOR_INTAKE_ENABLED` kill-switch; per-monitor `enabled` in YAML | blocked-by: TASK-085 |
| TASK-089 | Add `salary_structured JSONB` to `vacancies` for structured salary data from monitors | blocked-by-product-decision |
| TASK-090 | Extend scoring to use `salary_structured` if present (salary range filter in hard_filters) | blocked-by: TASK-089, EPIC-13 |
| TASK-091 | Document HH.ru ToS acceptance and rate limit policy in `docs/architecture.md` | blocked-by: TASK-084 |
| TASK-092 | Write `docs/specs/v6-market-monitoring.md` | blocked-by: TASK-084 |

---

### EPIC-19: Web UI (v7, depends on v4+v5)

| Task | Description | Status |
|------|-------------|--------|
| TASK-093 | Define web UI scope: what stays in Telegram vs what moves to web; write `docs/specs/v7-web-ui.md` | blocked-by-product-decision |
| TASK-094 | Add FastAPI + Jinja2 + HTMX scaffold: `roleforge/web/` package | blocked-by: TASK-093 |
| TASK-095 | Implement auth middleware: Bearer token from env/keyring | blocked-by: TASK-094 |
| TASK-096 | Analytics dashboard: match counts by profile/week, score distribution, state funnel | blocked-by: TASK-094 |
| TASK-097 | Queue browser: full queue table, sortable, multi-select bulk state update | blocked-by: TASK-094 |
| TASK-098 | Profile editor: view/edit `profiles.config` JSON (keywords, filters, delivery_mode) | blocked-by: TASK-094 |
| TASK-099 | System health panel: job_runs log, last-N per job type, status indicators | blocked-by: TASK-094 |
| TASK-100 | Application workspace: timeline view (requires v5 schema) | blocked-by: EPIC-17, TASK-094 |
| TASK-101 | Source management: view/enable/disable feeds and monitors | blocked-by: TASK-094, EPIC-18 |

---

### EPIC-20: Observability and Infrastructure (cross-cutting)

| Task | Description | Status |
|------|-------------|--------|
| TASK-102 | Add JSON structured logging to stdout using Python `logging` + JSON formatter | implementation-ready |
| TASK-103 | Add consecutive-failure admin alert: Telegram message to `TELEGRAM_ADMIN_CHAT_ID` if job fails 3+ times | implementation-ready |
| TASK-104 | Add `ai_cost_usd` to job_runs.summary documentation | blocked-by: EPIC-15 |
| TASK-105 | Monthly cost report query: document in `docs/specs/cost-governance.md` | implementation-ready |

---

## 8. Architecture Recommendation

### 8.1 Layered architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ SOURCE LAYER                                                                 │
│  gmail_poll (5-min) │ feed_poll (hourly) │ monitor_poll (per-monitor cadence)│
│  ↓                    ↓                    ↓                                 │
│  gmail_messages     │ normalized candidates (no raw store)                  │
└────────────────────────────────┬────────────────────────────────────────────┘
                                 ↓
┌────────────────────────────────┴────────────────────────────────────────────┐
│ INGESTION / NORMALIZE / DEDUP LAYER                                          │
│  normalize_candidate → group_by_dedup_key → persist_deduped                 │
│  vacancy_observations (gmail_message_id or feed_source_key)                 │
│  vacancies (canonical, deduped)                                              │
└────────────────────────────────┬────────────────────────────────────────────┘
                                 ↓
┌────────────────────────────────┴────────────────────────────────────────────┐
│ SCORING / INTELLIGENCE LAYER                                                 │
│  apply_hard_filters → compute_score (keyword-based dimensions)               │
│  profile_matches (score, explainability, review_rank, state)                 │
│  AI enrichment (optional, post-scoring, high-score only) → vacancies.ai_metadata│
└────────────────────────────────┬────────────────────────────────────────────┘
                                 ↓
┌────────────────────────────────┴────────────────────────────────────────────┐
│ DELIVERY LAYER                                                               │
│  delivery_router:                                                             │
│    score ≥ immediate_threshold + alert_enabled → alert job → Telegram alert  │
│    score ≥ batch_threshold + batch_enabled → batch queue → Telegram batch    │
│    default → digest (daily scheduled)                                        │
│  review queue (pull-based, Telegram)                                         │
│  telegram_deliveries, review_actions                                         │
└────────────────────────────────┬────────────────────────────────────────────┘
                                 ↓
┌────────────────────────────────┴────────────────────────────────────────────┐
│ OPPORTUNITY / LIFECYCLE LAYER (v5)                                           │
│  inbox_classifier → employer_threads                                         │
│  applications, interview_events                                              │
│  Telegram application update notifications                                   │
└────────────────────────────────┬────────────────────────────────────────────┘
                                 ↓
┌────────────────────────────────┴────────────────────────────────────────────┐
│ OPERATOR CONTROL LAYER (v7)                                                  │
│  FastAPI + Jinja2 + HTMX                                                     │
│  Analytics │ Queue browser │ Profile editor │ System health │ App workspace │
└────────────────────────────────┬────────────────────────────────────────────┘
                                 ↓
┌────────────────────────────────┴────────────────────────────────────────────┐
│ POSTGRES (single source of truth, everything above reads/writes here)        │
│  profiles, gmail_messages, vacancies, vacancy_observations,                  │
│  profile_matches, review_actions, telegram_deliveries, job_runs             │
│  + (v5) applications, employer_threads, interview_events                    │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 8.2 What to keep as a monolith

The core pipeline — source intake, normalize/dedup, scoring, delivery — should remain a
single Python package (`roleforge/`). The reasons:

1. **Shared data access**: all components read/write the same Postgres tables. Separating
   them into services would require an API layer with no benefit for single-operator scale.
2. **Transaction safety**: `persist_deduped` uses explicit `conn.commit()` after each
   vacancy group. Splitting this across services would require distributed transactions.
3. **Simplicity of operations**: one process, one venv, one deployment unit. This is
   appropriate for a personal tool running on one server.

### 8.3 What to separate as distinct bounded contexts (when ready)

**Inbox classifier / application lifecycle (v5):**
Separate job (`inbox_classify`), separate module (`roleforge/inbox_classifier.py`), separate
DB tables. The classification concern is distinct from vacancy ingestion. The tables are
related (via `profile_match_id`) but the logic is independent.

**Monitor adapters (v6):**
Each monitor type lives in `roleforge/monitors/{type}.py`. Adapters are isolated; the
`monitor_poll` job orchestrates them. Adding a new monitor type does not affect existing
pipeline code.

**Web UI (v7):**
`roleforge/web/` is a separate FastAPI application within the same package. It reads the
same DB but does not share job modules. It can be run as a separate process (`uvicorn
roleforge.web.app:app`). No direct function calls between web and jobs — they communicate
via Postgres state.

### 8.4 What NOT to separate prematurely

- **Scoring engine**: deeply coupled to profiles and profile_matches. No benefit to isolating.
- **Delivery logic**: reads directly from profile_matches; tight coupling is fine.
- **Dedup/normalize**: shared utility used by multiple source jobs; extract to module (done)
  but not to service.
- **Feed registry**: file-driven YAML loader; no reason to make this a service.
- **Monitoring vs connectors**: both emit the same candidate shape and go through the same
  pipeline. No need for separate "connector service" vs "monitor service" distinction at
  this scale.

### 8.5 Monolith boundary

```
roleforge/
  gmail_reader/         # Gmail API + retry
  parser/               # deterministic extraction
  normalize.py          # normalization
  dedup.py              # dedup + persist
  scoring.py            # scoring engine (real keyword matching in v4)
  enrichment.py         # AI enrichment (v4, post-scoring only)
  digest.py             # digest formatter
  queue.py              # queue card + actions
  delivery_log.py       # telegram delivery log
  feed_registry.py      # YAML feed registry
  feed_reader.py        # feedparser wrapper
  monitor_registry.py   # YAML monitor registry (v6)
  monitors/             # per-source adapters (v6)
    hh.py
  inbox_classifier.py   # employer reply classification (v5)
  replay.py             # replay helpers
  retry.py              # generic retry + classifiers
  job_runs.py           # job_runs DB helpers
  runtime.py            # DB connection, settings, Gmail service
  prompts/              # AI prompt constants (v4)
  web/                  # FastAPI app (v7)
    app.py
    routers/
    templates/
  jobs/                 # entrypoints
    gmail_poll.py
    feed_poll.py
    monitor_poll.py     # v6
    replay.py
    digest.py
    queue.py
    alert.py            # v4
    inbox_classify.py   # v5
  scheduler.py          # optional in-process scheduler (v4)
```

---

## Appendix: Key constraints to honor in every future decision

1. **Postgres is source of truth.** If a decision requires adding a non-Postgres state
   store (Redis, Celery broker, vector DB), it must be justified explicitly. The default
   answer is "use Postgres."

2. **Every job run is logged and auditable.** New jobs must call `log_job_start` /
   `log_job_finish`. New summary fields are additive to the JSONB summary.

3. **Deterministic scoring is non-negotiable.** AI may assist (summary, classification,
   enrichment) but must not gate or determine scores. A human must be able to understand
   why a vacancy scored what it scored.

4. **Kill-switches for all intake sources.** Global env var (`*_INTAKE_ENABLED`) + per-
   source `enabled` flag. No source is always-on by default except Gmail.

5. **Schema evolution is additive.** No dropping columns, no repurposing columns.
   Migrations are numbered and applied in order.

6. **Single-operator scope.** Any feature that only makes sense for multiple users is
   out of scope. Don't build for the hypothetical second operator.

7. **Low-noise delivery.** Any new notification path (alerts, application updates,
   interview reminders) must have a clear relevance threshold and a way for the operator
   to control its sensitivity. Default: less noise, not more.
