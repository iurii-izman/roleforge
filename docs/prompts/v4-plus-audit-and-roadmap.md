# V4+ Strategic Audit And Roadmap Prompt

Use this prompt for a planning-heavy Cursor or Codex session whose goal is to audit the current RoleForge system end-to-end and produce a coherent roadmap for v4 and later iterations.

---

## Prompt

Работаем в репозитории **RoleForge**.

Твоя задача: провести **глубокий аудит всей текущей программы** и на его основе спроектировать **связанный, архитектурно цельный и продуктово реалистичный план развития на v4 и последующие итерации**.

Это не brainstorming в отрыве от реальности. Это должен быть **серьёзный product + architecture + operations audit**, который:

- опирается на **реальное текущее состояние репозитория**,
- уважает философию проекта,
- не ломает уже принятые архитектурные решения без серьёзного обоснования,
- развивает систему постепенно, модульно и практически,
- создаёт основу для **следующего нового backlog / next phase**, а не просто список желаний.

### 1. Сначала изучи репозиторий и собери контекст

Обязательно прочитай и используй как основу:

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
- ключевые runtime entrypoints:
  - `roleforge/jobs/gmail_poll.py`
  - `roleforge/jobs/feed_poll.py`
  - `roleforge/jobs/replay.py`
  - `roleforge/jobs/digest.py`
  - `roleforge/jobs/queue.py`
- ключевые доменные модули:
  - `roleforge/gmail_reader/*`
  - `roleforge/parser/*`
  - `roleforge/dedup.py`
  - `roleforge/scoring.py`
  - `roleforge/queue.py`
  - `roleforge/digest.py`
  - `roleforge/feed_registry.py`
  - `roleforge/feed_reader.py`

Не делай предположений, которые противоречат текущему коду и документации.

### 2. Исходные принципы, которые нельзя терять

При любом предложении сохраняй ядро философии проекта:

- **Postgres-first**: Postgres остаётся главным source of truth.
- **Low-noise delivery**: Telegram должен оставаться сигналом, а не спамом.
- **Deterministic-first**: deterministic parsing, normalization, dedup и state model важнее “магии”.
- **AI only where ROI is explicit**: ИИ применяется там, где реально увеличивает signal-to-noise ratio или экономит время оператора.
- **Replayable / auditable system**: все ключевые решения, сообщения, действия и transitions должны быть проверяемыми и по возможности replayable.
- **Modularity over rewrite**: развитие идёт модульно и слоями, а не через “перепишем всё с нуля”.
- **Single-operator practicality first**: система должна в первую очередь усиливать одного продвинутого оператора, а не сразу пытаться стать enterprise ATS platform.

Если ты предлагаешь нарушить один из этих принципов, это допустимо только при явном tradeoff-анализе и сильном обосновании.

### 3. Базовые пользовательские идеи, которые надо развить в полноценные workflow

Ниже не готовые решения, а intent. Ты должен превратить их в корректные product/architecture workflows.

#### v4. Near-real-time vacancy intelligence instead of digest-first

Желаемое направление:

- письма и/или новые источники приходят,
- система за короткое время проводит intake,
- затем выполняет анализ, нормализацию, dedup, scoring, explainability и AI-assisted enrichment,
- далее в Telegram отправляется **не обязательно мгновенное**, но **почти real-time** сообщение о сильной вакансии или краткий alert-batch,
- при этом нельзя сломать low-noise philosophy.

Ты должен проработать:

- как именно меняется workflow по сравнению с digest-first подходом,
- какие режимы доставки нужны:
  - instant / near-real-time,
  - micro-batching,
  - fallback digest,
  - critical-only alerts,
- как защититься от шума,
- какие thresholds, buckets, debounce и dedup правила нужны,
- где именно нужен AI, а где deterministic logic,
- какой scheduling / job model или event model нужен,
- как это логируется, как replayable, как администрируется,
- как это будет выглядеть в Telegram UX.

#### v5. Employer replies / interview flow

Желаемое направление:

