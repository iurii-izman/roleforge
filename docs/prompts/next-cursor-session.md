# Next Cursor Session (post–TASK-048 / TASK-049)

Работаем в репозитории RoleForge.

Сначала прочитай:
- `docs/prompts/cursor-autopilot-roleforge.md`
- `AGENTS.md`
- `README.md`
- `docs/architecture.md`
- `docs/product-brief.md`
- `docs/roadmap.md`
- `docs/backlog/roleforge-backlog.json`
- `docs/backlog/README.md`
- `docs/bootstrap-access.md`
- `docs/specs/gmail-intake-spec.md`
- `docs/specs/deployment-runtime.md`
- `docs/specs/v2-profiles-and-queue.md`
- `docs/specs/v3-feeds-and-connectors.md`
- `schema/README.md`
- `.env.example`

## Текущее состояние после TASK-048 и TASK-049 (EPIC-12 v3.2)

- **MVP** и **EPIC-10 / EPIC-11** без изменений (Gmail + feeds, v2 профили, feed registry).
- **EPIC-12 (v3.2):** контракт коннекторов и первые кандидаты задокументированы (реализация не добавлялась).
  - **Контракт (TASK-048):** тот же candidate shape, что у Gmail/feeds; источник коннекторов — `feed_source_key` с префиксом `connector:{connector_id}:{external_id}`; без новых таблиц. Enable/disable: `CONNECTOR_INTAKE_ENABLED` + per-connector `enabled` в будущем реестре.
  - **Кандидаты (TASK-049):** 1) Greenhouse (приоритет), 2) Lever; реализация — только после метрик MVP и решения продукта.
  - Риски, ограничения и rollout path: `docs/specs/v3-feeds-and-connectors.md` §6.
- Обновлены: `docs/specs/v3-feeds-and-connectors.md`, `docs/architecture.md`, `docs/manual-tasks.md`, этот файл.

## Что делать в следующую очередь

1. Проверить репо: `python -m unittest discover -s tests -p "test_*.py" -v`.
2. Закрыть TASK-048 и TASK-049 в Linear и GitHub (контракт и кандидаты готовы; implementation по решению продукта).
3. Дальше по приоритету: реализация реестра коннекторов и первого адаптера (Greenhouse) при unblock; или точечные v2 доработки (queue undo, digest trends).

## Операционные заметки

Подробно: **[docs/manual-tasks.md](../manual-tasks.md)**. Кратко:

1. Держать `profiles` откалиброванными; периодически `report_profile_stats.py --days 7`.
2. EPIC-12: контракт определён; не добавлять код коннекторов до go-ahead и метрик.

## Ограничения

- Gmail — основной path; опционально feeds. Коннекторы — только после стабилизации и явного решения; без новых таблиц в v3.2.

## После завершения следующей сессии

- Обновить Linear, затем GitHub mirror.
- Перезаписать этот файл по фактическому результату.
