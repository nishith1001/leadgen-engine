# LeadGen Engine

An AI-powered pipeline that finds local service businesses with poor websites, generates a polished demo site for each one, and sends a personalized cold email with a preview link — fully automated.

## How it works

```
Google Places API
      │
      ▼
[1] scraper.py       → discovers businesses, screenshots their sites
      │
      ▼
[2] analyzer.py      → Claude scores each site 0–10, identifies pain points
      │  (score < threshold → disqualified)
      ▼
[3] site_generator.py → Claude writes copy → React template → Vercel deploy
      │
      ▼
[4] personalizer.py  → Claude writes a bespoke cold email per lead
      │
      ▼
[5] outreach.py      → Instantly.ai sends the email sequence
      │
      ▼
   Replies → Deals
```

All state is persisted in a local SQLite database (`data/leads.db`).

## Quick start

```bash
# 1. Clone & set up environment
cp .env.example .env        # fill in your API keys
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
playwright install chromium

# 2. Initialize the database
sqlite3 data/leads.db < database/schema.sql

# 3. Run the full pipeline
python cli.py scrape   --niche hvac --location "Phoenix, AZ"
python cli.py analyze
python cli.py generate
python cli.py send --dry-run   # remove --dry-run to actually send

# 4. Monitor progress
python cli.py status
streamlit run dashboard/app.py
```

## Project structure

```
leadgen-engine/
├── agents/
│   ├── scraper.py         # Google Places + Playwright scraping
│   ├── analyzer.py        # Claude website quality scoring
│   ├── site_generator.py  # Claude copy + React build + Vercel deploy
│   ├── personalizer.py    # Claude cold email personalizer
│   └── outreach.py        # Instantly.ai email sender
├── database/
│   └── schema.sql         # SQLite schema (leads, scores, sites, outreach, deals)
├── templates/
│   └── hvac/              # React (Vite) landing page template
├── data/                  # .gitignored — screenshots, leads.db
├── config/
│   ├── niches.yaml        # Niche definitions and target markets
│   └── prompts.yaml       # All Claude prompt templates
├── pipeline/
│   └── run.py             # Stage orchestrator
├── dashboard/
│   └── app.py             # Streamlit pipeline dashboard
├── cli.py                 # Click CLI (scrape, analyze, generate, send, status)
└── requirements.txt
```

## Configuration

Edit `config/niches.yaml` to add new niches or target markets.
Edit `config/prompts.yaml` to tune Claude prompts without touching Python code.

## Required API keys

| Key | Purpose |
|-----|---------|
| `ANTHROPIC_API_KEY` | Website analysis, copy generation, email personalization |
| `GOOGLE_PLACES_API_KEY` | Business discovery |
| `INSTANTLY_API_KEY` | Cold email delivery & sequencing |
| `VERCEL_TOKEN` | Demo site deployment |

## Adding a new niche

1. Add an entry to `config/niches.yaml`.
2. Create a new template under `templates/<niche>/` (or reuse an existing one).
3. Run the pipeline with `--niche <your-niche>`.