- была вакансия,
- она прошла анализ и попала в Telegram,
- оператор руками откликнулся,
- позже приходит письмо от работодателя про интервью / follow-up / next step,
- система должна распознать это как развитие existing thread/opportunity,
- сохранить артефакты,
- зафиксировать timeline,
- помочь с календарём,
- подготовить interview-prep workspace / отдельный сервис / контекст для подготовки.

Ты должен проработать:

- как матчить employer replies к original vacancy / application,
- какой state model нужен:
  - new vacancy,
  - reviewed,
  - applied,
  - employer_response,
  - interview_scheduled,
  - prep_in_progress,
  - completed / rejected / offer / archived,
- как разделить ручные и автоматические действия,
- как хранить письма работодателя, summary, attachments, structured notes,
- как интегрировать calendar,
- как строить reminders и preparation workflow,
- нужен ли отдельный interview-prep bounded context,
- как это будет отражаться в Telegram и будущем UI.

#### v6. Active vacancy monitoring outside email

Желаемое направление:

- система не только ждёт писем, но и сама периодически ищет новые объявления,
- отбрасывает явно неподходящее,
- дальше прогоняет оставшееся через уже существующую логику,
- и сильные вакансии отправляет в Telegram.

Для старта нужно продумать это **как модульную систему**, начиная с **HH.ru**.

Ты должен проработать:

- какие варианты intake реально доступны для HH.ru:
  - официальное API,
  - RSS/feeds,
  - публичные страницы,
  - email-derived alternatives,
  - hybrid подход,
- legal / stability / maintenance tradeoff,
- как не сломать философию existing connector/feed model,
- какую abstraction ввести:
  - connector registry,
  - source polling contract,
  - source capabilities matrix,
  - source health / rate-limits / retries,
- как встроить это в current schema и current jobs,
- как расширять потом на другие job sites,
- как бороться с антибот-механиками, rate limits и fragile parsing,
- как сочетать source-level prefilter и downstream scoring.

#### v7. Unified web interface / operator console

Желаемое направление:

- единое окно для мониторинга системы,
- просмотр источников, матчей, состояния, отправок, статистики,
- мониторинг и, возможно, управление criteria / profiles / thresholds,
- видимость того, что и откуда пришло,
- связка как минимум с почтой и календарём,
- управление operational состоянием проекта.

Ты должен проработать:

- нужен ли single-user operator console или multi-user admin panel,
- какие bounded contexts должны быть видны в UI:
  - intake,
  - vacancies,
  - matches,
  - opportunities/applications,
  - interviews,
  - jobs/runs,
  - deliveries,
  - analytics,
- что должно быть read-only, а что editable,
- какой backend contract нужен,
- какой frontend style/stack уместен без overbuild,
- какой MVP для web UI, а что отложить,
- как UI соотносится с Telegram, а не дублирует его бессмысленно.

### 4. Обязательный формат результата

Твой результат должен быть не просто “идеи”, а **структурированный набор artefacts**, который можно использовать как основу следующего цикла разработки.

Подготовь:

#### A. Current-State Audit

Сделай глубокий аудит текущей системы:

- что реально уже умеет продукт,
- какие сильные стороны архитектуры уже есть,
- где есть естественные точки расширения,
- где главные ограничения,
- где уже накоплен технический долг,
- какие части системы уже выглядят устойчиво,
- какие части опасно перегружать,
- какие cross-cutting concerns уже появились:
  - observability,
  - replayability,
  - config sprawl,
  - source governance,
  - AI governance,
  - UX noise,
  - schema pressure.

#### B. Future-State Product Vision

Сформулируй, чем RoleForge должен стать после v4-v7:

- не в стиле “всё и сразу”,
- а как эволюция текущего Gmail-first pipeline в более полноценную opportunity intelligence system.

Опиши:

- core product loop,
- operator journey,
- primary system entities,
- user-visible value на каждом этапе.

#### C. Versioned Roadmap: v4, v5, v6, v7

Для **каждой версии** дай:

