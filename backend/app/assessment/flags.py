"""Deterministic reason flags and tier-change candidates.

Every flag carries the reasons it fired, the evidence ids behind it, and any open
uncertainty. Growth is never treated as proof of higher GBV.
"""
from __future__ import annotations

from typing import Optional

from .. import config
from ..rules.baseline import BaselineResult, calculate_baseline
from .signals import EmployeeSource, Signals, independent_hosts

FLAG_LABELS = {
    "tier_mismatch": "Tier Mismatch",
    "data_conflict": "Data Conflict",
    "travel_potential": "Travel Potential",
    "growth_opportunity": "Growth Opportunity",
    "insufficient_evidence": "Insufficient Evidence",
}
# Display/priority order for picking the primary flag.
FLAG_ORDER = ["tier_mismatch", "data_conflict", "travel_potential", "growth_opportunity", "insufficient_evidence"]
SEVERITY_RANK = {"material": 3, "moderate": 2, "low": 1}

ROUTING_FIELDS = {"employee_count", "travel_indicators"}
GROWTH_FIELDS = {"funding_financial", "recent_expansion", "hiring_trends", "geographic_footprint"}


def _flag(ftype, severity, reasons, evidence_ids=None, uncertainty=None, stage="day0") -> dict:
    return {
        "type": ftype,
        "label": FLAG_LABELS[ftype],
        "severity": severity,
        "reasons": reasons,
        "evidence_ids": sorted(set(evidence_ids or [])),
        "uncertainty": uncertainty or [],
        "stage": stage,
    }


def _side(v: int) -> bool:
    return v >= config.TIER2_EMPLOYEES_MIN


def employee_conflict(s: Signals) -> Optional[dict]:
    srcs = s.employee_sources
    if len(srcs) < 2:
        return None
    gbv_decides = s.gbv is not None and s.gbv < config.TIER2_GBV_MIN
    crossing = len({_side(x.value) for x in srcs}) > 1
    lo, hi = min(x.value for x in srcs), max(x.value for x in srcs)
    big_gap = lo == 0 or (hi - lo) / max(lo, 1) > config.EMPLOYEE_CONFLICT_RATIO
    if not crossing and not big_gap:
        return None
    desc = "; ".join(f"{x.label}: {x.value:,}" + (f" (as of {x.as_of})" if x.as_of else "") for x in srcs)
    evidence_ids = [x.evidence_id for x in srcs if x.evidence_id]
    uncertainty = []
    if any(x.origin == "synthetic_test" for x in srcs):
        uncertainty.append("Includes a SYNTHETIC test observation, not public research.")
    if any(x.reliability == "aggregator" for x in srcs):
        uncertainty.append("Some employee figures come from data aggregators, which are often estimates.")
    if any(x.stale for x in srcs):
        uncertainty.append("Some employee figures are stale.")

    resolved = s.accepted_employee is not None and s.accepted_employee.reliability == "manual_verified"
    if resolved:
        return _flag("data_conflict", "low",
                     [f"Employee sources disagree ({desc}), but a verified manual value "
                      f"({s.accepted_employee.value:,}) is now used for the tier rules."],
                     evidence_ids, uncertainty)
    if crossing and gbv_decides:
        return _flag("data_conflict", "material",
                     [f"Employee sources fall on both sides of the {config.TIER2_EMPLOYEES_MIN}-employee "
                      f"Tier 2 threshold ({desc}). Reported GBV is below $100K, so this decides Tier 2 eligibility."],
                     evidence_ids, uncertainty)
    if crossing:
        return _flag("data_conflict", "moderate",
                     [f"Employee sources fall on both sides of {config.TIER2_EMPLOYEES_MIN} ({desc}). "
                      "Reported GBV already sets the tier, so the tier does not change today."],
                     evidence_ids, uncertainty)
    return _flag("data_conflict", "low", [f"Employee sources differ by more than 50% ({desc})."],
                 evidence_ids, uncertainty)


