"""Central configuration.

Every threshold in this file that is NOT one of Navan's official tier rules is a
prototype hypothesis. None of them are statistically validated; they exist so that
behaviour is explicit, testable and easy to change.
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent.parent
REPO_DIR = BACKEND_DIR.parent
load_dotenv(BACKEND_DIR / ".env")

# --- Storage -----------------------------------------------------------------
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{BACKEND_DIR / 'navan_growth.db'}")
CSV_PATH = Path(os.getenv("PROSPECTS_CSV", str(REPO_DIR / "data" / "prospects.csv")))

# --- Official Navan tier rules (from the assignment; not tunable hypotheses) --
TIER1_GBV_MIN = 500_000
TIER2_GBV_MIN = 100_000
TIER2_EMPLOYEES_MIN = 150

# --- LLM / research provider --------------------------------------------------
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
RESEARCH_MODEL = os.getenv("RESEARCH_MODEL", "claude-haiku-5-5")
# Without an API key, replay recorded real runs from data/demo_snapshot.json (clearly labelled).
DEMO_REPLAY = os.getenv("DEMO_REPLAY", "true").lower() == "true"
# Haiku 5.5 uses the basic web search tool version (dynamic filtering variants are
# Opus/Sonnet only).
WEB_SEARCH_TOOL_TYPE = os.getenv("WEB_SEARCH_TOOL_TYPE", "web_search_20250305")
STANDARD_MAX_SEARCHES = int(os.getenv("STANDARD_MAX_SEARCHES", "5"))
DEEP_MAX_SEARCHES = int(os.getenv("DEEP_MAX_SEARCHES", "10"))
RESEARCH_TIMEOUT_SECONDS = float(os.getenv("RESEARCH_TIMEOUT_SECONDS", "120"))
RESEARCH_MAX_TOKENS = int(os.getenv("RESEARCH_MAX_TOKENS", "16000"))
RESEARCH_EFFORT = os.getenv("RESEARCH_EFFORT", "low")

# Approximate list prices used only for the cost display (USD).
PRICE_INPUT_PER_MTOK = float(os.getenv("PRICE_INPUT_PER_MTOK", "0.10"))
PRICE_OUTPUT_PER_MTOK = float(os.getenv("PRICE_OUTPUT_PER_MTOK", "0.50"))
PRICE_PER_WEB_SEARCH = float(os.getenv("PRICE_PER_WEB_SEARCH", "0.01"))  # $10 / 1,000

# Companies that get automatic standard research on import (cost control).
# The six PRD priority cases plus ten contrasting ones. Also the demo-mode recording set.
AUTO_RESEARCH_IDS = [
    s.strip()
    for s in os.getenv(
        "AUTO_RESEARCH_IDS",
        "P-001,P-002,P-007,P-009,P-010,P-012,P-018,P-019,P-021,P-025,P-026,P-028,P-030,P-032,P-033,P-041",
    ).split(",")
    if s.strip()
]
AUTO_RESEARCH_ON_IMPORT = os.getenv("AUTO_RESEARCH_ON_IMPORT", "false").lower() == "true"

# --- Evidence handling (hypotheses) ------------------------------------------
STALE_AFTER_DAYS = int(os.getenv("STALE_AFTER_DAYS", "548"))  # ~18 months
EMPLOYEE_CONFLICT_RATIO = 0.5  # sources differ by >50% -> conflict even if same side of 150

# Domains treated as aggregators (lower reliability, never sole support for Travel Potential)
AGGREGATOR_DOMAINS = (
    "zoominfo.com", "rocketreach.co", "crunchbase.com", "pitchbook.com", "growjo.com",
    "leadiq.com", "apollo.io", "cbinsights.com", "tracxn.com", "dnb.com", "owler.com",
    "craft.co", "signalhire.com", "theorg.com", "clay.com", "6sense.com", "lusha.com",
    "datanyze.com", "glassdoor.com", "indeed.com", "linkedin.com", "wikipedia.org",
)
# Primary/official registries are distinguished from aggregators.
PRIMARY_REGISTRY_DOMAINS = ("find-and-update.company-information.service.gov.uk", "companieshouse.gov.uk")

# --- Attention / proposal policy (hypotheses) -------------------------------
NEAR_THRESHOLD_GBV_PCT = 0.15     # GBV within 15% below a tier cut-off
NEAR_THRESHOLD_EMP_PCT = 0.20     # employees within ±20% of 150
GROWTH_MIN_INDEPENDENT_SIGNALS = 2

# --- Day 30 policy (hypotheses; bookings are NOT dollars) ---------------------
DAY30_MATERIAL_TRAVELERS = 15
DAY30_MATERIAL_BOOKINGS = 40
DAY30_MATERIAL_TREND_PCT = 25
DAY30_WEAK_TRAVELERS = 3               # at/below this, activity is weak
