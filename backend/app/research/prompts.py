"""Versioned research prompts.

Every version is kept (never edited after it has been run) so the README can show
the original prompt, the observed failure, and the refinement.
"""
from __future__ import annotations

import json

from .schema import RESEARCH_FIELDS

JSON_SHAPE = {
    "company_identity_confirmed": True,
    "identity_note": "How you confirmed the sources describe the company at this domain",
    "fields": [
        {
            "field": "employee_count",
            "status": "found | not_found | conflicting | not_applicable",
            "summary": "One-sentence plain-English summary of what the sources say",
            "findings": [
                {
                    "claim": "Exact fact taken from the source",
                    "value_number": 120,
                    "signal_type": "direct_travel | indirect_growth | descriptive",
                    "observation": "observed | inferred",
                    "source_url": "URL returned by your web search",
                    "source_title": "Page title",
                    "publisher": "Site or organisation",
                    "published_date": "YYYY-MM-DD, YYYY-MM, YYYY, or null",
                }
            ],
        }
    ],
    "conflicts": [{"field": "employee_count", "description": "...", "source_urls": ["..."]}],
    "summary": "2-3 sentence summary for a salesperson",
    "research_limitations": ["What could not be found or verified"],
}

# v3 adds travel_scope. Each prompt version keeps its own JSON shape so old versions stay reproducible.
JSON_SHAPE_V3 = json.loads(json.dumps(JSON_SHAPE))
_f = JSON_SHAPE_V3["fields"][0]["findings"][0]
JSON_SHAPE_V3["fields"][0]["findings"][0] = {
    **{k: _f[k] for k in ("claim", "value_number", "signal_type", "observation")},
    "travel_scope": "business_travel | local_field_travel | unclear (direct_travel only, else null)",
    **{k: _f[k] for k in ("source_url", "source_title", "publisher", "published_date")},
}

_FIELD_LIST = "\n".join(f"- {k}: {v}" for k, v in RESEARCH_FIELDS.items())

# ---------------------------------------------------------------------------
# v1: first version
# ---------------------------------------------------------------------------
SYSTEM_V1 = """You are a company research assistant for a B2B sales team at a business-travel \
platform. You research companies using web search and report what public sources say.

Rules:
- Use only information from your web search results. Do not use prior knowledge.
- Every finding must cite the URL of the search result it came from.
- If you cannot find information for a field, mark it not_found. Do not guess.
- If sources disagree, mark the field conflicting and describe the conflict.
- Separate facts stated by a source (observed) from your own inferences (inferred).
- Do not estimate travel spend or GBV.
- Do not give confidence percentages.
- Respond with a single JSON object and nothing else."""

USER_V1 = """Research this company:
Company name: {company_name}
Website domain: {domain}

Cover these fields:
{fields}

signal_type meanings:
- direct_travel: direct evidence that employees travel for work (e.g. job ads requiring travel, \
field or client-site work, travelling sales teams)
- indirect_growth: growth signals (funding, new offices, hiring growth, international expansion)
- descriptive: everything else

For employee_count findings, put the number in value_number.

Return JSON in exactly this shape:
{shape}"""


# ---------------------------------------------------------------------------
# v2: refined after running v1 on P-007, P-009, P-033 (see docs/llm_experiments.md).
# Observed v1 failures this addresses:
#   1. Headcount bands ("101-250", "<25") were turned into exact numbers in value_number.
#   2. No search ever targeted travel requirements; travel_indicators was not_found in 3/3 runs.
#   3. Method/date differences between databases were reported as conflicts.
# ---------------------------------------------------------------------------
SYSTEM_V2 = SYSTEM_V1 + """
- Several pages repeating the same figure or announcement are one source, not several.
- Treat data aggregators (LinkedIn, ZoomInfo, PitchBook, Crunchbase, Tracxn, Dealroom and similar) as estimates."""

USER_V2 = """Research this company:
Company name: {company_name}
Website domain: {domain}

Cover these fields:
{fields}

Search plan (you have a small number of searches; use them in this order):
1. The company's own website and basic profile (what it does, where it operates, size).
2. Travel requirements: search for the company's job postings or careers page together with words like \
"travel", "client site", "on-site", "field". This is the most important field for this research. \
Report what job ads or company pages actually say. If you find nothing, mark travel_indicators not_found.
3. Recent funding, expansion and hiring news.

signal_type meanings:
- direct_travel: a source explicitly states that employees travel for work (e.g. a job ad saying \
"travel required" or "50% travel", field engineers visiting customer sites, consultants based at client sites). \
Use this ONLY when the source states it. If you are guessing that a role probably involves travel, \
set observation to "inferred".
- indirect_growth: growth signals (funding, new offices, hiring growth, international expansion)
- descriptive: everything else

Employee count rules:
- Put a number in value_number ONLY when the source states one exact headcount (e.g. "53 employees").
- For a band or range (e.g. "11-50", "51-200", "fewer than 25"), set value_number to null and keep the band in the claim.
- Include the "as of" date in published_date when the source gives one.

Conflict rules:
- Report a conflict only when sources disagree about the same fact for the same period in a way that \
changes the conclusion (for example, one source says 40 staff and another says 400).
- Different estimates from different databases, or figures from different dates, are normal. \
Describe them in the field summary, not as a conflict, and use status "found".

Return JSON in exactly this shape:
{shape}"""


