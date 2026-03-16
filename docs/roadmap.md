# Roadmap

## MVP

- Seed canonical backlog in Linear and mirrored backlog in GitHub Projects
- Complete access and bootstrap for Gmail, Telegram, and one AI provider
- Implement Gmail-only polling intake
- Implement deterministic parsing, normalization, and dedup
- Implement Postgres-first match, score, and review state model
- Implement Telegram digest plus review queue
- Add minimal retries, replay, and runtime docs

## v2

- Richer multiple-profile behavior (see docs/specs/v2-profiles-and-queue.md)
- Better summaries and score calibration
- Better queue ergonomics (see docs/specs/v2-profiles-and-queue.md)
- Basic analytics and reporting (see docs/specs/v2-profiles-and-queue.md)
- Optional exceptional alert path if the digest-only model proves too slow

## v3.1

- Add RSS and structured feeds through the same normalized schema (see docs/specs/v3-feeds-and-connectors.md)
- Add source registry and kill-switch controls (see docs/specs/v3-feeds-and-connectors.md)

## v3.2

- Add official source connectors only after Gmail MVP is stable (see docs/specs/v3-feeds-and-connectors.md)
- Use legal clarity, structured value, and maintenance cost as gating criteria (see docs/specs/v3-feeds-and-connectors.md)
