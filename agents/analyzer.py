"""
Analyzer Agent
Scores each scraped lead's website quality using Claude.
Produces a numeric score + structured breakdown saved to website_scores.
"""

import anthropic


def build_prompt(lead: dict) -> str:
    """Construct the Claude prompt for website quality analysis."""
    # TODO: load from config/prompts.yaml
    raise NotImplementedError


def analyze_lead(lead: dict, client: anthropic.Anthropic) -> dict:
    """
    Send website data to Claude and parse a structured quality score.
    Returns: { lead_id, score, design_score, seo_score, mobile_score, notes }
    """
    # TODO: call Claude, parse response
    raise NotImplementedError


def run(lead_ids: list[int] | None = None):
    """Entry point called by the pipeline orchestrator."""
    # TODO: load unscored leads from DB, analyze, persist scores
    raise NotImplementedError
