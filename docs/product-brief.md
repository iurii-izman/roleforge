# Product Brief

## One-Line Pitch

RoleForge is a Gmail-first job intelligence pipeline that captures relevant vacancies, scores them against multiple profiles, and delivers a low-noise review flow through Telegram.

## Problem We Want To Solve

Job alerts arrive in inconsistent formats, duplicate across sources, and create more review work than signal. The first product goal is not universal ingestion from every platform. The first goal is a practical Gmail-first intake loop that can:

- collect job emails from one controlled intake path
- normalize vacancy data into a single schema
- score each vacancy against multiple profiles
- keep every relevant match in Postgres
- expose only compact digests and a review queue in Telegram

## Target Users

- A single operator managing one personal or team-like job search pipeline
- A user who already receives job alerts by email and wants stricter filtering and review control

## Core User Outcomes

- See all relevant matches without pushing every vacancy as a separate Telegram notification
- Review high-signal vacancies quickly through a queue instead of raw inbox triage
- Maintain an auditable history of messages, scores, and review actions in Postgres

## MVP Constraints

- Gmail only
- Postgres only as source of truth
- Telegram digest plus review queue only
- One primary AI provider in MVP
- Keyring-first secret handling

## Non-Goals

- No IMAP, Outlook, RSS, ATS APIs, or scraping in MVP
- No Notion or secondary hub in MVP
- No dashboard in MVP
- No dual-LLM hot path in MVP
- No adaptive learning loop before the base pipeline is stable

## Open Questions

- Which Gmail intake pattern is preferred in practice: dedicated mailbox or dedicated label?
- Which AI provider is the primary MVP choice?
- What digest cadence is acceptable for Telegram?
- Which hosting provider and budget envelope should be used for the first deployment?
