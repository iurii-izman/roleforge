# Manual Tasks And Execution Blocks (v4+)

Этот документ отделяет то, что можно уверенно делать на автопилоте, от продуктовых решений и ручных действий пользователя.

## Current status

- Исследование `v4+` зафиксировано в [research-v4-plus.md](/var/home/user/Projects/roleforge/docs/research-v4-plus.md).
- Канонический backlog расширен до `EPIC-20` в [roleforge-backlog.json](/var/home/user/Projects/roleforge/docs/backlog/roleforge-backlog.json).
- `EPIC-13` закрыт: scoring больше не placeholder, профили расширены, калибровка выполнена на локальных данных.
- `EPIC-20` закрыт: structured logging, admin alert и cost-governance docs реализованы и покрыты тестами.
- `TASK-056`, `TASK-058`, `TASK-057`, `TASK-059`, `TASK-060` закрыты. `EPIC-14` (v4 Delivery Intelligence) завершён: alert job, batch job, обновлён telegram-interaction.md.
- `TASK-062` (AI enrichment contract) и `TASK-067` (AI governance в architecture) закрыты; контракт в [docs/specs/ai-enrichment-contract.md](specs/ai-enrichment-contract.md).
- `EPIC-15` (AI Enrichment) реализация закрыта: TASK-061 (миграция ai_metadata), TASK-063 (enrichment.py), TASK-064 (run_enrichment_for_high_scores), TASK-065 (ai_cost_usd в summary), TASK-066 (prompts/enrichment.py).
- Следующий блок: `EPIC-16` (Scheduler) или отдельный job entrypoint для enrichment; см. [next-session.md](prompts/next-session.md).

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

Можно брать после стабилизации `EPIC-13` и `EPIC-14`.

- `TASK-068` scheduler research
- `TASK-069` scheduler implementation
- `TASK-070` runtime docs

### Block F: EPIC-17 Application Lifecycle

Большой блок, запускать только после утверждения state machine.

- `TASK-072` through `TASK-083`

Зависимости:
- `TASK-071` state machine and schema direction
- для части задач нужен AI contract из `EPIC-15`

### Block G: EPIC-18 Market Monitoring

Стартует после `EPIC-13`, но лучше после стабилизации delivery path.

- `TASK-084` HH.ru research
- `TASK-085` monitor registry
- `TASK-086` HH.ru adapter
- `TASK-087` monitor poll
- `TASK-088` kill-switch
- `TASK-091` ToS/rate-limit docs
- `TASK-092` market monitoring spec

Опциональный хвост:
- `TASK-089`
- `TASK-090`

### Block H: EPIC-19 Web UI

Не начинать до появления стабильных v4/v5 flows.

- `TASK-094` through `TASK-101`

Зависимость:
- сначала нужен `TASK-093` scope decision

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
- состояния application
- состояния employer reply / interview
- terminal states
- какие переходы идут руками через Telegram
- где нужна автоматизация, а где только assistive UX

После решения:
- можно делать `EPIC-17`

### Decision 4: Structured salary scope

Связанный backlog:
- `TASK-089`

Нужно решить:
- нужен ли `salary_structured` уже в `v6`
- какие поля минимальны
- salary входит только в filters или ещё и в scoring

После решения:
- можно делать `TASK-090`

### Decision 5: Web UI scope

Связанный backlog:
- `TASK-093`

Нужно решить:
- что остаётся Telegram-first
- что переезжает в web
- что read-only, а что editable
- нужен ли auth only for self-use или закладываем future multi-user constraints

После решения:
- можно делать `EPIC-19`

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
4. `EPIC-16` (Scheduler) или enrichment job entrypoint
5. `TASK-071` decision
6. `EPIC-17`
7. `EPIC-18`
8. `TASK-093` decision
9. `EPIC-19`
