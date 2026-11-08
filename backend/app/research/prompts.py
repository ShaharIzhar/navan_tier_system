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
# Registry. v2 is added after observing v1 behaviour (see docs/llm_experiments.md).
# ---------------------------------------------------------------------------
PROMPTS: dict[str, dict[str, str]] = {
    "v1": {"system": SYSTEM_V1, "user": USER_V1},
}
CURRENT_VERSION = "v1"


def build_standard_prompt(company_name: str, domain: str, version: str | None = None) -> tuple[str, str, str]:
    """Return (version, system, user). Only Day 0 inputs are allowed here: name + domain."""
    v = version or CURRENT_VERSION
    p = PROMPTS[v]
    user = p["user"].format(
        company_name=company_name,
        domain=domain,
        fields=_FIELD_LIST,
        shape=json.dumps(JSON_SHAPE, indent=2),
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
        shape=json.dumps(JSON_SHAPE, indent=2),
    )
    return DEEP_SYSTEM, user


REPAIR_PROMPT = """Your previous answer could not be used because it was not valid JSON for the \
required schema. Validation error:
{error}

Return ONLY the corrected JSON object, using the same findings and the same source URLs. \
Do not add new facts. Do not wrap it in markdown."""
