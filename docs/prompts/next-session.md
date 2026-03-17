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

Текущее состояние после прошлой сессии:
- EPIC-13, EPIC-14, EPIC-15, EPIC-16 и EPIC-20 закрыты.
- По EPIC-18 реализован и проверен core path: TASK-084, TASK-085, TASK-086, TASK-087, TASK-088, TASK-091, TASK-092. Salary tail TASK-089/TASK-090 остаётся открытым, поэтому сам EPIC-18 ещё не закрывается.
- Scheduler реализован в `roleforge/scheduler.py` как in-process stdlib loop; `python -m roleforge.scheduler` — опциональный coordinated entrypoint.
- HH.ru market monitoring now exists via `config/monitors.yaml`, `roleforge/monitor_registry.py`, `roleforge/monitors/hh.py`, and `roleforge/jobs/monitor_poll.py`; optional salary modeling remains deferred.
- Backlog, architecture, README, deployment-runtime и manual-tasks синхронизированы. Тесты: 178 passed.

Что уже сделано:
- `docs/specs/scheduler.md` фиксирует decision record: custom in-process loop вместо APScheduler / `schedule` / Postgres cron table.
- `roleforge/scheduler.py` координирует `gmail_poll`, `feed_poll`, `alert`, `batch`, `digest`; `queue` остаётся on-demand.
- Runtime docs теперь описывают `DIGEST_AT_UTC` и scheduler cadence vars.

Что осталось следующим лучшим блоком:
- `EPIC-17` (Application Lifecycle): начать с `TASK-071` state machine decision, затем `TASK-072` onward.
- `EPIC-18` не закрывать до явного решения по `TASK-089`/`TASK-090`. Если продукт захочет salary-aware monitoring, вернуться к ним отдельным блоком.

Что пользователь должен подготовить заранее, если применимо:
- Для `EPIC-18` специальных ручных действий не нужно. Если позже пойдём в `EPIC-17`, потребуется отдельное state-machine решение по `TASK-071`.

Что сделать сначала:
1. Обновить Linear: `EPIC-16`, `TASK-068`, `TASK-069`, `TASK-070`, а также `TASK-084`, `TASK-085`, `TASK-086`, `TASK-087`, `TASK-088`, `TASK-091`, `TASK-092` в Done.
2. Оставить `EPIC-18` открытым, пока не решены `TASK-089` и `TASK-090`.
3. Следующим безопасным блоком начать `EPIC-17` с `TASK-071` decision / schema research.
4. Прогнать pytest после изменений; обновить GitHub mirror по канону.

Ограничения, которые нельзя ломать:
- Gmail-only MVP
- Postgres-first
- Telegram digest + review queue
- one primary AI provider in MVP
- keyring-first secrets under `service=roleforge`

После завершения:
- Обновить Linear first, затем GitHub mirror
- Оставить close-out comments
- Сгенерировать новый next-session prompt
