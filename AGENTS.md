# AGENTS.md

## Project Context

Roleforge is currently at the repository bootstrap stage. The project is AI-first, but the final product scope and technical stack are still undecided.

## Default Expectations

- Inspect the repository before proposing or making changes.
- Prefer small, reversible commits over large speculative scaffolding.
- Do not introduce a framework, database, or deployment platform unless the user asks for it or the docs already confirm the choice.
- Update `README.md`, `docs/product-brief.md`, and `docs/architecture.md` when major decisions change.
- Keep code and config comments concise and in English unless the file already uses another language.
- Never commit secrets, tokens, credentials, or private data.

## Working Agreements

- Treat AI output as draft material that still needs human review.
- Make assumptions explicit in commit messages, PRs, or final notes.
- Prefer simple tooling until the MVP and delivery path are clearer.
- If a change affects auth, billing, data storage, or permissions, call out the risk clearly.

## Repository Map

- `README.md`: project overview and onboarding
- `docs/product-brief.md`: product intent, audience, and open questions
- `docs/architecture.md`: technical direction and decision log
- `docs/roadmap.md`: near-term milestones and sequencing
- `.github/pull_request_template.md`: merge checklist

## Definition of Done

- The requested change is implemented or the blocker is explicit.
- Relevant docs are updated if the change affects product or architecture.
- Validation steps are listed in the final handoff.
