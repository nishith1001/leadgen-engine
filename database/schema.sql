-- leadgen-engine database schema
-- SQLite (development) — column types follow SQLite affinity rules

PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

-- ─────────────────────────────────────────────
-- 1. Raw leads discovered by the scraper
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS leads (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    business_name     TEXT    NOT NULL,
    niche             TEXT    NOT NULL,           -- e.g. "hvac", "plumbing"
    location          TEXT    NOT NULL,           -- city / metro
    phone             TEXT,
    email             TEXT,
    website_url       TEXT,
    google_place_id   TEXT    UNIQUE,
    screenshot_path   TEXT,                       -- local path to Playwright screenshot
    scraped_at        DATETIME DEFAULT (datetime('now')),
    status            TEXT    NOT NULL DEFAULT 'new'
                              CHECK(status IN ('new','analyzed','generated','contacted','replied','deal','disqualified'))
);

-- ─────────────────────────────────────────────
-- 2. Claude-generated website quality scores
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS website_scores (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    lead_id         INTEGER NOT NULL REFERENCES leads(id) ON DELETE CASCADE,
    overall_score   REAL    NOT NULL CHECK(overall_score BETWEEN 0 AND 10),
    design_score    REAL    CHECK(design_score BETWEEN 0 AND 10),
    seo_score       REAL    CHECK(seo_score BETWEEN 0 AND 10),
    mobile_score    REAL    CHECK(mobile_score BETWEEN 0 AND 10),
    speed_score     REAL    CHECK(speed_score BETWEEN 0 AND 10),
    pain_points     TEXT,   -- JSON array of strings
    opportunities   TEXT,   -- JSON array of strings
    raw_response    TEXT,   -- full Claude response for debugging
    scored_at       DATETIME DEFAULT (datetime('now'))
);

-- ─────────────────────────────────────────────
-- 3. Generated demo sites
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS generated_sites (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    lead_id         INTEGER NOT NULL REFERENCES leads(id) ON DELETE CASCADE,
    template_used   TEXT    NOT NULL,             -- e.g. "hvac"
    preview_url     TEXT,                         -- Vercel preview URL
    build_path      TEXT,                         -- local build output dir
    content_json    TEXT,                         -- generated copy as JSON
    deployed_at     DATETIME,
    created_at      DATETIME DEFAULT (datetime('now'))
);

-- ─────────────────────────────────────────────
-- 4. Outreach emails & sequences
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS outreach (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    lead_id             INTEGER NOT NULL REFERENCES leads(id) ON DELETE CASCADE,
    site_id             INTEGER REFERENCES generated_sites(id),
    subject             TEXT    NOT NULL,
    body_text           TEXT    NOT NULL,
    body_html           TEXT,
    instantly_lead_id   TEXT,                     -- Instantly.ai reference ID
    campaign_id         TEXT,
    sequence_step       INTEGER DEFAULT 1,
    status              TEXT    NOT NULL DEFAULT 'draft'
                                CHECK(status IN ('draft','queued','sent','opened','clicked','replied','bounced')),
    sent_at             DATETIME,
    opened_at           DATETIME,
    replied_at          DATETIME,
    created_at          DATETIME DEFAULT (datetime('now'))
);

-- ─────────────────────────────────────────────
-- 5. Closed deals / pipeline tracking
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS deals (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    lead_id         INTEGER NOT NULL REFERENCES leads(id) ON DELETE CASCADE,
    stage           TEXT    NOT NULL DEFAULT 'interested'
                            CHECK(stage IN ('interested','negotiating','closed_won','closed_lost')),
    deal_value      REAL,                         -- USD
    notes           TEXT,
    closed_at       DATETIME,
    created_at      DATETIME DEFAULT (datetime('now'))
);

-- ─────────────────────────────────────────────
-- Indexes
-- ─────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_leads_status   ON leads(status);
CREATE INDEX IF NOT EXISTS idx_leads_niche    ON leads(niche);
CREATE INDEX IF NOT EXISTS idx_outreach_lead  ON outreach(lead_id);
CREATE INDEX IF NOT EXISTS idx_outreach_status ON outreach(status);