- version goal,
- primary user outcome,
- why this version exists,
- architectural changes,
- functional modules,
- data model impact,
- integrations impact,
- AI roles,
- deterministic roles,
- risks,
- dependencies,
- rollout strategy,
- success metrics,
- what is intentionally deferred.

#### D. Blocks and Subtasks

Для **каждой версии** разбей работу минимум на:

- major development blocks / epics,
- для каждого блока — список подзадач,
- зависимости между блоками,
- что можно делать параллельно,
- что должно идти строго последовательно.

Старайся писать так, чтобы это можно было потом превратить в backlog без переизобретения.

#### E. Cross-Cutting Tracks

Отдельно выдели сквозные направления, которые нельзя забывать:

- data model evolution,
- config / secrets / runtime,
- observability / alerting / replay,
- testing strategy,
- AI prompt/version governance,
- Telegram UX evolution,
- security/privacy,
- cost control,
- legal/compliance risk for connectors and scraping,
- operator trust and explainability.

#### F. Recommended Architecture For V4+

Собери один цельный architecture section:

- какие bounded contexts / modules появятся,
- как будет выглядеть ingestion layer,
- как будет выглядеть opportunity / application / interview layer,
- как будет выглядеть delivery layer,
- как будет выглядеть future operator UI layer,
- какие новые tables / services действительно нужны, а какие нет,
- какой event / job / polling model оптимален.

Обязательно сравни варианты там, где есть неоднозначность:

- cron-style polling vs event-driven approximations,
- unified source ingestion job vs per-source jobs,
- one monolith service vs split services,
- web UI first vs Telegram-first with admin UI later.

#### G. Backlog Proposal For The Next Phase

Составь **черновой backlog** для следующего цикла после текущего завершённого проекта:

- new epics,
- tasks under each epic,
- suggested ordering,
- suggested statuses / phases,
- what is research-only,
- what is implementation-ready,
- what requires human product decision first.

### 5. Нужен не только анализ, но и продуктовая смелость

Ты можешь использовать креатив и фантазию, но:

- не превращай RoleForge в generic CRM/ATS monster,
- не добавляй экосистему ради экосистемы,
- не предлагай enterprise-heavy решения без причины,
- не уходи в “давайте построим orchestration platform”.

Нужны **умные расширения**, которые естественно вырастают из текущей системы.

Если видишь полезные дополнительные направления beyond v4-v7, можешь предложить их как:

- `v8 candidates`,
- `future research tracks`,
- `optional experiments`.

Но сначала полностью и качественно проработай `v4-v7`.

### 6. Практические требования к итоговому ответу

Твой итог должен быть:

- подробным,
- хорошо структурированным,
- на русском языке,
- архитектурно последовательным,
- без противоречий текущему коду,
- пригодным для последующего превращения в docs и backlog.

Где полезно — используй таблицы.
Где полезно — показывай ASCII workflows / sequence outlines.
Где полезно — сравнивай варианты и делай recommendation.

### 7. Что обновить в репозитории по итогам этой planning-сессии

Если итог получается качественным, оформи результат в репозитории, а не только в chat output.

Минимум:

- обнови `docs/roadmap.md` под v4+,
- обнови `docs/architecture.md`, если меняется direction,
- добавь новый planning doc, например:
  - `docs/future-roadmap-v4-plus.md`
  - или `docs/audit-and-roadmap-v4-plus.md`
- обнови `docs/prompts/next-cursor-session.md` под следующий реальный рабочий цикл.

Не реализуй фичи v4-v7 кодом в этой сессии, если на это нет отдельного явного запроса.
Это planning / audit / architecture session, а не implementation sprint.

### 8. Definition of Done for this planning session

Сессию можно считать завершённой только если:

- проведён честный аудит текущей системы,
- сформулировано будущее product direction,
- подробно проработаны v4, v5, v6, v7,
- для каждой версии выделены блоки и подзадачи,
- есть цельная архитектурная картина,
- есть понятный следующий backlog proposal,
- обновлены соответствующие docs в репозитории.

Работай глубоко, системно и без поверхностных общих слов.

