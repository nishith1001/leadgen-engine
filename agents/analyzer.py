"""
Analyzer Agent
Screenshots each scraped lead's website (desktop + mobile) using Playwright,
sends both images to Claude for quality scoring, and stores results in SQLite.

Usage:
    python agents/analyzer.py
"""

import asyncio
import base64
import json
import logging
import os
import sqlite3
from pathlib import Path

import anthropic
from dotenv import load_dotenv
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError, Error as PlaywrightError

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

DB_PATH = os.getenv("DB_PATH", "data/leads.db")
SCREENSHOT_DIR = Path("data/screenshots")
MODEL = "claude-sonnet-4-6"
PAGE_TIMEOUT_MS = 30_000  # 30s

EVAL_PROMPT = """\
You are evaluating a local business website for quality. \
Score it on these criteria (0-2 each):
- mobile_responsive: Does the mobile version look professional and usable?
- clear_cta: Is there a prominent phone number or booking button visible above the fold?
- modern_design: Does it look like it was built after 2018?
- services_listed: Are specific services listed with descriptions?
- trust_signals: Are there reviews, certifications, or photos of the team/work?

Return JSON only: \
{"score": <total out of 10>, "issues": [<3-5 specific problems>], "strengths": [<1-2 things that work>]}\
"""


# ── Database helpers ───────────────────────────────────────────────────────────

def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def load_scraped_leads(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        "SELECT id, business_name, website_url FROM leads WHERE status = 'scraped'"
    ).fetchall()
    return [dict(r) for r in rows]


def already_analyzed(conn: sqlite3.Connection, lead_id: int) -> bool:
    row = conn.execute(
        "SELECT 1 FROM website_scores WHERE lead_id = ?", (lead_id,)
    ).fetchone()
    return row is not None


def store_score(conn: sqlite3.Connection, lead_id: int, score: float,
                issues: list, strengths: list, raw_response: str) -> None:
    conn.execute(
        """
        INSERT INTO website_scores
            (lead_id, overall_score, pain_points, opportunities, raw_response)
        VALUES (?, ?, ?, ?, ?)
        """,
        (lead_id, score, json.dumps(issues), json.dumps(strengths), raw_response),
    )
    conn.execute(
        "UPDATE leads SET status = 'analyzed' WHERE id = ?", (lead_id,)
    )
    conn.commit()


def mark_disqualified(conn: sqlite3.Connection, lead_id: int) -> None:
    conn.execute(
        "UPDATE leads SET status = 'disqualified' WHERE id = ?", (lead_id,)
    )
    conn.commit()


# ── Screenshot capture ─────────────────────────────────────────────────────────

async def take_screenshots(url: str, lead_id: int) -> tuple[Path, Path]:
    """Returns (desktop_path, mobile_path). Raises on failure."""
    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
    desktop_path = SCREENSHOT_DIR / f"{lead_id}_desktop.png"
    mobile_path = SCREENSHOT_DIR / f"{lead_id}_mobile.png"

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        try:
            # Desktop
            ctx_desktop = await browser.new_context(
                viewport={"width": 1280, "height": 800},
                ignore_https_errors=True,
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                ),
            )
            page_d = await ctx_desktop.new_page()
            await page_d.goto(url, timeout=PAGE_TIMEOUT_MS, wait_until="domcontentloaded")
            await page_d.screenshot(path=str(desktop_path), full_page=False)
            await ctx_desktop.close()

            # Mobile
            ctx_mobile = await browser.new_context(
                viewport={"width": 375, "height": 812},
                ignore_https_errors=True,
                user_agent=(
                    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
                    "AppleWebKit/605.1.15 (KHTML, like Gecko) "
                    "Version/17.0 Mobile/15E148 Safari/604.1"
                ),
            )
            page_m = await ctx_mobile.new_page()
            await page_m.goto(url, timeout=PAGE_TIMEOUT_MS, wait_until="domcontentloaded")
            await page_m.screenshot(path=str(mobile_path), full_page=False)
            await ctx_mobile.close()

        finally:
            await browser.close()

    return desktop_path, mobile_path