# ---------------------------------------------------------------------------
# v3: refined after a live Deep Research run on P-025 Bionical Solutions found community-nurse
# job ads (driving to patients' homes, mileage allowance) and the rules counted them as business
# travel. Local field travel rarely creates bookable travel (flights, hotels, rail), which is what
# GBV measures. v3 asks the model to label the travel scope of every direct_travel finding.
# ---------------------------------------------------------------------------
TRAVEL_SCOPE_RULES = """
travel_scope (required for every direct_travel finding, null otherwise):
- business_travel: travel that is usually booked: flights, hotels, rail, overnight stays, travel to \
other cities or countries, travel to customer sites in other regions, conferences.
- local_field_travel: driving within a local area, home visits, a mileage or car allowance, \
"on the road" within a territory, daily site visits near home.
- unclear: the source says travel is required but not what kind."""

SYSTEM_V3 = SYSTEM_V2
USER_V3 = USER_V2.replace("Employee count rules:", TRAVEL_SCOPE_RULES.strip() + "\n\nEmployee count rules:")

# ---------------------------------------------------------------------------
# Registry. Old versions are kept unchanged for comparison.
# ---------------------------------------------------------------------------
PROMPTS: dict[str, dict[str, str]] = {
    "v1": {"system": SYSTEM_V1, "user": USER_V1, "shape": JSON_SHAPE},
    "v2": {"system": SYSTEM_V2, "user": USER_V2, "shape": JSON_SHAPE},
    "v3": {"system": SYSTEM_V3, "user": USER_V3, "shape": JSON_SHAPE_V3},
}
CURRENT_VERSION = "v3"


def build_standard_prompt(company_name: str, domain: str, version: str | None = None) -> tuple[str, str, str]:
    """Return (version, system, user). Only Day 0 inputs are allowed here: name + domain."""
    v = version or CURRENT_VERSION
    p = PROMPTS[v]
    user = p["user"].format(
        company_name=company_name,
        domain=domain,
        fields=_FIELD_LIST,
        shape=json.dumps(p["shape"], indent=2),
    )
    return v, p["system"], user


DEEP_SYSTEM = """You are doing a focused follow-up research pass for a B2B sales team at a \
business-travel platform. A first research pass already exists. Your job is to resolve the \
specific gaps and conflicts listed by the user with additional web searches.

Rules:
- Use only information from your web search results in THIS conversation. Do not use prior knowledge.
- Every finding must cite the URL of a search result you retrieved.
- Do not repeat findings that are already in the existing evidence unless you found an \
independent source that confirms or contradicts them.
- Several articles repeating the same announcement are one source of evidence, not several.
- If you still cannot find something, mark it not_found and say what you tried.
- Do not estimate travel spend or GBV. Do not give confidence percentages.
- Respond with a single JSON object and nothing else."""

DEEP_USER = """Company name: {company_name}
Website domain: {domain}

Fields to investigate (and why):
{focus}

Existing evidence (already known; do not search for it again):
{existing}

For every direct_travel finding, set travel_scope: business_travel (flights, hotels, rail, \
overnight or out-of-region trips), local_field_travel (local driving, home visits, mileage or car \
allowance), or unclear.

Return JSON in exactly this shape, including only the fields listed above:
{shape}"""


def build_deep_prompt(company_name: str, domain: str, focus: dict[str, str], existing: list[dict]) -> tuple[str, str]:
    focus_txt = "\n".join(f"- {f} ({RESEARCH_FIELDS.get(f, f)}): {why}" for f, why in focus.items())
    existing_txt = json.dumps(existing, indent=1)[:12000] if existing else "(none)"
    user = DEEP_USER.format(
        company_name=company_name,
        domain=domain,
        focus=focus_txt,
        existing=existing_txt,
        shape=json.dumps(JSON_SHAPE_V3, indent=2),
    )
    return DEEP_SYSTEM, user


REPAIR_PROMPT = """Your previous answer could not be used because it was not valid JSON for the \
required schema. Validation error:
{error}

Return ONLY the corrected JSON object, using the same findings and the same source URLs. \
Do not add new facts. Do not wrap it in markdown."""
