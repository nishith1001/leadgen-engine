"""
Scraper Agent
Discovers local service businesses using Google Places API (Text Search + Place Details)
and stores qualifying leads in SQLite.

Usage:
    python agents/scraper.py --city "Dallas TX" --niche hvac --max 100
    python agents/scraper.py --city "Chicago IL" --niche plumbing
"""

import argparse
import os
import sqlite3
import time
import logging
from pathlib import Path

import requests
import yaml
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

PLACES_TEXT_SEARCH_URL = "https://places.googleapis.com/v1/places:searchText"
PLACES_DETAILS_URL = "https://places.googleapis.com/v1/places/{place_id}"

# Field masks for the new Places API
SEARCH_FIELD_MASK = "places.id,places.displayName,places.rating,places.userRatingCount,places.websiteUri,nextPageToken"
DETAIL_FIELD_MASK = "id,displayName,formattedAddress,nationalPhoneNumber,websiteUri,rating,userRatingCount"

MIN_RATING = 2.5
MAX_RATING = 4.6   # high rating ≠ good website; captures the bulk of real businesses
MIN_REVIEWS = 5

_NICHES_PATH = Path(__file__).parent.parent / "config" / "niches.yaml"


def load_niches() -> dict:
    return yaml.safe_load(_NICHES_PATH.read_text())["niches"]


def get_db(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    schema = Path(__file__).parent.parent / "database" / "schema.sql"
    conn.executescript(schema.read_text())
    conn.commit()
    return conn


def website_exists(conn: sqlite3.Connection, website_url: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM leads WHERE website_url = ?", (website_url,)
    ).fetchone()
    return row is not None


def insert_lead(conn: sqlite3.Connection, lead: dict, city: str, niche: str) -> int:
    cur = conn.execute(
        """
        INSERT INTO leads
            (business_name, niche, location, phone, website_url,
             google_place_id, status)
        VALUES (?, ?, ?, ?, ?, ?, 'scraped')
        """,
        (
            lead.get("displayName", {}).get("text") or lead.get("displayName", ""),
            niche,
            city,
            lead.get("nationalPhoneNumber"),
            lead.get("websiteUri"),
            lead.get("id"),
        ),
    )
    conn.commit()
    return cur.lastrowid


def text_search(query: str, api_key: str, page_token: str | None = None) -> dict:
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": SEARCH_FIELD_MASK,
    }
    body: dict = {"textQuery": query, "pageSize": 20}
    if page_token:
        body["pageToken"] = page_token
    resp = requests.post(PLACES_TEXT_SEARCH_URL, json=body, headers=headers, timeout=10)
    resp.raise_for_status()
    return resp.json()


def place_details(place_id: str, api_key: str) -> dict | None:
    url = PLACES_DETAILS_URL.format(place_id=place_id)
    headers = {
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": DETAIL_FIELD_MASK,
    }
    resp = requests.get(url, headers=headers, timeout=10)
    resp.raise_for_status()
    data = resp.json()
    if "error" in data:
        log.warning("Details fetch failed for %s: %s", place_id, data["error"])
        return None
    return data


def passes_filter(detail: dict) -> bool:
    rating = detail.get("rating")
    reviews = detail.get("userRatingCount", 0)
    website = detail.get("websiteUri")
    if not website:
        return False
    if rating is None or not (MIN_RATING <= rating <= MAX_RATING):
        return False
    if reviews < MIN_REVIEWS:
        return False
    return True


def scrape(city: str, niche: str, niche_cfg: dict, max_results: int, api_key: str, db_path: str) -> dict:
    conn = get_db(db_path)
    display_name = niche_cfg["display_name"]
    query = f"{display_name} in {city}"

    saved = 0
    skipped_filter = 0
    skipped_duplicate = 0
    errors = 0
    candidates_seen = 0

    page_token = None
    first_page = True

    while candidates_seen < max_results:
        # Google requires a short delay before using a page token
        if page_token and not first_page:
            time.sleep(2)
        first_page = False

        try:
            data = text_search(query, api_key, page_token)
        except Exception as exc:
            log.error("Text search failed: %s", exc)
            break

        if "error" in data:
            log.error("Text search error: %s", data["error"])
            break

        results = data.get("places", [])
        if not results:
            break

        for place in results:
            if candidates_seen >= max_results:
                break

            place_id = place.get("id")
            candidates_seen += 1
            log.info("[%d] Fetching details for place_id=%s", candidates_seen, place_id)

            time.sleep(1)  # rate limit: 1 req/sec

            try:
                detail = place_details(place_id, api_key)
            except Exception as exc:
                log.error("Details request failed for %s: %s", place_id, exc)
                errors += 1
                continue

            if detail is None:
                errors += 1
                continue

            if not passes_filter(detail):
                log.info("  Filtered out: rating=%s reviews=%s website=%s",
                         detail.get("rating"), detail.get("userRatingCount"),
                         bool(detail.get("websiteUri")))
                skipped_filter += 1
                continue

            website = detail["websiteUri"]
            if website_exists(conn, website):
                log.info("  Duplicate (website already in DB): %s", website)
                skipped_duplicate += 1
                continue

            name = detail.get("displayName", {}).get("text", "") if isinstance(detail.get("displayName"), dict) else detail.get("displayName", "")
            try:
                lead_id = insert_lead(conn, detail, city, niche)
                saved += 1
                log.info("  Saved lead #%d: %s - %s (rating=%.1f, reviews=%d)",
                         lead_id, name, website,
                         detail.get("rating", 0), detail.get("userRatingCount", 0))
            except sqlite3.IntegrityError as exc:
                log.warning("  DB insert skipped (integrity): %s", exc)
                skipped_duplicate += 1

        page_token = data.get("nextPageToken")
        if not page_token:
            break

    conn.close()
    return {
        "candidates_seen": candidates_seen,
        "saved": saved,
        "skipped_filter": skipped_filter,
        "skipped_duplicate": skipped_duplicate,
        "errors": errors,
    }


def main():
    niches = load_niches()
    niche_choices = list(niches.keys())

    parser = argparse.ArgumentParser(description="Scrape local service leads from Google Places")
    parser.add_argument("--city", required=True, help='City to search, e.g. "Dallas TX"')
    parser.add_argument(
        "--niche",
        required=True,
        choices=niche_choices,
        metavar="{" + ",".join(niche_choices) + "}",
        help="Business niche to search for",
    )
    parser.add_argument("--max", type=int, default=100, dest="max_results",
                        help="Maximum candidates to inspect (default 100)")
    args = parser.parse_args()

    api_key = os.getenv("GOOGLE_PLACES_API_KEY")
    if not api_key:
        raise SystemExit("GOOGLE_PLACES_API_KEY not set in environment / .env")

    db_path = os.getenv("DB_PATH", "data/leads.db")
    niche_cfg = niches[args.niche]

    log.info("Starting scrape: niche=%s city=%r max=%d db=%s",
             args.niche, args.city, args.max_results, db_path)
    summary = scrape(args.city, args.niche, niche_cfg, args.max_results, api_key, db_path)

    print(f"\n-- Scrape complete [{args.niche} / {args.city}] --")
    print(f"  Candidates inspected : {summary['candidates_seen']}")
    print(f"  Leads saved          : {summary['saved']}")
    print(f"  Filtered out         : {summary['skipped_filter']}")
    print(f"  Duplicates skipped   : {summary['skipped_duplicate']}")
    print(f"  Errors               : {summary['errors']}")
    print("-" * 50)


if __name__ == "__main__":
    main()
