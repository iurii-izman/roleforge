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
- docs/specs/ai-enrichment-contract.md
- docs/specs/job-runs-logging.md
- docs/specs/cost-governance.md

Текущее состояние после прошлой сессии:
- EPIC-13, EPIC-14, EPIC-20 закрыты.
- EPIC-15 (AI Enrichment) закрыт: TASK-061 (миграция ai_metadata), TASK-062/067 (контракт и governance), TASK-063 (enrichment.py), TASK-064 (run_enrichment_for_high_scores), TASK-065 (ai_cost_usd в summary), TASK-066 (prompts/enrichment.py). Тесты 160 passed.

Что уже сделано:
- Схема 003_ai_metadata.sql; roleforge.enrichment (enrich_one, run_enrichment_for_high_scores, update_vacancy_ai_metadata); roleforge.prompts.enrichment (PROMPT_VERSION, build_user_prompt); зависимости openai, anthropic в requirements.txt.

Что осталось следующим лучшим блоком:
- EPIC-16 (Scheduler): TASK-068 research, TASK-069 implementation, TASK-070 docs.
- Опционально: отдельный job entrypoint для enrichment (например `python -m roleforge.jobs.enrichment`), вызывающий run_enrichment_for_high_scores и log_job_finish с summary (включая ai_cost_usd).

Что пользователь должен подготовить заранее, если применимо:
- Для запуска enrichment: PRIMARY_AI_PROVIDER и OPENAI_API_KEY или ANTHROPIC_API_KEY в keyring/env. Применить миграцию 003: `psql "$DATABASE_URL" -f schema/003_ai_metadata.sql`.

Что сделать сначала:
1. Обновить Linear: TASK-061, TASK-063, TASK-064, TASK-065, TASK-066 и EPIC-15 в Done.
2. Взять блок EPIC-16 (Scheduler) или реализовать enrichment job entrypoint.
3. Прогон pytest после изменений; обновить GitHub mirror по канону.

Ограничения, которые нельзя ломать:
- Gmail-only MVP; Postgres-first; Telegram digest + review queue; one primary AI provider; keyring-first secrets; AI enrichment только post-scoring.

После завершения:
- Обновить Linear first, затем GitHub mirror; close-out comments; сгенерировать новый next-session prompt.
