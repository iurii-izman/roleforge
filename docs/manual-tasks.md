# Manual Tasks And Execution Blocks (v4+)

Этот документ отделяет то, что можно уверенно делать на автопилоте, от продуктовых решений и ручных действий пользователя.

## Current status

- Исследование `v4+` зафиксировано в [research-v4-plus.md](/var/home/user/Projects/roleforge/docs/research-v4-plus.md).
- Канонический backlog расширен до `EPIC-20` в [roleforge-backlog.json](/var/home/user/Projects/roleforge/docs/backlog/roleforge-backlog.json).
- Следующий implementation-спринт уже подготовлен в [next-session.md](/var/home/user/Projects/roleforge/docs/prompts/next-session.md).

## Autopilot blocks

### Block A: EPIC-13 Scoring Engine Enhancement

Можно делать на автопилоте сразу.

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

Можно делать параллельно или сразу после `EPIC-13`.

- `TASK-102` structured JSON logging
- `TASK-103` consecutive-failure admin alerts
- `TASK-105` monthly cost report doc/query

Зависимости:
- `TASK-103` требует рабочий `TELEGRAM_ADMIN_CHAT_ID`

### Block C: EPIC-14 Delivery Intelligence

Частично на автопилоте после `EPIC-13`.

- `TASK-058` add `alert` delivery type support
- `TASK-057` implement `alert.py`
- `TASK-059` micro-batch delivery
- `TASK-060` Telegram interaction spec update

Зависимость:
- сначала нужен product-decision по `TASK-056`

### Block D: EPIC-15 AI Enrichment

Автопилот возможен после решения по контракту ИИ.

- `TASK-061` add `ai_metadata`
- `TASK-063` enrichment module
- `TASK-064` post-scoring enrichment step
- `TASK-065` `ai_cost_usd` in job summaries
- `TASK-066` prompt versioning
- `TASK-067` AI governance docs

Зависимость:
- сначала нужен contract по `TASK-062`

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

Нужно решить:
- нужен ли instant alert path в `v4`
- какой `immediate_threshold`
- нужен ли micro-batch path
- какой `batch_threshold`
- какой `batch_interval_minutes`
- что остаётся ролью digest

После решения:
- можно делать `EPIC-14`

### Decision 2: AI enrichment contract

Связанный backlog:
- `TASK-062`

Нужно решить:
- какой provider/model использовать
- какие поля ИИ генерирует
- на каких score bands enrichment включается
- месячный budget / cost ceiling
- fallback при ошибке ИИ

После решения:
- можно делать `EPIC-15`

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

1. `EPIC-13`
2. `EPIC-20` quick wins
3. `TASK-056` decision
4. `EPIC-14`
5. `TASK-062` decision
6. `EPIC-15`
7. `EPIC-16`
8. `TASK-071` decision
9. `EPIC-17`
10. `EPIC-18`
11. `TASK-093` decision
12. `EPIC-19`
