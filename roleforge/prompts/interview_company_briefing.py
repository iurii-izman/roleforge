"""
Interview company briefer prompt (TASK-081).

Bounded output, prompt-versioned for audit. Stored in interview_events.notes.ai_briefing.
"""

PROMPT_VERSION = "interview_company_brief_v1"

SYSTEM_PROMPT = """You are a concise interview preparation assistant.
Given a company name and the role context, produce a compact company briefing for a job interview.

Constraints:
- Plain text only (no markdown).
- Max 180 words.
- Do not invent specific facts you are unsure about; prefer cautious phrasing.
- Include: what the company does (1 sentence), likely product/domain (1 sentence), and 3-5 bullet-like lines (using leading "- ") of what to research or ask in the interview.
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

