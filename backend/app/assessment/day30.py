"""Day 30 (post-signup) evaluation. Pure functions, no DB.

Booking counts are not dollars. This module never estimates GBV; it only decides
whether observed activity is strong enough to ask a human to look again.
All thresholds are prototype hypotheses in config.py.
"""
from __future__ import annotations

from typing import Optional

from .. import config
from .flags import _flag as make_flag


def evaluate_day30(
    travelers: Optional[int],
    bookings: Optional[int],
    trend_pct: Optional[float],
    applied_tier: Optional[int],
    previous_flags: list[str],
) -> dict:
    caveat = (
        "Booking counts do not establish dollar GBV, and 30 days may not represent a full year."
    )
    out = {
        "travelers": travelers,
        "bookings": bookings,
        "trend_pct": trend_pct,
        "material": False,
        "tier1_candidate": False,
        "weak": False,
        "declining": False,
        "comparison": "neutral",
        "notes": [],
        "flags": [],
        "proposal": None,
    }
    if travelers is None or bookings is None:
        out["notes"].append("Day 30 activity could not be parsed; no conclusion drawn.")
        return out

    t = trend_pct if trend_pct is not None else 0.0
    material = travelers >= config.DAY30_MATERIAL_TRAVELERS or (
        bookings >= config.DAY30_MATERIAL_BOOKINGS and t >= config.DAY30_MATERIAL_TREND_PCT
    )
    tier1_candidate = travelers >= config.DAY30_TIER1_CANDIDATE_TRAVELERS
    weak = travelers <= config.DAY30_WEAK_TRAVELERS
    declining = trend_pct is not None and trend_pct < 0
    out.update(material=material, tier1_candidate=tier1_candidate, weak=weak, declining=declining)

    summary = f"{travelers} travelers, {bookings} bookings in 30 days"
    if trend_pct is not None:
        summary += f", bookings {trend_pct:+.0f}% in days 16–30 vs days 1–15"

    positive_prior = any(f in previous_flags for f in ("travel_potential", "growth_opportunity", "tier_mismatch"))

    if applied_tier == 3 and material:
        out["flags"].append(_day30_flag("tier_mismatch", "material",
            [f"Observed activity ({summary}) is high for a Tier 3 account."], []))
        out["flags"].append(_day30_flag("travel_potential", "moderate", [f"Observed Navan activity: {summary}."], []))
        out["proposal"] = {
            "proposal_type": "evidence_override", "from_tier": 3, "proposed_tier": 2,
            "title": "Day 30 activity suggests Tier 3 → Tier 2 support",
            "rationale": [f"Observed activity: {summary}.",
                          "Standard rules still give Tier 3 from reported GBV and headcount; this is an override recommendation."],
            "uncertainties": [caveat],
        }
        out["comparison"] = "strengthens" if positive_prior else "new_signal"
    elif applied_tier == 2 and tier1_candidate:
        out["flags"].append(_day30_flag("tier_mismatch", "material",
            [f"Observed activity ({summary}) is at the level this policy treats as a Tier 1 candidate."], []))
        out["flags"].append(_day30_flag("travel_potential", "moderate", [f"Observed Navan activity: {summary}."], []))
        out["proposal"] = {
            "proposal_type": "evidence_override", "from_tier": 2, "proposed_tier": 1,
            "title": "Day 30 activity suggests Tier 2 → Tier 1 support",
            "rationale": [f"Observed activity: {summary}.",
                          "Reported GBV is below $500K, so this goes against the standard rule and needs a human decision."],
            "uncertainties": [caveat],
        }
        out["comparison"] = "strengthens" if positive_prior else "new_signal"
    elif material and applied_tier == 1:
        out["comparison"] = "consistent"
        out["notes"].append(f"Day 30 activity ({summary}) is consistent with Tier 1 support. No action needed.")
    elif material:
        growing = t >= config.DAY30_MATERIAL_TREND_PCT
        out["flags"].append(_day30_flag("travel_potential", "moderate" if growing else "low",
            [f"Observed Navan activity: {summary}. Consistent with the current Tier {applied_tier} support level"
             + (" and still growing." if growing else ".")], []))
        out["comparison"] = "strengthens" if positive_prior else "consistent"
    elif not weak and not declining and t >= config.DAY30_MATERIAL_TREND_PCT:
        out["flags"].append(_day30_flag("growth_opportunity", "moderate",
            [f"Early activity is growing ({summary}), though volume is still below the review threshold."], []))
        out["comparison"] = "strengthens" if positive_prior else "new_signal"
    else:
        if positive_prior:
            out["comparison"] = "weakens"
            out["notes"].append(
                f"Day 30 activity ({summary}) is weak or declining and weakens the earlier Day 0 signal."
            )
        else:
            out["comparison"] = "consistent"
            out["notes"].append(f"Day 30 activity ({summary}) does not change the earlier assessment.")
    return out


def _day30_flag(ftype: str, severity: str, reasons: list[str], uncertainty: list[str]) -> dict:
    return make_flag(ftype, severity, reasons, uncertainty=uncertainty, stage="day30")
