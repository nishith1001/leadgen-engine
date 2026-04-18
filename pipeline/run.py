"""
Pipeline Orchestrator
Runs the full lead generation pipeline (or individual stages) end-to-end.
Called by CLI commands or directly: python -m pipeline.run
"""

import os
import sys
import logging
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("pipeline")


def run_scrape(niche: str, location: str):
    """Stage 1: Discover businesses and scrape their websites."""
    from agents.scraper import run as scraper_run
    log.info("Scraping niche=%s location=%s", niche, location)
    scraper_run(niche=niche, location=location)


def run_analyze(lead_ids: list[int] | None = None):
    """Stage 2: Score leads with Claude."""
    from agents.analyzer import run as analyzer_run
    log.info("Analyzing leads: %s", lead_ids or "all unscored")
    analyzer_run(lead_ids=lead_ids)


def run_generate(lead_ids: list[int] | None = None):
    """Stage 3: Generate and deploy demo sites."""
    from agents.site_generator import run as generator_run
    log.info("Generating sites for leads: %s", lead_ids or "all qualified")
    generator_run(lead_ids=lead_ids)


def run_personalize(lead_ids: list[int] | None = None):
    """Stage 4: Write personalized outreach emails."""
    from agents.personalizer import run as personalizer_run
    log.info("Personalizing emails for leads: %s", lead_ids or "all ready")
    personalizer_run(lead_ids=lead_ids)


def run_outreach(lead_ids: list[int] | None = None):
    """Stage 5: Send emails via Instantly."""
    from agents.outreach import run as outreach_run
    log.info("Sending outreach for leads: %s", lead_ids or "all personalized")
    outreach_run(lead_ids=lead_ids)


def run_full_pipeline(niche: str, location: str):
    """Run all stages sequentially for a given niche + location."""
    run_scrape(niche, location)
    run_analyze()
    run_generate()
    run_personalize()
    run_outreach()
    log.info("Pipeline complete.")


if __name__ == "__main__":
    # Quick smoke-test: python -m pipeline.run hvac "Phoenix, AZ"
    if len(sys.argv) == 3:
        run_full_pipeline(niche=sys.argv[1], location=sys.argv[2])
    else:
        print("Usage: python -m pipeline.run <niche> <location>")
        sys.exit(1)
