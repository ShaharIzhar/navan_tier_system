"""Run research prompts on test cases and save the raw, unedited outputs.

Usage (from backend/):
    .venv/bin/python -m scripts.prompt_experiment --version v1 --cases P-007 P-033
    .venv/bin/python -m scripts.prompt_experiment --version v1 --conflict-test P-007

Outputs go to docs/experiments/<version>/<case>.json, so they can be quoted in
docs/llm_experiments.md. This does not touch the application database.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import config  # noqa: E402
from app.importer import read_csv  # noqa: E402
from app.research import prompts  # noqa: E402
from app.research.client import AnthropicResearchClient, ResearchProviderError, estimate_cost  # noqa: E402
from app.research.evidence import (ParseError, classify_reliability, clear_band_headcounts, parse_research_output,
                                   validate_citations)  # noqa: E402

OUT = config.REPO_DIR / "docs" / "experiments"

SYNTHETIC_CONFLICT = [
    {
        "field": "employee_count",
        "claim": "[SYNTHETIC TEST] Alternative estimate: 90 employees",
        "source_url": None,
        "published_date": None,
        "note": "Synthetic observation for a controlled test, not a real source.",
    },
    {
        "field": "employee_count",
        "claim": "Enrichment provider estimate: 155 employees",
        "source_url": None,
        "published_date": None,
        "note": "Dataset enrichment value (fictional scenario data).",
    },
]


def company(pid: str) -> dict:
    for r in read_csv(config.CSV_PATH):
        if r["scenario_id"] == pid:
            return r
    raise SystemExit(f"Unknown case {pid}")


def analyse(text: str, search_results: list[dict], domain: str) -> dict:
    out: dict = {"parse_ok": False}
    try:
        parsed = parse_research_output(text)
    except ParseError as e:
        out["parse_error"] = str(e)
        return out
    allowed = {r["url"] for r in search_results}
    validated, dropped = validate_citations(parsed, allowed)
    raw_employee_values = [
        {"value": x.value_number, "claim": x.claim}
        for f in validated.fields if f.field == "employee_count" for x in f.findings
    ]
    band_fixes = clear_band_headcounts(validated)
    out.update(
        raw_employee_values_before_guard=raw_employee_values,
        band_guard_changes=band_fixes,
        parse_ok=True,
        field_statuses={f.field: f.status for f in validated.fields},
        findings_kept=sum(len(f.findings) for f in validated.fields),
        findings_dropped=dropped,
        employee_values=[
            {"value": x.value_number, "claim": x.claim, "url": x.source_url,
             "reliability": classify_reliability(x.source_url, domain), "date": x.published_date}
            for f in validated.fields if f.field == "employee_count" for x in f.findings
        ],
        travel_findings=[
            {"claim": x.claim, "signal_type": x.signal_type, "observation": x.observation, "url": x.source_url}
            for f in validated.fields if f.field == "travel_indicators" for x in f.findings
        ],
        conflicts=[c.model_dump() for c in validated.conflicts],
        identity=(validated.company_identity_confirmed, validated.identity_note),
    )
    return out


def run_case(client, label: str, system: str, user: str, max_searches: int, domain: str, version: str) -> None:
    started = datetime.now(timezone.utc).isoformat()
    try:
        res = client.complete(system, user, max_searches)
    except ResearchProviderError as e:
        record = {"case": label, "error": str(e)}
    else:
        record = {
            "case": label,
            "prompt_version": version,
            "model": config.RESEARCH_MODEL,
            "started_at": started,
            "usage": {"input_tokens": res.input_tokens, "output_tokens": res.output_tokens,
                      "web_searches": res.web_search_requests, "llm_calls": res.llm_calls,
                      "approx_cost_usd": estimate_cost(res.input_tokens, res.output_tokens, res.web_search_requests)},
            "stop_reason": res.stop_reason,
            "search_errors": res.search_errors,
            "search_queries": res.search_queries,
            "search_results": res.search_results,
            "system_prompt": system,
            "user_prompt": user,
            "raw_text": res.text,
            "analysis": analyse(res.text, res.search_results, domain),
        }
    dest = OUT / version
    dest.mkdir(parents=True, exist_ok=True)
    path = dest / f"{label}.json"
    path.write_text(json.dumps(record, indent=2, ensure_ascii=False))
    a = record.get("analysis", {})
    print(f"{label}: saved {path.relative_to(config.REPO_DIR)} | parse_ok={a.get('parse_ok')} "
          f"kept={a.get('findings_kept')} dropped={len(a.get('findings_dropped', []))} "
          f"error={record.get('error')}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", default=prompts.CURRENT_VERSION)
    ap.add_argument("--cases", nargs="*", default=[])
    ap.add_argument("--conflict-test", nargs="*", default=[])
    args = ap.parse_args()
    client = AnthropicResearchClient()
    for pid in args.cases:
        c = company(pid)
        v, system, user = prompts.build_standard_prompt(c["company_name"], c["company_domain"], args.version)
        run_case(client, f"{pid}-standard", system, user, config.STANDARD_MAX_SEARCHES, c["company_domain"], v)
    for pid in args.conflict_test:
        c = company(pid)
        focus = {"employee_count": "two inputs disagree across the 150-employee Tier 2 threshold (155 vs 90)"}
        system, user = prompts.build_deep_prompt(c["company_name"], c["company_domain"], focus, SYNTHETIC_CONFLICT)
        run_case(client, f"{pid}-conflict", system, user, config.STANDARD_MAX_SEARCHES, c["company_domain"],
                 args.version)


if __name__ == "__main__":
    main()
