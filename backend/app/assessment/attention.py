"""Attention classification and priority ordering.

Attention = WHEN a salesperson should look. It is separate from tier (support level),
reason flags (why) and review status (where a proposal stands).

Priority policy is a prototype hypothesis: impact, then evidence strength, then
actionability. The score is only used for ordering and is shown as High/Medium/Low,
never as a probability or a dollar estimate.
"""
from __future__ import annotations

from typing import Optional

from .flags import FLAG_ORDER, SEVERITY_RANK

ATTENTION_LABELS = {
    "review_now": "Review Now",
    "review_suggested": "Review Suggested",
    "monitor": "Monitor",
}


def classify(flags: list[dict], has_open_proposal: bool) -> Optional[str]:
    if not flags and not has_open_proposal:
        return None
    if has_open_proposal:
        return "review_now"
    if any(f["severity"] == "material" and f["type"] in ("data_conflict", "tier_mismatch") for f in flags):
        return "review_now"
    if any(f["severity"] in ("material", "moderate") for f in flags):
        return "review_suggested"
    return "monitor"


def primary_flag(flags: list[dict]) -> Optional[str]:
    if not flags:
        return None
    return sorted(flags, key=lambda f: (-SEVERITY_RANK[f["severity"]], FLAG_ORDER.index(f["type"])))[0]["type"]


def priority(flags: list[dict], proposals: list[dict], gbv: Optional[float], near: Optional[str]) -> tuple[int, list[str]]:
    score, reasons = 0, []
    # 1. Potential business impact
    if any(p["proposed_tier"] == 1 for p in proposals):
        score += 30
        reasons.append("Impact: possible move to Tier 1 (dedicated AE + AM).")
    elif proposals:
        score += 20
        reasons.append("Impact: possible change between Tier 2 and Tier 3.")
    if near:
        score += 10
        reasons.append(f"Impact: {near}")
    if gbv:
        score += min(int(gbv // 100_000), 5)
    # 2. Evidence strength
    if any(f["type"] == "data_conflict" and f["severity"] == "material" for f in flags):
        score += 10
        reasons.append("Evidence: a conflict that decides tier eligibility.")
    if any(f["type"] == "travel_potential" and f["severity"] == "material" for f in flags):
        score += 10
        reasons.append("Evidence: direct travel indicators from 2+ independent sources.")
    elif any(f["type"] == "travel_potential" for f in flags):
        score += 5
        reasons.append("Evidence: some direct travel or activity evidence.")
    if any(f.get("stage") == "day30" and f["type"] == "tier_mismatch" for f in flags):
        score += 10
        reasons.append("Evidence: observed post-signup activity.")
    # 3. Actionability
    if proposals:
        score += 10
        reasons.append("Actionable: a tier proposal is ready for a decision.")
    if flags and all(f["type"] == "insufficient_evidence" for f in flags):
        score -= 5
    return score, reasons


def priority_label(score: int) -> str:
    return "High" if score >= 40 else "Medium" if score >= 20 else "Low"
