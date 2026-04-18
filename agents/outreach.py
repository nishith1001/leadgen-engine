"""
Outreach Agent
Sends personalized emails via Instantly.ai API and tracks replies.
Handles follow-up sequences and marks leads as responded.
"""

import requests


INSTANTLY_BASE = "https://api.instantly.ai/api/v1"


def send_email(campaign_id: str, lead: dict, email: dict, api_key: str) -> dict:
    """
    Add a lead + personalized email to an Instantly campaign.
    Returns the Instantly API response payload.
    """
    # TODO: POST to Instantly /lead/add with personalized fields
    raise NotImplementedError


def check_replies(campaign_id: str, api_key: str) -> list[dict]:
    """Poll Instantly for new replies and return them as a list."""
    # TODO: GET /analytics/campaign/summary or webhook handler
    raise NotImplementedError


def run(lead_ids: list[int] | None = None):
    """Entry point called by the pipeline orchestrator."""
    # TODO: load personalized-but-unsent outreach rows, send, update status
    raise NotImplementedError
