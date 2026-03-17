"""
Vacancy summarization prompt for AI enrichment (TASK-066, EPIC-15).

Prompt text and version are versioned here; when the prompt changes, PROMPT_VERSION
must change so that stored ai_metadata.prompt_version remains meaningful.
See docs/specs/ai-enrichment-contract.md.
"""

PROMPT_VERSION = "summary_v1"

SYSTEM_PROMPT = """You are a concise job-summary assistant. Given a job vacancy (title, company, location, salary, description excerpt), output exactly one short paragraph: 2-3 sentences summarizing the role, key requirements or focus, and any notable details (e.g. remote, salary). Plain text only, no markdown or bullets. Write in the same language as the vacancy when obvious, otherwise English."""

USER_PROMPT_TEMPLATE = """Title: {title}
Company: {company}
Location: {location}
Salary: {salary_raw}

Description excerpt:
{body_excerpt}"""


def build_user_prompt(*, title: str | None, company: str | None, location: str | None, salary_raw: str | None, body_excerpt: str) -> str:
    """Build the user prompt from vacancy fields. Empty values become placeholder."""
    return USER_PROMPT_TEMPLATE.format(
        title=title or "(not specified)",
        company=company or "(not specified)",
        location=location or "(not specified)",
        salary_raw=salary_raw or "(not specified)",
        body_excerpt=body_excerpt or "(no description)",
    )


def prompt_hash_text(system: str, user: str) -> str:
    """Return a short hash of the full prompt for reproducibility (e.g. first 12 chars of sha256)."""
    import hashlib
    combined = f"{system}\n---\n{user}"
    return "sha256:" + hashlib.sha256(combined.encode("utf-8")).hexdigest()[:12]
