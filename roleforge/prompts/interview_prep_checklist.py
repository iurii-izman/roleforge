"""
Interview preparation checklist prompt (TASK-082).

Bounded output, prompt-versioned for audit. Stored in interview_events.notes.prep_checklist.
"""

PROMPT_VERSION = "interview_prep_checklist_v1"

SYSTEM_PROMPT = """You are an interview preparation assistant.
Given the role and the vacancy context, produce a short preparation checklist.

Constraints:
- Plain text only (no markdown).
- Output exactly 8 checklist items, each on its own line, prefixed with "- ".
- Each item must be <= 120 characters.
"""

USER_PROMPT_TEMPLATE = """Company: {company}
Role: {title}

Vacancy excerpt (may be incomplete):
{body_excerpt}"""


def build_user_prompt(*, company: str | None, title: str | None, body_excerpt: str) -> str:
    return USER_PROMPT_TEMPLATE.format(
        company=company or "(not specified)",
        title=title or "(not specified)",
        body_excerpt=body_excerpt or "(no excerpt)",
    )

