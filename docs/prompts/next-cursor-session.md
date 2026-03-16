# Next Cursor Session (post–EPIC-11)

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
- `schema/README.md`
- `.env.example`

## Текущее состояние после EPIC-11 (v3.1 Feed Expansion)

- **MVP** завершён; EPIC-01 … EPIC-09 закрыты.
- **EPIC-10** (TASK-044, TASK-045): v2 профили, queue UX, digest bands, аналитика — реализованы.
- **EPIC-11** (TASK-046, TASK-047) реализован:
  - Feed registry: `config/feeds.yaml` (id, name, url, type, enabled); `roleforge.feed_registry`.
  - Kill-switch: `FEED_INTAKE_ENABLED` (env, по умолчанию false); per-feed `enabled` в YAML.
  - Feed intake: `roleforge.feed_reader`, `python -m roleforge.jobs.feed_poll`; фиды идут в ту же normalize/dedup path; `vacancy_observations` с `feed_source_key` (schema 002).
  - Тесты: `tests/test_feed_registry.py`, `tests/test_feed_reader.py`; dedup с feed_source_key в `test_normalize_and_dedup.py`.

## Что делать в следующую очередь

1. Проверить репо: `python -m unittest discover -s tests -p "test_*.py" -v` (ожидается `111 tests`, `OK`).
2. Для feed intake: применить `schema/002_feed_observations.sql`, при необходимости добавить фиды в `config/feeds.yaml`, выставить `FEED_INTAKE_ENABLED=true`, запускать `feed_poll`.
3. Следующий блок по приоритету: **EPIC-12 (v3.2)** — контракт коннекторов и первые официальные коннекторы; или точечные v2 доработки (queue undo, digest trends).

## Операционные заметки

Подробно: **[docs/manual-tasks.md](../manual-tasks.md)**. Кратко:

1. Держать `profiles` откалиброванными под реальный поиск.
2. Периодически смотреть `report_profile_stats.py --days 7`.
3. EPIC-11 (feed registry, kill-switch, feed_poll) реализован; при необходимости — добавить фиды и включить intake.
4. Для `EPIC-12` не стартовать реализацию коннекторов, пока не определён общий connector contract.

## Ограничения

- Gmail — основной MVP path; опционально RSS/Atom через config/feeds.yaml и feed_poll. Postgres-first; Telegram digest + queue; без официальных коннекторов до v3.2; Telegram text-first.

## После завершения следующей сессии

- Обновить Linear first, затем GitHub mirror.
- Оставить close-out comments при закрытии задач.
- Перезаписать этот файл (`docs/prompts/next-cursor-session.md`) по фактическому результату.
