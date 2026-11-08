"""Deterministic post-processing of LLM research output.

- Extract and validate JSON.
- Reject findings whose source URL was not actually returned by the search tool.
- Classify source reliability by domain (company site / registry / aggregator / other).
- Mark stale evidence by publication date.
"""
from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Optional
from urllib.parse import urlsplit

from pydantic import ValidationError

from .. import config
from .schema import ResearchOutput


class ParseError(Exception):
    pass


def extract_json(text: str) -> dict:
    if not text or not text.strip():
        raise ParseError("Empty response from model.")
    fenced = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.S)
    candidate = fenced.group(1) if fenced else None
    if candidate is None:
        start, end = text.find("{"), text.rfind("}")
        if start == -1 or end <= start:
            raise ParseError("No JSON object found in model response.")
        candidate = text[start : end + 1]
    try:
        data = json.loads(candidate)
    except json.JSONDecodeError as e:
        raise ParseError(f"Invalid JSON: {e.msg} at position {e.pos}.") from e
    if not isinstance(data, dict):
        raise ParseError("Top-level JSON value is not an object.")
    return data


def parse_research_output(text: str) -> ResearchOutput:
    data = extract_json(text)
    try:
        return ResearchOutput.model_validate(data)
    except ValidationError as e:
        # Compact, model-readable error summary (used for the repair retry).
        msgs = [f"{'.'.join(str(p) for p in err['loc'])}: {err['msg']}" for err in e.errors()[:12]]
        raise ParseError("Schema validation failed: " + "; ".join(msgs)) from e


def normalize_url(url: Optional[str]) -> str:
    if not url:
        return ""
    url = url.strip()
    if "://" not in url:
        url = "https://" + url
    parts = urlsplit(url)
    host = parts.netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    path = parts.path.rstrip("/")
    query = "&".join(q for q in parts.query.split("&") if q and not q.lower().startswith("utm_"))
    return f"{host}{path}" + (f"?{query}" if query else "")


def host_of(url: Optional[str]) -> str:
    return normalize_url(url).split("/", 1)[0].split("?", 1)[0]


def classify_reliability(url: Optional[str], company_domain: str) -> str:
    host = host_of(url)
    if not host:
        return "secondary"
    cd = company_domain.lower().removeprefix("www.")
    if host == cd or host.endswith("." + cd):
        return "primary"  # the company's own website
    if any(host == d or host.endswith("." + d) for d in config.PRIMARY_REGISTRY_DOMAINS):
        return "primary"
    if any(host == d or host.endswith("." + d) for d in config.AGGREGATOR_DOMAINS):
        return "aggregator"
    return "secondary"


_DATE_FORMATS = (("%Y-%m-%d", 10), ("%Y-%m", 7), ("%Y", 4))


def parse_date(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    v = value.strip()
    for fmt, length in _DATE_FORMATS:
        try:
            return datetime.strptime(v[:length], fmt)
        except ValueError:
            continue
    return None


def is_stale(published: Optional[str], cutoff: datetime) -> bool:
    d = parse_date(published)
    if d is None:
        return False  # unknown date is not the same as stale
    return (cutoff.replace(tzinfo=None) - d).days > config.STALE_AFTER_DAYS


def is_future(published: Optional[str], cutoff: datetime) -> bool:
    d = parse_date(published)
    return d is not None and d > cutoff.replace(tzinfo=None)


def validate_citations(output: ResearchOutput, allowed_urls: set[str]) -> tuple[ResearchOutput, list[dict]]:
    """Drop findings whose URL was not returned by the search tool in this run."""
    allowed = {normalize_url(u) for u in allowed_urls if u}
    dropped: list[dict] = []
    for fr in output.fields:
        kept = []
        for f in fr.findings:
            if normalize_url(f.source_url) in allowed:
                kept.append(f)
            else:
                dropped.append(
                    {"field": fr.field, "claim": f.claim, "source_url": f.source_url,
                     "reason": "unsupported_citation: URL not among search results returned in this run"}
                )
        fr.findings = kept
    return output, dropped


_RANGE = re.compile(
    r"\d[\d,]*\s*(?:-|\u2013|\u2014|to)\s*\d|\b(?:fewer|less|more)\s+than\b|\bunder\s+\d|\bover\s+\d|[<>]\s*\d|\d\+",
    re.I,
)


def clear_band_headcounts(output: ResearchOutput) -> list[dict]:
    """A headcount band ("51-200", "fewer than 25") is not an exact number. If the model put a
    number in value_number for a band, clear it so the band is not used by the tier rules."""
    changed = []
    for fr in output.fields:
        if fr.field != "employee_count":
            continue
        for f in fr.findings:
            if f.value_number is not None and _RANGE.search(f.claim):
                changed.append({"field": fr.field, "claim": f.claim, "source_url": f.source_url,
                                "reason": f"value_number {f.value_number:g} cleared: the source gives a band, not an exact headcount"})
                f.value_number = None
    return changed
