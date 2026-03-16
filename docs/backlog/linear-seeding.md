# Linear Seeding Guide

Use this guide with `docs/backlog/roleforge-backlog.json`.

## Project

- Create one Linear project: `RoleForge MVP`
- Team key: `ROL`
- Canonical workflow:
  - `Backlog`
  - `Ready`
  - `In Progress`
  - `Blocked`
  - `User Input`
  - `Done`

## Metadata Mapping

- Priority:
  - `P0`
  - `P1`
  - `P2`
- AI readiness:
  - `AI-Ready`
  - `Human-Verify`
  - `Human-Only`
- Effort:
  - `L`
  - `M`
  - `H`

## Creation Order

1. Create the project.
2. Create the epics from `roleforge-backlog.json` in ID order.
3. Create tasks under each epic in ID order.
4. Keep all `User Input` work as first-class issues, not comments.
5. Keep future-phase epics (`v2`, `v3.1`, `v3.2`) as placeholders until MVP execution begins.

## Manual Rules

- Use the issue `id` as a stable external reference in the title or body.
- Copy the body sections exactly:
  - Goal
  - Inputs
  - Outputs
  - Acceptance criteria
  - AI should generate
  - Human should verify
- If a task has `"github_mirror": false`, it can stay Linear-only.
