# Manual Tasks And Execution Blocks (v4+)

Этот документ отделяет то, что можно уверенно делать на автопилоте, от продуктовых решений и ручных действий пользователя.

## Current status

- Исследование `v4+` зафиксировано в [research-v4-plus.md](/var/home/user/Projects/roleforge/docs/research-v4-plus.md).
- Канонический backlog расширен до `EPIC-20` в [roleforge-backlog.json](/var/home/user/Projects/roleforge/docs/backlog/roleforge-backlog.json).
- `EPIC-13` закрыт: scoring больше не placeholder, профили расширены, калибровка выполнена на локальных данных.
- `EPIC-20` закрыт: structured logging, admin alert и cost-governance docs реализованы и покрыты тестами.
- `TASK-056`, `TASK-058`, `TASK-057`, `TASK-059`, `TASK-060` закрыты. `EPIC-14` (v4 Delivery Intelligence) завершён: alert job, batch job, обновлён telegram-interaction.md.
- `TASK-062` (AI enrichment contract) и `TASK-067` (AI governance в architecture) закрыты; контракт в [docs/specs/ai-enrichment-contract.md](specs/ai-enrichment-contract.md).
- `EPIC-15` (AI Enrichment) закрыта: TASK-061 (миграция ai_metadata), TASK-063 (enrichment.py), TASK-064 (run_enrichment_for_high_scores), TASK-065 (ai_cost_usd в summary), TASK-066 (prompts/enrichment.py).
- `EPIC-16` (Scheduler) закрыт: TASK-068 (research), TASK-069 (scheduler), TASK-070 (docs).
- `EPIC-18` (Market Monitoring) закрыт: core path TASK-084, TASK-085, TASK-086, TASK-087, TASK-088, TASK-091, TASK-092 реализованы; salary tail TASK-089/TASK-090 закрыт product-decision'ом — остаёмся на `salary_raw`, без `salary_structured` в текущем roadmap.
- `EPIC-17` закрыт: TASK-071..083 (включая TASK-079..082) реализованы и покрыты тестами; есть deterministic extraction + optional notify + optional AI enrichment для interview events.
- `TASK-093` закрыт: web UI scope зафиксирован как single-user operator console.
- `EPIC-19` foundation slice закрыт: TASK-094, TASK-095, TASK-096, TASK-097, TASK-098, TASK-099, TASK-101 реализованы; следующий блок — `TASK-100` application workspace timeline view.

## Autopilot blocks

### Block A: EPIC-13 Scoring Engine Enhancement

Закрыт.

- `TASK-050` real title keyword overlap
- `TASK-051` real company preference scoring
- `TASK-052` extend `profiles.config` with `keywords` and `skills`
- `TASK-053` real keyword bonus
- `TASK-054` calibration on real data
- `TASK-055` update scoring spec

Зависимости:
- нет внешних product-decisions
- нужны реальные данные для калибровки

### Block B: EPIC-20 Observability quick wins

Закрыт.

- `TASK-102` structured JSON logging
- `TASK-103` consecutive-failure admin alerts
- `TASK-104` ai_cost_usd reporting contract docs
- `TASK-105` monthly cost report doc/query

Зависимости:
- `TASK-103` требует рабочий `TELEGRAM_ADMIN_CHAT_ID`

### Block C: EPIC-14 Delivery Intelligence

Закрыт.

- `TASK-056` delivery_mode contract and defaults
- `TASK-058` add `alert` delivery type support
- `TASK-057` implement `alert.py`
- `TASK-059` micro-batch delivery job (`roleforge/jobs/batch.py`)
- `TASK-060` Telegram interaction spec update (digest/queue/alert/batch coexistence)

### Block D: EPIC-15 AI Enrichment

Закрыт.

- ~~`TASK-061`~~ add `ai_metadata` (schema/003_ai_metadata.sql)
- ~~`TASK-063`~~ enrichment module (roleforge/enrichment.py)
- ~~`TASK-064`~~ post-scoring step (run_enrichment_for_high_scores)
- ~~`TASK-065`~~ `ai_cost_usd` in job summary (returned by run_enrichment_for_high_scores)
- ~~`TASK-066`~~ prompt versioning (roleforge/prompts/enrichment.py)
- ~~`TASK-067`~~ AI governance docs — done

