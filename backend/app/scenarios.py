"""In-app scenario checks: deterministic acceptance tests from the PRD that can be shown in
the Reports view. These prove the RULES behave as specified; they say nothing about
real-world predictive accuracy (the dataset has no verified outcome labels).
"""
from __future__ import annotations

from .assessment.day30 import evaluate_day30
from .assessment.flags import build_day0_flags, employee_conflict
from .assessment.signals import EmployeeSource, Signals
from .models import Prospect
from .rules.baseline import calculate_baseline


def _signals(gbv, emps: list[tuple[int, str, str]], accepted_idx=0) -> Signals:
    p = Prospect(id="TEST", company_name="Test Co", domain="test.example", entered_gbv_usd=gbv, applied_tier=2)
    srcs = [EmployeeSource(v, origin, rel, label=f"{origin}") for v, origin, rel in emps]
    s = Signals(prospect=p, gbv=gbv, employee_sources=srcs)
    s.accepted_employee = srcs[accepted_idx] if srcs else None
    s.research_employee_sources = [x for x in srcs if x.origin in ("ai_research", "synthetic_test")]
    s.coverage = {}
    return s


def run_checks() -> list[dict]:
    checks: list[dict] = []

    def check(name, expected, actual):
        checks.append({"name": name, "expected": str(expected), "actual": str(actual), "passed": expected == actual})

    check("GBV $500,000 → Tier 1", 1, calculate_baseline(500_000, None).tier)
    check("GBV $499,999 → Tier 2", 2, calculate_baseline(499_999, None).tier)
    check("GBV $100,000 → Tier 2", 2, calculate_baseline(100_000, 10).tier)
    check("GBV $99,999, 150 employees → Tier 2", 2, calculate_baseline(99_999, 150).tier)
    check("GBV $99,999, 149 employees → Tier 3", 3, calculate_baseline(99_999, 149).tier)
    r = calculate_baseline(48_000, None)
    check("GBV < $100K, employees missing → provisional Tier 3", (3, True), (r.tier, r.provisional))
    check("GBV missing → no tier (data-quality issue, not $0)", None, calculate_baseline(None, 500).tier)
    check("Negative GBV → no tier", None, calculate_baseline(-5, 10).tier)

    c = employee_conflict(_signals(48_000, [(155, "dataset", "enrichment"), (90, "synthetic_test", "synthetic")]))
    check("Employee sources 155 vs 90 with GBV < $100K → material Data Conflict",
          ("data_conflict", "material"), (c["type"], c["severity"]) if c else None)
    c = employee_conflict(_signals(395_000, [(42, "dataset", "enrichment"), (200, "ai_research", "secondary")]))
    check("Conflict across 150 but GBV ≥ $100K → not material", "moderate", c["severity"] if c else None)
    c = employee_conflict(_signals(48_000, [(155, "dataset", "enrichment"),
                                            (90, "human", "manual_verified")], accepted_idx=1))
    check("Verified manual value resolves the conflict → low severity", "low", c["severity"] if c else None)

    s = _signals(30_000, [(20, "dataset", "enrichment")])
    s.prospect.applied_tier = 3
    flags, _ = build_day0_flags(s, calculate_baseline(30_000, 20))
    check("No research evidence → no Travel Potential flag", False, any(f["type"] == "travel_potential" for f in flags))

    d = evaluate_day30(83, 318, 12, 2, [])
    check("Day 30: 83 travelers on Tier 2 → Tier 1 override proposal", 1, (d["proposal"] or {}).get("proposed_tier"))
    d = evaluate_day30(19, 57, 62, 2, [])
    check("Day 30: 19 travelers on Tier 2 → no proposal", None, d["proposal"])
    d = evaluate_day30(20, 50, 30, 3, [])
    check("Day 30: material activity on Tier 3 → Tier 2 override proposal", 2, (d["proposal"] or {}).get("proposed_tier"))
    d = evaluate_day30(5, 19, -22, 3, ["travel_potential"])
    check("Day 30: weak/declining activity after positive Day 0 → 'weakens'", "weakens", d["comparison"])
    d = evaluate_day30(83, 318, 12, 2, [])
    check("Day 30 never produces a dollar GBV estimate", False, any("gbv" in k.lower() for k in d))
    return checks
