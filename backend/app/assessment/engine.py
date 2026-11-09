"""Deterministic (re)assessment. Never calls the LLM.

Every call writes a NEW Assessment row; earlier rows (including the Day 0 history)
are never modified.
"""
from __future__ import annotations

from typing import Optional

from sqlmodel import Session, select

from .. import audit
from ..models import Assessment, Prospect, TierProposal
from ..rules.baseline import calculate_baseline
from . import attention as att
from .day30 import evaluate_day30
from .flags import build_day0_flags, near_threshold
from .proposals import sync_proposals
from .signals import build_signals


def latest_assessment(session: Session, prospect_id: str, stage: Optional[str] = None) -> Optional[Assessment]:
    q = select(Assessment).where(Assessment.prospect_id == prospect_id)
    if stage:
        q = q.where(Assessment.stage == stage)
    return session.exec(q.order_by(Assessment.id.desc())).first()


def _override_in_effect(session: Session, prospect: Prospect) -> bool:
    if not prospect.applied_tier_source.startswith("proposal:"):
        return False
    p = session.get(TierProposal, int(prospect.applied_tier_source.split(":", 1)[1]))
    return bool(p and p.status == "approved" and p.proposal_type == "evidence_override")


def reassess(session: Session, prospect_id: str, trigger: str, actor: str = "system") -> Assessment:
    prospect = session.get(Prospect, prospect_id)
    if prospect is None:
        raise ValueError(f"Unknown prospect {prospect_id}")
    s = build_signals(session, prospect)
    baseline = calculate_baseline(s.gbv, s.accepted_employees)
    previous = latest_assessment(session, prospect_id)

    flags, candidates = build_day0_flags(s, baseline, _override_in_effect(session, prospect))

    stage = "day0"
    day30 = None
    if s.activity is not None:
        stage = "day30"
        prev_day0 = latest_assessment(session, prospect_id, "day0")
        prev_types = [f["type"] for f in (prev_day0.flags or [])] if prev_day0 else []
        day30 = evaluate_day30(
            s.activity.travelers, s.activity.bookings, s.activity.trend_pct, prospect.applied_tier, prev_types
        )
        day30["compared_with_assessment_id"] = prev_day0.id if prev_day0 else None
        flags.extend(day30["flags"])
        if day30["proposal"]:
            candidates.append({**day30["proposal"], "evidence_ids": [], "basis": {"day30_activity_id": s.activity.id}})

    assessment = Assessment(
        prospect_id=prospect_id,
        stage=stage,
        trigger=trigger,
        applied_tier=prospect.applied_tier,
        baseline=baseline.to_dict(),
        supersedes_id=previous.id if previous else None,
    )
    session.add(assessment)
    session.flush()

    proposal_ids, suppressed = sync_proposals(session, prospect_id, assessment.id, stage, candidates)
    if suppressed and not proposal_ids:
        for f in flags:
            if f["type"] == "tier_mismatch":
                f["severity"] = "low"
                f["reasons"] = f["reasons"] + [x["reason"] for x in suppressed[:1]]
            elif f["type"] == "data_conflict" and f["severity"] == "material":
                # A reviewer has already looked at the proposal this conflict produced. Keep it
                # visible, but stop holding it in Review Now until new evidence arrives.
                f["severity"] = "moderate"
                f["reasons"] = f["reasons"] + ["A reviewer has already reviewed the resulting tier proposal."]
    proposals = [session.get(TierProposal, i) for i in proposal_ids]
    proposal_dicts = [{"id": p.id, "proposed_tier": p.proposed_tier, "status": p.status} for p in proposals]

    near = near_threshold(s, baseline)
    attention = att.classify(flags, bool(proposal_ids))
    score, reasons = att.priority(flags, proposal_dicts, s.gbv, near)

    coverage = {k: dict(v) for k, v in s.coverage.items()}
    if any(f["type"] == "data_conflict" and "Employee" in " ".join(f["reasons"]) for f in flags):
        if coverage["employee_count"]["status"] in ("found", "stale"):
            coverage["employee_count"]["status"] = "conflicting"

    deep = suggest_deep_research(flags, coverage, baseline.provisional, bool(proposal_ids), s.research_ran)

    assessment.flags = flags
    assessment.attention = attention
    assessment.priority_score = score
    assessment.priority_reasons = reasons
    assessment.primary_flag = att.primary_flag(flags)
    assessment.coverage = coverage
    assessment.day30 = day30
    assessment.proposal_ids = proposal_ids
    assessment.accepted_values = {
        "gbv_usd": s.gbv,
        "employees": s.accepted_employees,
        "employee_source": s.accepted_employee.label if s.accepted_employee else None,
        "research_employees": s.research_employee_value,
        "employee_sources": [
            {"value": x.value, "label": x.label, "origin": x.origin, "reliability": x.reliability,
             "as_of": x.as_of, "evidence_id": x.evidence_id, "stale": x.stale}
            for x in s.employee_sources
        ],
        "headcount_history": s.headcount_history,
        "near_threshold": near,
        "research_ran": s.research_ran,
        "research_failed_last": s.research_failed_last,
        "deep_research": deep,
        "suppressed_proposals": [{"title": x["title"], "reason": x["reason"]} for x in suppressed],
    }
    assessment.recommended_action = recommend(flags, proposals, s.research_ran, baseline.provisional, deep, day30)
    session.add(assessment)
    audit.record(
        session, entity_type="assessment", entity_id=assessment.id, prospect_id=prospect_id, actor=actor,
        action="assessed",
        details={
            "stage": stage, "trigger": trigger, "baseline_tier": baseline.tier, "attention": attention,
            "flags": [f["type"] for f in flags], "previous_assessment_id": previous.id if previous else None,
            "llm_calls": 0,
        },
    )
    session.commit()
    session.refresh(assessment)
    return assessment


