Работаем в репозитории RoleForge.

Сначала прочитай:
- docs/prompts/cursor-autopilot-roleforge.md
- AGENTS.md
- README.md
- docs/architecture.md
- docs/product-brief.md
- docs/roadmap.md
- docs/backlog/roleforge-backlog.json
- docs/backlog/README.md
- docs/bootstrap-access.md
- docs/specs/gmail-intake-spec.md
- docs/specs/deployment-runtime.md
- docs/specs/v2-profiles-and-queue.md
- docs/specs/v3-feeds-and-connectors.md
- schema/README.md
- .env.example

Текущее состояние после прошлой сессии:
- Доступы к GitHub, Linear, Gmail, Telegram, AI и Postgres подтверждены и проверены через keyring и gh.
- Все прежние User Input-задачи по доступам, OAuth, выбору меток/провайдера/каденса и хостинга переведены в Done в Linear.
- Блок EPIC-03 / TASK-011–TASK-014 (Gmail intake spec, gmail_reader, персистенция и retry) реализован и синхронизирован между Linear и GitHub.
- EPIC-09 / TASK-041–TASK-043 реализован на уровне документации: задокументирован контракт окружения и деплоя, маппинг секретов из keyring в hosted runtime и минимальные требования к Postgres.

Что уже сделано:
- TASK-004, TASK-005, TASK-006, TASK-009, TASK-010, TASK-015, TASK-026, TASK-031, TASK-040 переведены в Done в Linear, так как решения и доступы фактически готовы.
- TASK-011 (Gmail-only intake spec) доведён до Accepted, спецификация лежит в docs/specs/gmail-intake-spec.md.
- TASK-012 (gmail_reader around messages.list/messages.get) реализован в roleforge/gmail_reader/reader.py, покрыт тестами tests/test_gmail_reader.py.
- TASK-013/TASK-014 закрывают персистенцию и retry; gmail_reader.store и gmail_reader.retry покрыты тестами (tests/test_gmail_store.py).
- TASK-041–TASK-043 (EPIC-09 Deployment and Runtime) реализованы через:
  - docs/specs/deployment-runtime.md — Deployment and Runtime Contract (env, секреты, Postgres минимумы, entrypoints).
  - обновлённый блок "Deployment and Runtime (EPIC-09)" в docs/architecture.md.
  - обновлённый schema/README.md с требованиями к Postgres и бэкапам.
  - обновлённый .env.example с явным контрактом переменных окружения для локального и hosted runtime.
- GitHub mirrors для EPIC-03 (TASK-011–TASK-014) синхронизированы; для EPIC-09 предполагается, что связанный issue/Project item отражает новое состояние (проверь и обнови при необходимости).
- Для post-MVP эпиков:
  - EPIC-10 (v2 Enhancements): добавлен v2-спек docs/specs/v2-profiles-and-queue.md, который раскрывает TASK-044/TASK-045 (расширенные профили, улучшенный queue UX и базовая аналитика) без смены MVP-схемы.
  - EPIC-11 и EPIC-12 (v3.1/v3.2): добавлен v3-спек docs/specs/v3-feeds-and-connectors.md, который описывает feed registry/kill-switch и connector-контракт (TASK-046–TASK-049) строго как post-MVP планы.

Что осталось следующим лучшим блоком:
- На стороне MVP:
  - human-verify задачи по схеме/профилям/фикстурам (TASK-021, TASK-035) — ревью против реальных писем и операторских запросов.
- На стороне post-MVP:
  - для EPIC-10–EPIC-12: уточнение v2/v3.x решений и, при готовности MVP, переход к реализации выбранных частей v2-прослоек (queue UX/analytics) или первых feed/connector-пилотов.

Что пользователь должен подготовить заранее, если применимо:
- Ничего критичного: решения по хостингу, бюджету и выбору AI-провайдера уже приняты; все ключи для MVP лежат в keyring (см. docs/bootstrap-access.md).
- Желательно свериться глазами с выбранным хостинг-провайдером и финальным URL-форматом для DATABASE_URL и, при использовании Telegram webhook, TELEGRAM_WEBHOOK_URL.
- Для будущего v2/v3.x: при появлении первых реальных метрик по Gmail intake/очереди — сохранить несколько типовых сценариев и запросов оператора, чтобы использовать их в качестве входа для EPIC-10–EPIC-12.

Что сделать сначала:
1. В Linear проверить, что TASK-041–TASK-043 переведены в Done, а EPIC-09 отражает фактическое состояние (если кто-то уже закрыл их с другими решениями — зафиксировать drift и завести отдельный drift-fix блок, не ломая текущие решения).
2. В GitHub Projects/Issues убедиться, что mirrors для TASK-041–TASK-043 (если есть) закрыты или переведены в done-колонку с короткими close-out комментариями по принятому контракту env/секретов/Postgres.
3. Для EPIC-10–EPIC-12 — при необходимости завести/обновить mirrors под TASK-044–TASK-049 и сослаться на новые v2/v3.x specs в описаниях.
4. Выбрать следующий максимальный когерентный блок (например, human-verify задачи по схеме/профилям или первые v2-улучшения очереди/аналитики) и развернуть план выполнения.
5. При необходимости доуточнить TELEGRAM_* и DATABASE_URL под конкретный hosted runtime, не меняя общую архитектуру (Gmail-only, Postgres-first, Telegram digest + queue, один AI-провайдер).

Ограничения, которые нельзя ломать:
- Gmail-only MVP
- Postgres-first
- Telegram digest + review queue
- one primary AI provider in MVP
- keyring-first secrets under service=roleforge

Если заблокирован:
- Если в Linear TASK-041–TASK-043 уже принудительно переведены в Done человеком с другими решениями, зафиксируй расхождение между docs и фактическим состоянием и создай отдельный drift-fix блок вместо изменения решений.
- Если обнаружится, что какой-то ключ в keyring отсутствует или локальный/hosted Postgres ещё не доступен, опиши точный недостающий секрет или шаг (domain/key или команду для поднятия БД) и продолжи с безопасной частью документации и кода, которая не требует живого подключения.

После завершения:
-- обнови Linear first (для блока задач → Done с коротким комментарием по принятым решениям и проверкам),
-- обнови GitHub mirror second (issues/Project items для этих задач, если они есть),
-- оставь close-out comments (кратко: что реализовано, где лежат ключевые specs/docs, чем проверено — тестами/фикстурами/ручной проверкой),
-- сгенерируй новый next-session prompt поверх фактического результата работы по выбранному эпіку/блоку.
