"""
Scraper Agent
Discovers local service businesses using Google Places API and scrapes
their existing websites (if any) via Playwright for quality analysis.
"""

import asyncio
from playwright.async_api import async_playwright


async def discover_businesses(niche: str, location: str, api_key: str) -> list[dict]:
    """Query Google Places API to find local businesses in a given niche/location."""
    # TODO: implement Google Places API search
    raise NotImplementedError


async def scrape_website(url: str) -> dict:
    """
    Use Playwright to screenshot and extract metadata from a business website.
    Returns: { url, screenshot_path, title, meta_description, has_mobile, load_time_ms }
    """
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        # TODO: implement full scrape logic
        await browser.close()
    raise NotImplementedError


async def run(niche: str, location: str):
    """Entry point called by the pipeline orchestrator."""
    # TODO: orchestrate discovery + scraping, persist to DB
    raise NotImplementedError
