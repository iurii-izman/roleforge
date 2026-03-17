Работаем в репозитории RoleForge.

Сначала прочитай:
- docs/prompts/cursor-autopilot-roleforge.md
- AGENTS.md
- README.md
- docs/architecture.md
- docs/roadmap.md
- docs/backlog/roleforge-backlog.json
- docs/manual-tasks.md
- docs/specs/scheduler.md
- docs/specs/deployment-runtime.md
- docs/specs/v6-market-monitoring.md

Текущее состояние:
- EPIC-13, EPIC-14, EPIC-15, EPIC-16 и EPIC-20 закрыты.
- По EPIC-18 закрыты TASK-084, TASK-085, TASK-086, TASK-087, TASK-088, TASK-091, TASK-092; сам EPIC-18 остаётся открытым из-за deferred salary tail TASK-089/TASK-090.
- Scheduler реализован в `roleforge/scheduler.py` и задокументирован в `docs/specs/scheduler.md`.
- HH.ru market monitoring lives in `config/monitors.yaml`, `roleforge/monitor_registry.py`, `roleforge/monitors/hh.py`, and `roleforge/jobs/monitor_poll.py`.
- Следующий блок: EPIC-17, начиная с TASK-071 state machine + schema research.

Что сделать сначала:
1. Перевести EPIC-17 и TASK-071 в In Progress в Linear.
2. Определить минимальную application lifecycle state machine и schema plan.
3. Обновить docs/specs и architecture decision log.
4. Прогнать pytest; обновить Linear/GitHub; сгенерировать next-session prompt.

Ограничения: Gmail-only MVP; Postgres-first; one primary AI provider; AI только post-scoring.