def encode_image(path: Path) -> str:
    return base64.standard_b64encode(path.read_bytes()).decode()


# ── Claude scoring ─────────────────────────────────────────────────────────────

def call_claude(client: anthropic.Anthropic, desktop_path: Path, mobile_path: Path) -> str:
    response = client.messages.create(
        model=MODEL,
        max_tokens=1024,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/png",
                            "data": encode_image(desktop_path),
                        },
                    },
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/png",
                            "data": encode_image(mobile_path),
                        },
                    },
                    {"type": "text", "text": EVAL_PROMPT},
                ],
            }
        ],
    )
    return next(b.text for b in response.content if b.type == "text")


def parse_claude_response(raw: str) -> dict:
    """Extract JSON from Claude's response, even if wrapped in markdown fences."""
    text = raw.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
    return json.loads(text)


# ── Per-lead pipeline ──────────────────────────────────────────────────────────

async def process_lead(lead: dict, client: anthropic.Anthropic, conn: sqlite3.Connection) -> str:
    """Returns one of: 'scored', 'skipped', 'screenshot_error', 'claude_error'."""
    lead_id = lead["id"]
    name = lead["business_name"]
    url = lead["website_url"]

    if already_analyzed(conn, lead_id):
        log.info("[%d] %s — already analyzed, skipping", lead_id, name)
        return "skipped"

    log.info("[%d] %s — screenshotting %s", lead_id, name, url)

    try:
        desktop_path, mobile_path = await take_screenshots(url, lead_id)
    except PlaywrightTimeoutError:
        log.warning("[%d] %s — page timed out", lead_id, name)
        mark_disqualified(conn, lead_id)
        return "screenshot_error"
    except PlaywrightError as exc:
        log.warning("[%d] %s — Playwright error: %s", lead_id, name, exc)
        mark_disqualified(conn, lead_id)
        return "screenshot_error"
    except Exception as exc:
        log.error("[%d] %s — unexpected screenshot error: %s", lead_id, name, exc)
        mark_disqualified(conn, lead_id)
        return "screenshot_error"

    log.info("[%d] %s — sending to Claude", lead_id, name)

    try:
        raw = call_claude(client, desktop_path, mobile_path)
        parsed = parse_claude_response(raw)
        score = float(parsed["score"])
        issues = parsed.get("issues", [])
        strengths = parsed.get("strengths", [])
    except json.JSONDecodeError as exc:
        log.error("[%d] %s — Claude returned invalid JSON: %s", lead_id, name, exc)
        return "claude_error"
    except anthropic.APIError as exc:
        log.error("[%d] %s — Anthropic API error: %s", lead_id, name, exc)
        return "claude_error"
    except Exception as exc:
        log.error("[%d] %s — unexpected Claude error: %s", lead_id, name, exc)
        return "claude_error"

    store_score(conn, lead_id, score, issues, strengths, raw)
    log.info("[%d] %s — score=%.1f/10  issues=%d  strengths=%d",
             lead_id, name, score, len(issues), len(strengths))
    return "scored"


# ── Entry point ────────────────────────────────────────────────────────────────

async def run() -> None:
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise SystemExit("ANTHROPIC_API_KEY not set in environment / .env")

    client = anthropic.Anthropic(api_key=api_key)
    conn = get_db()

    leads = load_scraped_leads(conn)
    if not leads:
        log.info("No leads with status='scraped' found.")
        conn.close()
        return

    log.info("Found %d lead(s) to analyze", len(leads))

    counts = {"scored": 0, "skipped": 0, "screenshot_error": 0, "claude_error": 0}
    for lead in leads:
        result = await process_lead(lead, client, conn)
        counts[result] += 1

    conn.close()

    print("\n-- Analysis complete --")
    print(f"  Scored              : {counts['scored']}")
    print(f"  Already analyzed    : {counts['skipped']}")
    print(f"  Screenshot failures : {counts['screenshot_error']}")
    print(f"  Claude errors       : {counts['claude_error']}")
    print("-" * 40)


if __name__ == "__main__":
    asyncio.run(run())
