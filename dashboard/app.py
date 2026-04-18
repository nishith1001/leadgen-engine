"""
Streamlit Dashboard
Provides a live view of the pipeline: leads, scores, sites, outreach stats, deals.
Run with: streamlit run dashboard/app.py
"""

import sqlite3
import json
import os
import streamlit as st
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

DB_PATH = os.getenv("DB_PATH", "data/leads.db")


@st.cache_resource
def get_connection():
    return sqlite3.connect(DB_PATH, check_same_thread=False)


def load_table(query: str, params: tuple = ()) -> pd.DataFrame:
    conn = get_connection()
    return pd.read_sql_query(query, conn, params=params)


# ── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="LeadGen Engine",
    page_icon="⚡",
    layout="wide",
)

st.title("LeadGen Engine Dashboard")

# ── Sidebar filters ───────────────────────────────────────────────────────────
st.sidebar.header("Filters")
niche_filter = st.sidebar.text_input("Niche (leave blank for all)")
status_options = ["all", "new", "analyzed", "generated", "contacted", "replied", "deal", "disqualified"]
status_filter = st.sidebar.selectbox("Lead status", status_options)

# ── KPI row ───────────────────────────────────────────────────────────────────
col1, col2, col3, col4 = st.columns(4)

try:
    df_kpi = load_table("SELECT status, COUNT(*) as n FROM leads GROUP BY status")
    totals = dict(zip(df_kpi["status"], df_kpi["n"]))
    col1.metric("Total Leads",       sum(totals.values()))
    col2.metric("Sites Generated",   totals.get("generated", 0))
    col3.metric("Emails Sent",       totals.get("contacted", 0))
    col4.metric("Replies",           totals.get("replied", 0))
except Exception:
    col1.info("No data yet — run the pipeline first.")

st.divider()

# ── Leads table ───────────────────────────────────────────────────────────────
st.subheader("Leads")

where_clauses = []
params: list = []
if niche_filter:
    where_clauses.append("l.niche = ?")
    params.append(niche_filter)
if status_filter != "all":
    where_clauses.append("l.status = ?")
    params.append(status_filter)

where_sql = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

try:
    df_leads = load_table(
        f"""
        SELECT l.id, l.business_name, l.niche, l.location,
               l.website_url, l.status, l.scraped_at,
               ws.overall_score,
               gs.preview_url
        FROM leads l
        LEFT JOIN website_scores ws ON ws.lead_id = l.id
        LEFT JOIN generated_sites gs ON gs.lead_id = l.id
        {where_sql}
        ORDER BY l.id DESC
        LIMIT 500
        """,
        tuple(params),
    )
    st.dataframe(df_leads, use_container_width=True)
except Exception as e:
    st.warning(f"Could not load leads: {e}")

# ── Outreach stats ────────────────────────────────────────────────────────────
st.subheader("Outreach")
try:
    df_out = load_table(
        "SELECT status, COUNT(*) as n FROM outreach GROUP BY status ORDER BY n DESC"
    )
    st.bar_chart(df_out.set_index("status"))
except Exception:
    st.info("No outreach data yet.")

# ── Deals ─────────────────────────────────────────────────────────────────────
st.subheader("Deals")
try:
    df_deals = load_table(
        """
        SELECT d.id, l.business_name, l.niche, d.stage, d.deal_value, d.closed_at
        FROM deals d JOIN leads l ON l.id = d.lead_id
        ORDER BY d.created_at DESC
        """
    )
    st.dataframe(df_deals, use_container_width=True)
except Exception:
    st.info("No deals yet.")
