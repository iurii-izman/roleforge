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
- docs/specs/job-runs-logging.md
- docs/specs/cost-governance.md
- docs/specs/v3-feeds-and-connectors.md

Текущее состояние:
- `EPIC-13` закрыт.
- `EPIC-14` закрыт: delivery_mode, alert job, batch job и Telegram delivery spec завершены.
- `EPIC-20` закрыт.
- Следующий лучший блок: `TASK-062`, при хорошем результате можно сразу закрыть и `TASK-067`.

Что нужно сделать:
1. Выполнить `TASK-062`: определить AI enrichment contract для `EPIC-15`.
2. Если research получается цельным, сразу закрыть и `TASK-067`: задокументировать AI governance rules в `docs/architecture.md`.
3. Не делать runtime AI implementation в этой сессии. Это research/spec sprint.

Что должен содержать результат:
- provider/model decision или shortlist с понятным default
- input contract для enrichment
- output contract для enrichment
- gating rule: на каких score bands enrichment запускается
- timeout / retry / fallback policy без блокировки deterministic pipeline
- cost guardrails и связь с `ai_cost_usd`
- prompt/versioning expectations
- privacy and logging guardrails
- clear path к `TASK-061`, `TASK-063`, `TASK-064`, `TASK-065`, `TASK-066`

Что проверить:
- `python -m pytest tests/ -v` для регрессии
- консистентность между `research-v4-plus.md`, `architecture.md`, `manual-tasks.md`, backlog JSON
- отсутствие premature AI code

Tracker discipline:
- Linear — канон.
- GitHub — зеркало.
- Перед стартом перевести `TASK-062` в `In Progress`.
- `TASK-067` переводить в `In Progress` только если реально берёшь governance docs в этой же сессии.
- Закрывать только реально завершённые задачи.

После завершения:
- Обновить Linear first, затем GitHub mirror.
- Если `TASK-062` закрыт, следующий prompt должен вести в implementation path `TASK-061` + `TASK-063`.
- Если `TASK-062` не закрыт, следующий prompt должен быть продолжением `TASK-062`.
- В финальном handoff вставить полный новый Next Prompt inline.
