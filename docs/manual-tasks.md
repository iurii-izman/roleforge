# Ручные задачи (post–EPIC-11)

Чеклист того, что ещё может понадобиться после завершения и синхронизации EPIC-11.

---

## 1. Статус синхронизации

На 2026-03-16:

- `TASK-044` и `TASK-045` реализованы в коде и покрыты тестами.
- **TASK-046 и TASK-047 (EPIC-11 v3.1 Feed Expansion)** реализованы: feed registry (config/feeds.yaml), kill-switch (FEED_INTAKE_ENABLED), feed_poll job, schema 002 для feed_source_key в vacancy_observations. Тесты: test_feed_registry.py, test_feed_reader.py; dedup поддерживает feed_source_key.
- После проверки кодом `TASK-046` и `TASK-047` можно закрывать в GitHub и Linear вместе с `EPIC-11`.

---

## 2. Следующий блок после EPIC-11

- **EPIC-12 (v3.2):** следующий рекомендуемый блок. Официальные коннекторы — только после стабилизации Gmail и опционально feeds; контракт коннектора в `docs/specs/v3-feeds-and-connectors.md`.
- Остаться в v2: если нужны queue undo, threshold tuning или digest trends — можно делать точечные доработки.

---

## 3. Откалибровать профили под свой поиск

Базовые `v2` профили уже засеяны:

- `default_mvp`
- `primary_search`
- `stretch_geo`

Их можно подстроить под реальные вакансии и гео.

**Вариант A — правка в БД (текущие данные сохраняются):**

1. Подключиться к Postgres (например `podman exec -it roleforge-pg psql -U roleforge -d roleforge` или DBeaver).
2. Посмотреть текущий config:
   ```sql
   SELECT id, name, config FROM profiles WHERE name IN ('primary_search', 'stretch_geo');
   ```
3. Обновить `config` (JSONB): подправить `hard_filters.locations`, `hard_filters.exclude_titles`, `hard_filters.exclude_companies`, `config.min_score` под свой кейс.
4. Пересчитать матчи и ранги:
   ```bash
   python scripts/run_scoring_once.py
   ```

**Вариант B — правка в коде (для всех будущих seed):**

1. Открыть `scripts/seed_profiles_v2.py`.
2. В функциях `_build_profiles()` изменить списки `locations`, `exclude_titles`, `exclude_companies` и значения `min_score` для `primary_search` и/или `stretch_geo`.
3. Выполнить:
   ```bash
   python scripts/seed_profiles_v2.py
   python scripts/run_scoring_once.py
   ```

---

## 4. Feeds (EPIC-11) — реализовано

- **Реестр:** `config/feeds.yaml` (id, name, url, type: rss|atom, enabled). Файловый; без новой таблицы.
- **Kill-switch:** глобальный `FEED_INTAKE_ENABLED` (по умолчанию false); по фиду — `enabled: true/false` в YAML.
- **Запуск:** `python -m roleforge.jobs.feed_poll`; перед первым прогоном применить `schema/002_feed_observations.sql`.
- **EPIC-12:** контракт коннектора и приоритет официальных коннекторов — по готовности метрик и решению продукта.

---

## 5. Регулярный ритуал (по желанию)

- Раз в неделю (или после накопления матчей) запускать:
  ```bash
  python scripts/report_profile_stats.py --days 7
  ```
  По выводу решать: менять ли пороги/фильтры профилей, добавлять ли новые.

- При изменении профилей или добавлении данных всегда после этого запускать:
  ```bash
  python scripts/run_scoring_once.py
  ```
