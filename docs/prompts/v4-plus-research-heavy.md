# V4+ Research-Heavy Audit Prompt

Use this prompt for a research-first planning session whose goal is to deeply audit the current RoleForge system and design a realistic, architecture-aware roadmap for v4 and later phases without jumping into implementation.

---

## Prompt

Работаем в репозитории **RoleForge**.

Твоя задача: провести **максимально глубокий research-heavy аудит** текущего состояния продукта, архитектуры, UX, data model, delivery model и operational model, а затем подготовить **связанный стратегический план развития на v4 и последующие итерации**.

Это не implementation sprint.
Это не “давай накидаем фич”.
Это **исследовательская, архитектурная и продуктовая сессия**, результат которой должен помочь понять:

- куда продукт логично развивать дальше,
- какие направления действительно усиливают систему,
- какие направления выглядят соблазнительно, но опасны,
- какие шаги реально совместимы с философией проекта,
- как сформировать следующий backlog без архитектурного хаоса.

## 1. Режим работы

Работай в режиме:

- **research-first**
- **audit-first**
- **architecture-first**
- **tradeoff-driven**
- **without implementation by default**

Не добавляй код, если это не требуется для оформления planning artefacts.
Если обновляешь репозиторий, то только документацию planning-уровня.

## 2. Сначала изучи текущее состояние системы

Обязательно прочитай:

- `AGENTS.md`
- `README.md`
- `docs/architecture.md`
- `docs/product-brief.md`
- `docs/roadmap.md`
- `docs/manual-tasks.md`
- `docs/mvp-verification.md`
- `docs/specs/gmail-intake-spec.md`
- `docs/specs/parser-behavior.md`
- `docs/specs/vacancy-schema.md`
- `docs/specs/profile-schema.md`
- `docs/specs/scoring-spec.md`
- `docs/specs/telegram-interaction.md`
- `docs/specs/idempotency-and-replay.md`
- `docs/specs/job-runs-logging.md`
- `docs/specs/retry-and-fallback-policy.md`
- `docs/specs/v2-profiles-and-queue.md`
- `docs/specs/v3-feeds-and-connectors.md`
- `schema/001_initial_mvp.sql`
- `schema/002_feed_observations.sql`

И посмотри ключевые runtime/доменные модули:

- `roleforge/jobs/gmail_poll.py`
- `roleforge/jobs/feed_poll.py`
- `roleforge/jobs/replay.py`
- `roleforge/jobs/digest.py`
- `roleforge/jobs/queue.py`
- `roleforge/dedup.py`
- `roleforge/scoring.py`
- `roleforge/queue.py`
- `roleforge/digest.py`
- `roleforge/feed_registry.py`
- `roleforge/feed_reader.py`
- `roleforge/parser/*`
- `roleforge/gmail_reader/*`

Нельзя строить выводы, которые противоречат текущему коду и docs.

## 3. Ключевая установка

RoleForge надо усиливать **как зрелую single-operator job intelligence system**, а не превращать в generic enterprise monster.

Сохраняй и уважай:

- **Postgres-first source of truth**
- **low-noise delivery**
- **deterministic-first pipeline**
- **AI only where ROI is explicit**
- **replayable / auditable state**
- **modular evolution instead of rewrite**
- **operator trust and explainability**

Если предлагаешь отойти от этого, обязательно объясни:

- зачем,
- что выигрываем,
- что теряем,
- почему это всё ещё разумно.

## 4. Что именно нужно исследовать

Нужно не просто “расписать версии”, а исследовать **пространство возможного развития продукта**.

Исследуй следующие направления.

### A. v4 — Near-real-time intelligence instead of digest-first

Исходная идея:

- письмо / источник приходит,
- система быстро делает intake,
- проводит нормализацию, dedup, scoring, explainability, AI-assisted analysis,
- и присылает результат в Telegram в near-real-time или short batching режиме.

Нужно исследовать:

- насколько это совместимо с low-noise philosophy,
- какие существуют delivery modes:
  - instant
  - near-real-time
  - micro-batch every N minutes
  - threshold-triggered
  - digest fallback
- как не превратить Telegram в шум,
- как меняются thresholds, buckets и score bands,
- как может выглядеть dual-mode delivery:
  - high urgency immediately
  - medium in short batch
  - low only in digest
- какой scheduling model оптимален:
  - pure polling
  - pseudo-event-driven
  - hybrid
- где нужен AI:
  - enrichment
  - summary
  - decision support
  - confidence calibration
- где deterministic rules обязаны остаться основой.

### B. v5 — Employer replies, interview lifecycle, preparation workflow

Исходная идея:

- вакансия была зафиксирована,
- оператор откликнулся,
- позже приходят письма от работодателя,
- система распознаёт это как continuation opportunity,
- помогает фиксировать timeline,
- помогает с calendar,
- помогает с interview prep.

Нужно исследовать:

- какой должен быть application/opportunity model,
- как матчить письма работодателя к вакансии/компании/отклику,
- какие state transitions понадобятся,
- нужен ли отдельный bounded context:
  - applications
  - employer threads
  - interviews
  - prep dossiers
- как хранить calendar-related state,
- как отличать:
  - HR ping
  - scheduling email
  - interview confirmation
  - rejection
  - offer signal
- как и где ИИ реально полезен:
  - summarization
  - extracting next actions
  - calendar parsing
  - preparation checklist
  - company/interviewer briefing.

### C. v6 — Active market monitoring beyond email

Исходная идея:

- система не только читает входящие письма, но и сама проверяет новые вакансии с внешних площадок,
- фильтрует,
- оценивает,
- отправляет подходящее в Telegram.

Нужно исследовать:

- какие классы источников существуют:
  - official APIs
  - feeds
  - semi-structured public pages
  - search result pages
  - marketplace-like aggregators
- как встроить это в текущую source model,
- как начинать с `HH.ru` без архитектурной ловушки,
- как сравнить варианты:
  - official API
  - HTML polling
  - hybrid strategy
  - email-assisted fallback
- legal / maintenance / data quality tradeoffs,
- какой source governance model нужен,
- как расширять от `HH.ru` к другим сайтам не через ad-hoc spaghetti connectors,
- как проектировать abstraction:
  - feed
  - connector
  - monitor
  - search source
  - polling adapter
  - normalized source event.

### D. v7 — Unified operator console / web layer

Исходная идея:

- единое окно,
- мониторинг и управление системой,
- видимость всех этапов,
- статистика,
- критерии оценки,
- мониторинг источников, вакансий, откликов, интервью, календаря.

Нужно исследовать:

- какой реальный scope полезен для single operator,
- что должно остаться в Telegram,
- что имеет смысл перенести в web UI,
- какой UI реально нужен:
  - console
  - dashboard
  - operations panel
  - review workspace
  - application/interview workspace
- какие контексты в UI read-only,
- какие editable,
- нужна ли аутентификация в первой версии web UI,
- нужен ли backend API слой и какой именно,
- стоит ли делать UI как internal tool first,
- какой MVP для web-интерфейса, а что отложить.

## 5. Обязательно исследуй не только фичи, но и системные напряжения

Отдельно проанализируй:

- schema pressure,
- state model complexity growth,
- source sprawl risk,
- config sprawl risk,
- job orchestration complexity,
- replayability erosion risk,
- AI prompt/version drift,
- Telegram UX overload,
- observability debt,
- legal and compliance exposure,
- operator cognitive overload.

Нужно понять не только “что можно добавить”, но и “что может сломать систему”.

## 6. Требуемый формат результата

Итог должен быть подробным и структурированным.

Подготовь следующие разделы.

### 6.1 Current-State Audit

Сделай честный аудит текущего продукта:

- что уже реально работает,
- что является strongest foundation,
- что сейчас bottleneck,
- какие архитектурные решения уже доказали свою полезность,
- где есть хрупкость,
- где возможен controlled expansion,
- какие продуктовые assumptions уже устарели или близки к пересмотру.

### 6.2 Strategic Product Diagnosis

Ответь на вопросы:

- чем RoleForge уже является сегодня,
- чем RoleForge не должен становиться,
- в чём его уникальная product logic,
- какой “core loop” у продукта сейчас,
- каким должен стать core loop в v4+.

### 6.3 Future Product Map

Сформируй целевую картину:

- как продукт эволюционирует от Gmail-first vacancy triage
- к opportunity intelligence / interview support / active monitoring / operator console

Но сделай это поэтапно, без magic leap.

### 6.4 Version Research: v4, v5, v6, v7

Для каждой версии обязательно дай:

- **goal**
- **operator value**
- **workflow**
- **architectural impact**
- **data model impact**
- **AI role**
- **deterministic role**
- **ops impact**
- **main risks**
- **what unlocks it**
- **what should be deferred**

### 6.5 Alternatives And Tradeoffs

Там, где есть развилки, обязательно сравни варианты.

Например:

- digest-first vs near-real-time alerting
- unified source job vs per-source jobs
- web UI later vs web UI earlier
- connector-first vs market-monitor-first
- application tracking inside core DB vs separate bounded context
- calendar sync lightweight vs full interview workflow engine

Для каждого сравнения:

- опиши плюсы,
- минусы,
- скрытые costs,
- рекомендованный выбор.

### 6.6 Cross-Cutting Workstreams

Отдельно выдели workstreams, которые будут пересекать все версии:

- data model evolution
- runtime/orchestration
- observability
- security/privacy
- AI governance
- cost governance
- legal/compliance
- UX consistency
- analytics and learning loops

### 6.7 Proposed New Backlog Structure

Сформируй черновик нового backlog после текущего завершённого цикла.

Нужно:

- предложить новые epics,
- для каждого epic дать задачи,
- пометить:
  - research-only
  - implementation-ready
  - blocked-by-product-decision
  - blocked-by-legal/ops

Желательно сделать это в стиле, который потом можно прямо использовать для Linear/GitHub.

### 6.8 Architecture Recommendation

Собери единый recommended architecture direction:

- ingestion layer
- source governance layer
- scoring/intelligence layer
- opportunity/interview layer
- delivery layer
- operator UI layer
- analytics/control layer

Укажи:

- что оставить монолитом,
- что выделять в отдельные bounded contexts,
- что не надо выделять слишком рано.

## 7. Уровень глубины

Нужен ответ не на 2 страницы.
Нужен **действительно глубокий** материал, который можно использовать как основу planning-doc.

Подход:

- меньше лозунгов,
- больше reasoning,
- больше связей между слоями,
- больше реальных tradeoffs,
- больше продуманной последовательности развития.

## 8. Стиль мышления

Думай как:

- сильный product architect,
- systems designer,
- operator workflow designer,
- pragmatic technical strategist.

Избегай:

- generic startup clichés,
- over-engineering,
- “давайте сделаем platform for everything”,
- решений, не совместимых с текущим кодом и философией.

## 9. Что можно обновить в репозитории по итогам

Если итог качественный, оформи выводы в docs:

- `docs/roadmap.md`
- `docs/architecture.md`
- новый planning doc, например:
  - `docs/research-v4-plus.md`
  - или `docs/strategic-roadmap-v4-plus.md`
- `docs/prompts/next-cursor-session.md`

Но не реализуй сами фичи без отдельного запроса.

## 10. Definition of Done

Сессия завершена только если:

- проведён глубокий аудит current state,
- проработаны `v4`, `v5`, `v6`, `v7`,
- выделены architectural options и tradeoffs,
- предложена coherent future architecture,
- составлен draft backlog structure,
- обновлены planning docs в repo.

Работай глубоко, последовательно и без поверхностных общих слов.

