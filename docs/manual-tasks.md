# Ручные задачи (post–EPIC-10)

Чеклист того, что ещё может понадобиться после завершения и синхронизации EPIC-10.

---

## 1. Статус синхронизации

На 2026-03-16:

- `TASK-044` и `TASK-045` реализованы в коде и покрыты тестами.
- GitHub mirror для `TASK-044`, `TASK-045` и `EPIC-10` должен быть закрыт и переведён в `Done`.
- В Linear child tasks уже были в `Done`; если эпик `EPIC-10` ещё не закрыт, его можно закрыть после проверки child tasks.

---

## 2. Выбрать следующий эпик

Рекомендованный следующий блок: **EPIC-11 (v3.1 Feed Expansion)**.

- Почему не `EPIC-12`:
  сначала лучше определить общий feed/registry path и kill-switch, а уже потом вводить официальные коннекторы поверх этого контракта.
- Когда имеет смысл остаться в `v2`:
  если появится явная боль по queue undo, threshold tuning или digest trends на реальных данных.

Если продуктовых вводных пока мало, оставляем `EPIC-11` в приоритете, но начинаем с research/contract части, а не с широкой реализации intake.

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

## 4. Product-решения по feeds/connectors (если стартуете EPIC-11 или EPIC-12)

Когда будете готовы к расширению источников, сначала зафиксируйте:

- **EPIC-11:** приоритет источников (какие RSS/feeds первыми), модель feed registry и kill-switch, способ хранения конфига фидов.
- **EPIC-12:** контракт коннектора (что должен уметь коннектор, как подключать новые источники), приоритет первых официальных коннекторов.

Эти пункты в бэклоге помечены как research/placeholder; для реализации нужны явные решения.

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
