Работаем в репозитории RoleForge.

Сначала прочитай:
- docs/prompts/cursor-autopilot-roleforge.md
- AGENTS.md
- README.md
- docs/architecture.md
- docs/roadmap.md
- docs/backlog/roleforge-backlog.json
- docs/manual-tasks.md
- docs/specs/ai-enrichment-contract.md

Текущее состояние:
- EPIC-15 закрыт (ai_metadata, enrichment.py, run_enrichment_for_high_scores, prompts, ai_cost_usd в summary).
- Следующий блок: EPIC-16 (Scheduler) или enrichment job entrypoint.

Что сделать сначала:
1. Обновить Linear: TASK-061, TASK-063–TASK-066 и EPIC-15 в Done.
2. Выполнить EPIC-16 (TASK-068 research → TASK-069 scheduler → TASK-070 docs) или добавить `roleforge/jobs/enrichment.py`, вызывающий run_enrichment_for_high_scores и log_job_finish с summary (включая ai_cost_usd).
3. Прогнать pytest; обновить Linear/GitHub; сгенерировать next-session prompt.

Ограничения: Gmail-only MVP; Postgres-first; one primary AI provider; AI только post-scoring.