def suggest_deep_research(flags, coverage, provisional, has_proposal, research_ran) -> dict:
    if not research_ran:
        return {"suggested": False, "reason": "Run standard research first."}
    if any(f["type"] == "data_conflict" and f["severity"] == "material" for f in flags):
        return {"suggested": True, "reason": "A source conflict decides Tier 2 eligibility."}
    if provisional and coverage["employee_count"]["status"] in ("not_found", "stale"):
        return {"suggested": True, "reason": "Employee count is still unknown and decides Tier 2 eligibility."}
    if has_proposal and any(v["status"] in ("not_found", "conflicting", "stale") for v in coverage.values()):
        return {"suggested": True, "reason": "A tier proposal is open and some evidence is missing or disputed."}
    return {"suggested": False, "reason": "No routing-relevant gap that deeper research is likely to resolve."}


def recommend(flags, proposals, research_ran, provisional, deep, day30) -> str:
    unresolved = [p for p in proposals if p.status in ("open", "needs_info")]
    if unresolved:
        p = unresolved[0]
        kind = "standard-rule correction" if p.proposal_type == "standard_rule_correction" else "evidence-based override"
        return f"Review the {kind} proposal: Tier {p.from_tier} → Tier {p.proposed_tier}."
    rank = {"material": 3, "moderate": 2, "low": 1}
    types: dict[str, dict] = {}
    for f in flags:  # keep the most severe flag of each type
        if f["type"] not in types or rank[f["severity"]] > rank[types[f["type"]]["severity"]]:
            types[f["type"]] = f
    if "data_conflict" in types and types["data_conflict"]["severity"] == "material":
        return "Confirm the employee count — it decides Tier 2 eligibility. Use Edit next to Employees, or run Deep Research."
    if "travel_potential" in types and types["travel_potential"]["severity"] != "low":
        return "Check the travel evidence and consider an extra AE touchpoint. No tier change is proposed."
    if "travel_potential" in types:
        return "Travel evidence is consistent with the current support level. No action needed."
    if day30 and day30.get("comparison") == "weakens":
        return "Day 30 activity weakens the earlier signal. No action needed unless new evidence appears."
    if "growth_opportunity" in types:
        return "Keep an eye on this account. Growth signals alone do not justify a tier change."
    if not research_ran:
        if provisional:
            return "Employee count unknown, so Tier 2 eligibility is unresolved. Run standard research or add a known value."
        return "Not researched yet. Run standard research if this account matters."
    if "insufficient_evidence" in types:
        return "Little public information. No action needed now; add details manually if Sales learns more."
    return "No action needed. Current tier is consistent with the available evidence."
