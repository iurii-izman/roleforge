# Roleforge

Roleforge is a new AI-first product and engineering repository. The exact product scope is still being shaped, so this repository now contains the baseline documentation, collaboration rules, and project hygiene we will build on as decisions become clearer.

## Current Status

- GitHub repository connected and synchronized locally
- Baseline repository files added for AI-assisted development
- Product scope, stack, and MVP definition are still open

## Working Principles

- AI-assisted development by default
- Small, reviewable changes with explicit assumptions
- Documentation stays close to implementation
- No secrets in git; keep credentials in local keyring or `.env`

## Repository Layout

- `.github/` GitHub ownership and pull request templates
- `docs/` product, architecture, and roadmap notes
- `AGENTS.md` repository-specific guidance for AI coding agents
- `.env.example` local environment template

## Getting Started

1. Clone the repository.
2. Authenticate GitHub access with `gh auth login` if your local setup needs it.
3. Copy `.env.example` to `.env` and fill only the keys you actually use.
4. Update `docs/product-brief.md` before building the first feature.
5. Keep `README.md` and `docs/architecture.md` aligned with major decisions.

## AI Workflow

1. Define the task in an issue, PR, or working note.
2. Let the AI agent inspect the repository before proposing changes.
3. Keep outputs small and easy to review.
4. Record product and architecture decisions in `docs/`.
5. Review anything touching auth, billing, data, or permissions especially carefully.

## First Next Steps

- Define the product promise and target user
- Choose the initial tech stack
- Outline the MVP flow
- Add the first runnable application skeleton

## Notes

This baseline intentionally avoids locking the project into a framework too early. Once we choose a stack, we can add stack-specific tooling, CI, and developer commands without rewriting the repository foundation.