Опционально: отдельный job entrypoint (e.g. `python -m roleforge.jobs.enrichment`) для запуска enrichment после scoring.

### Block E: EPIC-16 Scheduler

Закрыт.

- ~~`TASK-068`~~ scheduler research
- ~~`TASK-069`~~ scheduler implementation (`roleforge/scheduler.py`)
- ~~`TASK-070`~~ runtime docs (architecture, README, deployment contract, scheduler spec)

### Block F: EPIC-17 Application Lifecycle

Decision made. Implementation slice in progress.

- ~~`TASK-072`~~ add `classified_as` to `gmail_messages` (schema/005_gmail_classified.sql, docs)
- ~~`TASK-073`~~ design deterministic inbox classifier (docs/specs/inbox-classifier.md)
- ~~`TASK-074`~~ define AI classification contract for ambiguous emails (docs/specs/ai-inbox-classification-contract.md)
- ~~`TASK-075`~~ implement roleforge/inbox_classifier.py (deterministic rules)
- ~~`TASK-076`~~ inbox_classify job (roleforge/jobs/inbox_classify.py); intake label IDs from config/env
- ~~`TASK-077`~~ employer thread matching + `employer_threads` record creation (roleforge/employer_thread_matching.py, roleforge/jobs/employer_thread_match.py)
- ~~`TASK-078`~~ application state transitions via Telegram (`roleforge.application_lifecycle`)
- ~~`TASK-079`~~ interview event extraction (deterministic-first: meeting links + best-effort datetime parsing; idempotent via `interview_events.notes.source_gmail_message_id`; job `python -m roleforge.jobs.interview_event_extract`)
- ~~`TASK-080`~~ Telegram application update notifications (job `python -m roleforge.jobs.application_notify`; disabled by default via `APPLICATION_NOTIFY_ENABLED`; auditable via `telegram_deliveries.delivery_type='application_update'`)
- ~~`TASK-081`~~ AI company briefer artifacts in `interview_events.notes.ai_briefing` (prompt-versioned, bounded; job `python -m roleforge.jobs.interview_event_ai_enrich`; disabled by default via `INTERVIEW_AI_ENRICH_ENABLED`)
- ~~`TASK-082`~~ AI prep checklist artifacts in `interview_events.notes.prep_checklist` (same job/governance)

Зависимости:
- `TASK-071` state machine and schema direction is now fixed
- для части задач нужен AI contract из `EPIC-15`

### Block G: EPIC-18 Market Monitoring

Closed. HH.ru monitoring exists as a safe, reversible sweep over the same normalized vacancy pipeline. Product decision: keep `salary_raw` only; do not add `salary_structured` or salary-aware scoring in the current roadmap.

- ~~`TASK-084`~~ HH.ru research
- ~~`TASK-085`~~ monitor registry
- ~~`TASK-086`~~ HH.ru adapter
- ~~`TASK-087`~~ monitor poll
- ~~`TASK-088`~~ kill-switch
- ~~`TASK-091`~~ ToS/rate-limit docs
- ~~`TASK-092`~~ market monitoring spec

Decision:
- ~~`TASK-089`~~ no-op by product decision: keep `salary_raw`
- ~~`TASK-090`~~ no-op by product decision: do not extend scoring with salary

### Block H: EPIC-19 Web UI

Scope decision fixed. Foundation implementation completed.

- ~~`TASK-093`~~ scope decision documented in `docs/specs/v7-web-ui.md`
- ~~`TASK-094`~~ FastAPI + Jinja2 + HTMX scaffold (`roleforge/web/`)
- ~~`TASK-095`~~ Bearer token auth middleware (env/keyring `WEB_BEARER_TOKEN`)
- ~~`TASK-096`~~ analytics dashboard (read-only, DB-backed `/analytics`)
- ~~`TASK-099`~~ system health panel (read-only `/system-health`)
- ~~`TASK-101`~~ source management view (feeds/monitors `/sources` + HTMX toggles)
- ~~`TASK-097`~~ queue browser (web `/queue-browser`, bulk actions via existing `queue.apply_review_action`)
- ~~`TASK-098`~~ profile editor (web `/profiles`, guardrails + audit via `job_runs` job_type `web_profile_edit`)
- `TASK-100` later wave (application workspace timeline)

