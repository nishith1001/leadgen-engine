"""
Personalizer Agent
Crafts hyper-personalized cold outreach emails using Claude.
References specific pain points found during website analysis.
"""

import anthropic


def build_email(lead: dict, score: dict, preview_url: str, client: anthropic.Anthropic) -> dict:
    """
    Generate a personalized cold email for a lead.
    Returns: { subject, body_text, body_html }
    """
    # TODO: load email prompt from config/prompts.yaml, call Claude
    raise NotImplementedError


def run(lead_ids: list[int] | None = None):
    """Entry point called by the pipeline orchestrator."""
    # TODO: load qualified leads without outreach, personalize, persist to outreach table
    raise NotImplementedError
