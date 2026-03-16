# Next Cursor Session (post–v2.1)

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

## Текущее состояние после EPIC-10

- **MVP** завершён; эпики EPIC-01 … EPIC-09 закрыты в Linear и GitHub.
- **EPIC-10** (TASK-044, TASK-045) реализован, валидирован тестами и должен считаться закрытым:
  - v2 профили: `scripts/seed_profiles_v2.py` — `default_mvp`, `primary_search`, `stretch_geo` (intents и локации задокументированы в v2 spec).
  - Queue UX v2: позиция в очереди, имя профиля, «Why in queue» по explainability.
  - Digest v2: score bands (high/medium/low) и state counts в одной строке по профилю.
  - Аналитика: `scripts/report_profile_stats.py` с `--days`/`--since`; в выводе есть `new_in_window`, `high_score_applied`; в v2 spec добавлены ad-hoc SQL примеры.
- **v2.1 polish** сделан: калибровка дефолтов профилей, расширение аналитики, preset ideas и SQL examples в `docs/specs/v2-profiles-and-queue.md`, тесты (`92 passed` через `unittest`), обновлены README и `docs/mvp-verification.md` (v2 опциональные шаги).

## Что делать в следующую очередь

1. Проверить репо: `python -m unittest discover -s tests -p "test_*.py" -v` (ожидается `92 tests`).
2. При необходимости: откалибровать профили под реальный поиск (БД или правки в `seed_profiles_v2.py`), затем `seed_profiles_v2.py` + `run_scoring_once.py`.
3. Основной рекомендованный следующий блок: **EPIC-11 (v3.1 Feed Expansion)**.
4. Если открывается новый реальный pain-point в Telegram UX, допускается короткий detour на `v2` follow-up: undo в очереди, digest trends, threshold tuning.

## Операционные заметки

Подробно: **[docs/manual-tasks.md](../manual-tasks.md)**. Кратко:

1. Держать `profiles` откалиброванными под реальный поиск.
2. Периодически смотреть `report_profile_stats.py --days 7`.
3. Для `EPIC-11` сначала зафиксировать priority sources, feed registry и kill-switch.
4. Для `EPIC-12` не стартовать работу, пока не определён общий connector contract.

## Ограничения

- Gmail-only MVP; Postgres-first; Telegram digest + queue; без новых таблиц для v2; без RSS/feeds/official connectors до явного решения; Telegram text-first.

## После завершения следующей сессии

- Обновить Linear first, затем GitHub mirror.
- Оставить close-out comments при закрытии задач.
- Перезаписать этот файл (`docs/prompts/next-cursor-session.md`) по фактическому результату.
