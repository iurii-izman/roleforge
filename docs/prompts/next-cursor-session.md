Работаем в репозитории RoleForge.

Сначала прочитай:
- docs/prompts/cursor-autopilot-roleforge.md
- AGENTS.md
- README.md
- docs/architecture.md
- docs/roadmap.md
- docs/backlog/roleforge-backlog.json
- docs/manual-tasks.md
- docs/specs/profile-schema.md
- docs/specs/telegram-interaction.md
- docs/specs/scoring-spec.md
- roleforge/delivery_log.py
- scripts/seed_profiles_v2.py

Текущее состояние:
- `EPIC-13` закрыт: scoring откалиброван и больше не placeholder.
- `EPIC-20` закрыт: structured logging, admin alert и cost-governance docs завершены.
- `TASK-056` и `TASK-058` закрыты как подготовка alert pipeline.
- Следующий реальный блок: `TASK-057`.

Что нужно сделать:
- Реализовать `roleforge/jobs/alert.py`.
- Брать только новые `profile_matches`, которые проходят `profile.config.delivery_mode`.
- Поддержать `alert_enabled=true` и `score >= immediate_threshold`.
- Не переотправлять уже отправленные alert-сообщения.
- Логировать отправки в `telegram_deliveries` с `delivery_type='alert'`.
- Писать `job_runs` summary для alert job.
- Добавить tests и docs.

Что проверить:
1. `podman start roleforge-pg` при необходимости.
2. `python -m pytest tests/ -v`
3. dry-run / no-op сценарий для alert job.
4. если есть тестовые данные и Telegram config, один живой alert path.

Tracker discipline:
- Linear — канон.
- GitHub — зеркало.
- Перед началом перевести `TASK-057` и `EPIC-14` в `In Progress`.
- Закрывать только реально завершённые задачи.

После завершения:
- Обновить Linear first, затем GitHub mirror.
- Переписать этот файл под следующий блок: либо `TASK-059`, либо продолжение `TASK-057`, если останутся хвосты.
- В финальном handoff обязательно вставить полный новый Next Prompt inline, а не только обновить файл.