Зависимость:
- scope decision уже принят; implementation можно начинать, когда v5 flow достаточно стабилен

## User decision blocks

Это не просто “руками сделать”, а именно решения, без которых следующие эпики будут либо шумными, либо архитектурно размазанными.

### Decision 1: Delivery thresholds and mode

Связанный backlog:
- `TASK-056`

Статус:
- решение уже принято и задокументировано в `profiles.config.delivery_mode`
- digest остаётся default path
- immediate alerts и micro-batch включаются per profile

Следствие:
- можно делать `EPIC-14`

### Decision 2: AI enrichment contract

Связанный backlog:
- `TASK-062` (closed)

Статус:
- решено и задокументировано в [docs/specs/ai-enrichment-contract.md](specs/ai-enrichment-contract.md): provider/model shortlist (OpenAI gpt-4o-mini / Anthropic Haiku), input/output contract, gating по score ≥ 0.75, timeout/retry/fallback без блокировки pipeline, cost guardrails и ai_cost_usd, prompt versioning, privacy/logging.

Следствие:
- можно делать реализацию `EPIC-15` (TASK-061, TASK-063–TASK-066)

### Decision 3: Application lifecycle state machine

Связанный backlog:
- `TASK-071`

Нужно решить:
- состояния application, employer reply / interview
- terminal states
- какие переходы идут руками через Telegram
- где нужна автоматизация, а где только assistive UX

После решения:
- можно делать `EPIC-17`

Статус:
- решено и задокументировано в [docs/specs/v5-application-lifecycle.md](specs/v5-application-lifecycle.md)
- additive schema plan: `schema/004_application_lifecycle.sql`
- AI остаётся только post-scoring / assistive, без state gating

### Decision 4: Structured salary scope

Связанный backlog:
- `TASK-089`

Статус:
- решено: `salary_structured` не вводим в текущем roadmap
- остаёмся на `salary_raw TEXT`
- salary не участвует в scoring и не добавляется в hard filters как structured field

Причина:
- низкий ROI против дополнительной schema/support complexity
- для operator context и ручного отбора текущего `salary_raw` достаточно
- если позже появится реальная потребность в salary-aware automation, это можно вернуть отдельной новой волной

### Decision 5: Web UI scope

Связанный backlog:
- `TASK-093`

Статус:
- решено и должно жить в `docs/specs/v7-web-ui.md`

Принятый scope:
- single-user only
- Bearer token auth
- Telegram остаётся primary delivery and action surface
- web нужен как operator console: analytics, system health, source management, queue browser, profile inspection/editing
- application workspace допустим, но как later wave внутри `EPIC-19`, не как стартовый обязательный блок

## Manual checks and rituals

### После любых scoring changes

```bash
cd /var/home/user/Projects/roleforge
source /var/home/user/Projects/roleforge/.venv/bin/activate
python /var/home/user/Projects/roleforge/scripts/run_scoring_once.py
```

Потом проверить распределение score SQL-запросами из `docs/prompts/next-session.md`.

### После любых profile changes

```bash
cd /var/home/user/Projects/roleforge
source /var/home/user/Projects/roleforge/.venv/bin/activate
python /var/home/user/Projects/roleforge/scripts/seed_profiles_v2.py
python /var/home/user/Projects/roleforge/scripts/run_scoring_once.py
```

### Периодический review ritual

```bash
cd /var/home/user/Projects/roleforge
source /var/home/user/Projects/roleforge/.venv/bin/activate
python /var/home/user/Projects/roleforge/scripts/report_profile_stats.py --days 7
```

## Recommended order

1. ~~`EPIC-14`~~ (closed)
2. ~~`TASK-062`~~ (closed), ~~`TASK-067`~~ (closed)
3. ~~`EPIC-15`~~ (closed)
4. ~~`EPIC-16`~~ (closed)
5. `EPIC-17`
6. `TASK-079` through `TASK-082`
7. `TASK-100`