def build_day0_flags(
    s: Signals, baseline: BaselineResult, override_in_effect: bool = False
) -> tuple[list[dict], list[dict]]:
    """Return (flags, proposal_candidates) using only signup-time information.

    `override_in_effect`: a reviewer approved an evidence-based override, so the applied
    tier intentionally differs from the standard rules and must not be "corrected" back.
    """
    p = s.prospect
    flags: list[dict] = []
    candidates: list[dict] = []
    applied = p.applied_tier

    # --- Data Conflict ------------------------------------------------------
    conflict = employee_conflict(s)
    if conflict:
        flags.append(conflict)
    for c in s.llm_conflicts:
        # Only conflicts in fields that can affect routing become flags. Others (e.g. differing
        # funding totals) stay visible in the research section without raising attention.
        if c.get("field") not in ROUTING_FIELDS or (c.get("field") == "employee_count" and conflict):
            continue
        flags.append(_flag("data_conflict", "low",
                           [f"Research reported conflicting sources for {c.get('field', 'a field').replace('_', ' ')}: "
                            f"{c.get('description', '')}"]))

    # --- Travel Potential (direct evidence only) --------------------------------
    if s.direct_travel:
        hosts = independent_hosts(s.direct_travel)
        only_unverified_manual = all(e.reliability == "manual_unverified" for e in s.direct_travel)
        strong = len(hosts) >= 2 and not only_unverified_manual
        reasons = [f"{len(s.direct_travel)} direct travel indicator(s) from {len(hosts)} independent source(s)."]
        reasons += [f"“{e.claim}”" for e in s.direct_travel[:3]]
        unc = []
        if only_unverified_manual:
            unc.append("Based only on unverified manual input.")
        if any(e.origin == "synthetic_test" for e in s.direct_travel):
            unc.append("Includes a SYNTHETIC test observation.")
        if len(hosts) < 2:
            unc.append("Only one independent source.")
        unc.append("Travel indicators do not tell us annual travel spend.")
        flags.append(_flag("travel_potential", "material" if strong else "moderate", reasons,
                           [e.id for e in s.direct_travel], unc))
        if strong and applied == 3:
            candidates.append({
                "proposal_type": "evidence_override", "from_tier": 3, "proposed_tier": 2,
                "title": "Direct travel evidence suggests Tier 3 → Tier 2 support",
                "basis": {},
                "rationale": [
                    "Two or more independent sources show employees travel for work.",
                    "Standard rules give Tier 3 from reported GBV and headcount; this is an override recommendation.",
                ],
                "evidence_ids": [e.id for e in s.direct_travel],
                "uncertainties": unc,
            })

    # --- Growth Opportunity (indirect, never proof of GBV) ------------------------
    growth_fields = {e.field for e in s.growth if e.field in GROWTH_FIELDS}
    if len(growth_fields) >= config.GROWTH_MIN_INDEPENDENT_SIGNALS:
        near = near_threshold(s, baseline)
        reasons = [f"Independent growth signals in: {', '.join(sorted(f.replace('_', ' ') for f in growth_fields))}."]
        reasons += [f"“{e.claim}”" for e in s.growth[:3]]
        if near:
            reasons.append(near)
        flags.append(_flag("growth_opportunity", "moderate" if near else "low", reasons,
                           [e.id for e in s.growth],
                           ["Company growth is not evidence of higher travel spend (GBV).",
                            "Several articles about the same announcement count as one signal."]))

    # --- Insufficient Evidence -----------------------------------------------
    insufficient: list[str] = []
    if baseline.tier is None:
        insufficient.append("Annual GBV is missing or invalid, so no baseline tier can be calculated.")
    if baseline.provisional and not s.research_employee_sources:
        insufficient.append("No employee count from any source; Tier 2 eligibility by headcount is unresolved.")
    if s.research_ran:
        searched = [v for v in s.coverage.values() if v["status"] != "not_searched"]
        nf = [v for v in searched if v["status"] == "not_found"]
        if searched and len(nf) >= 5:
            insufficient.append(f"Research found nothing usable for {len(nf)} of {len(searched)} fields.")
    if insufficient:
        flags.append(_flag("insufficient_evidence", "low", insufficient,
                           uncertainty=["Missing information is not evidence that the company does not travel."]))

    # --- Tier Mismatch (standard rules) ------------------------------------------
    if baseline.tier is not None and applied is not None and baseline.tier != applied and not override_in_effect:
        src = s.accepted_employee
        why = [baseline.basis]
        if src and src.origin == "human":
            why.append(f"Employee count {src.value:,} comes from {src.label}.")
        candidates.append({
            "proposal_type": "standard_rule_correction", "from_tier": applied, "proposed_tier": baseline.tier,
            "title": f"Standard rules give Tier {baseline.tier} (currently Tier {applied})",
            "basis": {"employees": s.accepted_employees, "gbv": s.gbv},
            "rationale": why,
            "evidence_ids": [src.evidence_id] if src and src.evidence_id else [],
            "uncertainties": (["Employee count is an unverified manual value."]
                              if src and src.reliability == "manual_unverified" else []),
        })

    # Research-implied tier: what the standard rules would say if research headcount were accepted.
    rv = s.research_employee_value
    if rv is not None and rv != s.accepted_employees and applied is not None:
        rb = calculate_baseline(s.gbv, rv)
        if rb.tier is not None and rb.tier != applied and rb.tier != baseline.tier:
            r_srcs: list[EmployeeSource] = s.research_employee_sources
            unc = []
            if any(x.reliability == "aggregator" for x in r_srcs):
                unc.append("Research headcount comes partly from data aggregators (estimates).")
            if any(x.origin == "synthetic_test" for x in r_srcs):
                unc.append("Research headcount includes a SYNTHETIC test observation.")
            if s.accepted_employees is not None:
                unc.append(f"Enrichment/accepted value is {s.accepted_employees:,}; sources disagree.")
            candidates.append({
                "proposal_type": "standard_rule_correction", "from_tier": applied, "proposed_tier": rb.tier,
                "title": f"Research headcount implies Tier {rb.tier} under standard rules (currently Tier {applied})",
                "basis": {"employees": rv, "gbv": s.gbv, "employee_source": "research"},
                "rationale": [
                    f"Research headcount {rv:,} (" + "; ".join(f"{x.label}: {x.value:,}" for x in r_srcs) + ").",
                    rb.basis,
                    "Approving accepts this headcount as the value used for the tier rules.",
                ],
                "evidence_ids": [x.evidence_id for x in r_srcs if x.evidence_id],
                "uncertainties": unc,
            })

    if candidates:
        flags.append(_flag(
            "tier_mismatch", "material",
            [c["title"] for c in candidates],
            [i for c in candidates for i in c["evidence_ids"]],
            sorted({u for c in candidates for u in c["uncertainties"]}),
        ))
    return flags, candidates


def near_threshold(s: Signals, baseline: BaselineResult) -> Optional[str]:
    g = s.gbv
    if g is not None:
        for cut, label in ((config.TIER1_GBV_MIN, "Tier 1"), (config.TIER2_GBV_MIN, "Tier 2")):
            if cut * (1 - config.NEAR_THRESHOLD_GBV_PCT) <= g < cut:
                return f"Reported GBV ${g:,.0f} is within {config.NEAR_THRESHOLD_GBV_PCT:.0%} of the {label} threshold."
    e = s.accepted_employees
    if e is not None and (g is None or g < config.TIER2_GBV_MIN):
        lo = config.TIER2_EMPLOYEES_MIN * (1 - config.NEAR_THRESHOLD_EMP_PCT)
        hi = config.TIER2_EMPLOYEES_MIN * (1 + config.NEAR_THRESHOLD_EMP_PCT)
        if lo <= e <= hi:
            return f"Headcount {e:,} is close to the {config.TIER2_EMPLOYEES_MIN}-employee Tier 2 threshold."
    return None
