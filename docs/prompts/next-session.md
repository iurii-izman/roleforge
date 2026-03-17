Работаем в репозитории RoleForge.

Сначала прочитай:
- docs/prompts/cursor-autopilot-roleforge.md
- AGENTS.md
- README.md
- docs/architecture.md
- docs/roadmap.md
- docs/research-v4-plus.md
- docs/backlog/roleforge-backlog.json
- docs/manual-tasks.md
- docs/specs/scheduler.md
- docs/specs/deployment-runtime.md
- docs/specs/job-runs-logging.md
- docs/specs/v6-market-monitoring.md

Текущее состояние после прошлой сессии:
- EPIC-13, EPIC-14, EPIC-15, EPIC-16 и EPIC-20 закрыты.
- По EPIC-18 закрыты TASK-084, TASK-085, TASK-086, TASK-087, TASK-088, TASK-091, TASK-092. EPIC-18 остаётся открытым только из-за deferred salary tail TASK-089/TASK-090.
- Scheduler реализован в `roleforge/scheduler.py` как in-process stdlib loop; `python -m roleforge.scheduler` — опциональный coordinated entrypoint.
- HH.ru market monitoring now exists via `config/monitors.yaml`, `roleforge/monitor_registry.py`, `roleforge/monitors/hh.py`, and `roleforge/jobs/monitor_poll.py`.
- Backlog, architecture, README, deployment-runtime и manual-tasks синхронизированы. Тесты: 178 passed.

Следующий рабочий блок:
- `EPIC-17` (Application Lifecycle), начиная с `TASK-071`.
- Сначала нужно определить state machine и минимальную data model для applications / employer threads / interview events.

Что нужно сделать:
1. Прочитать research и текущие runtime constraints.
2. Реализовать `TASK-071`: определить application lifecycle state machine и подготовить схему для `schema/004_application_lifecycle.sql` или следующей согласованной миграции.
3. Если state machine и schema становятся достаточно ясными, подготовить groundwork для `TASK-072` (classification marker в `gmail_messages`), но не уходить глубоко в classifier implementation.
4. Обновить docs/specs для v5 lifecycle и задокументировать decisions в `docs/architecture.md`.
5. Обновить Linear first, затем GitHub mirror.

Что пользователь должен подготовить заранее, если применимо:
- Для `TASK-071` можно идти без user input, если получится выбрать минимальную single-user state machine.
- Если по ходу работы всплывёт несколько равноценных вариантов application states, выбрать самый простой, Postgres-first, Telegram-compatible вариант и зафиксировать его в docs.

Что сделать сначала:
1. Перевести `EPIC-17` и `TASK-071` в `In Progress` в Linear.
2. Изучить `docs/research-v4-plus.md` по v5 lifecycle, затем текущее schema/runtime состояние.
3. Подготовить минимальную lifecycle spec и migration plan.
4. После изменений прогнать pytest и синхронизировать трекеры.

Ограничения, которые нельзя ломать:
- Gmail-only MVP
- Postgres-first
- Telegram digest + review queue
- one primary AI provider in MVP
- keyring-first secrets under `service=roleforge`
- Не закрывать `EPIC-18`, пока не сделаны `TASK-089` и `TASK-090`
- Не уходить в full classifier / interview automation до утверждения lifecycle state machine

После завершения:
- Обновить Linear first, затем GitHub mirror
- Оставить close-out comments
- Сгенерировать новый next-session prompt
