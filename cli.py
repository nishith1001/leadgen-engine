"""
LeadGen Engine CLI
Usage: python cli.py [COMMAND] [OPTIONS]
"""

import click
from dotenv import load_dotenv

load_dotenv()


@click.group()
def cli():
    """AI-powered lead generation engine for local service business website flips."""


@cli.command()
@click.option("--niche",    required=True,  help="Target niche (e.g. hvac, plumbing)")
@click.option("--location", required=True,  help='Target city (e.g. "Phoenix, AZ")')
@click.option("--limit",    default=50,     show_default=True, help="Max leads to scrape")
def scrape(niche: str, location: str, limit: int):
    """Discover businesses and scrape their websites."""
    from pipeline.run import run_scrape
    click.echo(f"Scraping {limit} {niche} businesses in {location}...")
    run_scrape(niche=niche, location=location)
    click.echo("Done.")


@cli.command()
@click.option("--lead-ids", default=None, help="Comma-separated lead IDs (default: all unscored)")
def analyze(lead_ids: str | None):
    """Score leads with Claude website analysis."""
    from pipeline.run import run_analyze
    ids = [int(x) for x in lead_ids.split(",")] if lead_ids else None
    click.echo("Analyzing leads...")
    run_analyze(lead_ids=ids)
    click.echo("Done.")


@cli.command()
@click.option("--lead-ids", default=None, help="Comma-separated lead IDs (default: all qualified)")
def generate(lead_ids: str | None):
    """Generate and deploy demo sites for qualified leads."""
    from pipeline.run import run_generate, run_personalize
    ids = [int(x) for x in lead_ids.split(",")] if lead_ids else None
    click.echo("Generating sites...")
    run_generate(lead_ids=ids)
    click.echo("Personalizing emails...")
    run_personalize(lead_ids=ids)
    click.echo("Done.")


@cli.command()
@click.option("--lead-ids", default=None, help="Comma-separated lead IDs (default: all ready)")
@click.option("--dry-run",  is_flag=True,  help="Prepare emails but do not send")
def send(lead_ids: str | None, dry_run: bool):
    """Send personalized outreach emails via Instantly."""
    from pipeline.run import run_outreach
    ids = [int(x) for x in lead_ids.split(",")] if lead_ids else None
    if dry_run:
        click.echo("[DRY RUN] Would send to leads: " + (str(ids) if ids else "all ready"))
        return
    click.echo("Sending outreach...")
    run_outreach(lead_ids=ids)
    click.echo("Done.")


@cli.command()
@click.option("--niche",  default=None, help="Filter by niche")
@click.option("--status", default=None, help="Filter by status")
def status(niche: str | None, status: str | None):
    """Show pipeline status summary."""
    import sqlite3
    import os

    db_path = os.getenv("DB_PATH", "data/leads.db")
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        where_clauses = []
        params: list = []
        if niche:
            where_clauses.append("niche = ?")
            params.append(niche)
        if status:
            where_clauses.append("status = ?")
            params.append(status)
        where_sql = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

        cursor.execute(
            f"SELECT status, COUNT(*) FROM leads {where_sql} GROUP BY status ORDER BY status",
            params,
        )
        rows = cursor.fetchall()
        conn.close()

        if not rows:
            click.echo("No leads found.")
            return

        click.echo(f"\n{'Status':<15} {'Count':>6}")
        click.echo("-" * 23)
        for row_status, count in rows:
            click.echo(f"{row_status:<15} {count:>6}")
        click.echo()

    except Exception as e:
        click.echo(f"Error reading database: {e}", err=True)


if __name__ == "__main__":
    cli()
