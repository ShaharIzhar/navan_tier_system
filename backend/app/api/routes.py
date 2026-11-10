from __future__ import annotations

from collections import Counter
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from .. import config, scenarios
from ..assessment.attention import ATTENTION_LABELS, priority_label
from ..assessment.engine import latest_assessment, reassess
from ..assessment.flags import FLAG_LABELS
from ..db import get_session
from ..enrichment import EnrichmentError, add_enrichment, add_synthetic_evidence, retract_evidence
from ..models import (Assessment, AuditEvent, Evidence, PostSignupActivity, Prospect, ResearchRun,
                      ReviewDecision, TierProposal)
from ..postsignup import release_all, release_day30, remove_day30, update_day30
from ..research import service as research
from ..research.schema import RESEARCH_FIELDS
from ..reviews.service import ReviewError, decide

router = APIRouter(prefix="/api")

REVIEW_STATUS_LABELS = {
    "open": "Awaiting review", "needs_info": "Needs info", "approved": "Approved",
    "rejected": "Rejected", "superseded": "No longer needed",
}


# ---------------------------------------------------------------------------
# Serialisers
# ---------------------------------------------------------------------------
def _assessment_dict(a: Optional[Assessment]) -> Optional[dict]:
    if a is None:
        return None
    return {
        "id": a.id, "stage": a.stage, "trigger": a.trigger, "created_at": a.created_at.isoformat(),
        "applied_tier": a.applied_tier, "baseline": a.baseline, "accepted_values": a.accepted_values,
        "flags": a.flags or [], "attention": a.attention,
        "attention_label": ATTENTION_LABELS.get(a.attention) if a.attention else "No action",
        "priority_score": a.priority_score, "priority": priority_label(a.priority_score),
        "priority_reasons": a.priority_reasons or [], "primary_flag": a.primary_flag,
        "primary_flag_label": FLAG_LABELS.get(a.primary_flag) if a.primary_flag else None,
        "recommended_action": a.recommended_action, "coverage": a.coverage or {}, "day30": a.day30,
        "proposal_ids": a.proposal_ids or [], "supersedes_id": a.supersedes_id,
    }


def _evidence_dict(e: Evidence) -> dict:
    return {
        "id": e.id, "run_id": e.run_id, "field": e.field, "claim": e.claim, "value_number": e.value_number,
        "signal_type": e.signal_type, "observation": e.observation, "travel_scope": e.travel_scope, "source_title": e.source_title,
        "source_url": e.source_url, "publisher": e.publisher, "published_date": e.published_date,
        "retrieved_at": e.retrieved_at.isoformat() if e.retrieved_at else None, "reliability": e.reliability,
        "origin": e.origin, "is_stale": e.is_stale, "accepted_for_reassessment": e.accepted_for_reassessment,
        "entered_by": e.entered_by, "note": e.note, "superseded_by": e.superseded_by,
        "created_at": e.created_at.isoformat(),
    }


def _run_dict(r: ResearchRun, include_raw: bool = False) -> dict:
    d = {
        "id": r.id, "kind": r.kind, "status": r.status, "stage": r.stage, "prompt_version": r.prompt_version, "model": r.model,
        "replayed": r.replayed,
        "focus_fields": r.focus_fields, "started_at": r.started_at.isoformat(),
        "finished_at": r.finished_at.isoformat() if r.finished_at else None,
        "research_cutoff": r.research_cutoff.isoformat(), "input_tokens": r.input_tokens,
        "output_tokens": r.output_tokens, "web_search_requests": r.web_search_requests, "llm_calls": r.llm_calls,
        "approx_cost_usd": r.approx_cost_usd, "error": r.error, "summary": r.summary,
        "limitations": r.limitations or [], "dropped_findings": r.dropped_findings or [],
        "normalized_findings": r.normalized_findings or [], "search_queries": r.search_queries or [],
        "conflicts": (r.parsed or {}).get("conflicts", []),
        "search_result_count": len(r.searched_results or []),
    }
    if include_raw:
        d["raw_text"] = r.raw_text
        d["searched_results"] = r.searched_results
    return d


def _proposal_dict(p: TierProposal) -> dict:
    return {
        "id": p.id, "prospect_id": p.prospect_id, "assessment_id": p.assessment_id, "stage": p.stage,
        "proposal_type": p.proposal_type, "from_tier": p.from_tier, "proposed_tier": p.proposed_tier,
        "title": p.title, "basis": p.basis, "rationale": p.rationale or [], "evidence_ids": p.evidence_ids or [],
        "uncertainties": p.uncertainties or [], "linked_assessment_ids": p.linked_assessment_ids or [],
        "status": p.status, "status_label": REVIEW_STATUS_LABELS.get(p.status, p.status),
        "created_at": p.created_at.isoformat(), "updated_at": p.updated_at.isoformat(),
    }


def _review_status(session: Session, prospect_id: str) -> Optional[str]:
    props = list(session.exec(select(TierProposal).where(TierProposal.prospect_id == prospect_id)
                              .order_by(TierProposal.updated_at.desc())))
    for status in ("open", "needs_info"):
        if any(p.status == status for p in props):
            return REVIEW_STATUS_LABELS[status]
    decided = [p for p in props if p.status in ("approved", "rejected")]
    return REVIEW_STATUS_LABELS[decided[0].status] if decided else None


def _suggestion(session: Session, prospect_id: str) -> Optional[dict]:
    """The tier change waiting for a human decision, if any."""
    p = session.exec(select(TierProposal).where(TierProposal.prospect_id == prospect_id,
                                                TierProposal.status.in_(("open", "needs_info")))
                     .order_by(TierProposal.id.desc())).first()
    if p is None:
        return None
    return {"proposal_id": p.id, "from_tier": p.from_tier, "to_tier": p.proposed_tier, "title": p.title,
            "type": p.proposal_type, "status": p.status}


def _prospect_row(session: Session, p: Prospect) -> dict:
    a = latest_assessment(session, p.id)
    last_run = session.exec(select(ResearchRun).where(ResearchRun.prospect_id == p.id)
                            .order_by(ResearchRun.id.desc())).first()
    act = session.exec(select(PostSignupActivity).where(PostSignupActivity.prospect_id == p.id)).first()
    return {
        "id": p.id, "company_name": p.company_name, "domain": p.domain,
        "entered_gbv_usd": p.entered_gbv_usd, "zi_employees": p.zi_employees,
        "original_tier": p.original_tier, "applied_tier": p.applied_tier,
        "baseline_tier": (a.baseline or {}).get("tier") if a else None,
        "baseline_provisional": (a.baseline or {}).get("provisional") if a else None,
        "attention": a.attention if a else None,
        "attention_label": (ATTENTION_LABELS.get(a.attention) if a and a.attention else "No action"),
        "priority_score": a.priority_score if a else 0,
        "priority": priority_label(a.priority_score) if a else "Low",
        "primary_flag": a.primary_flag if a else None,
        "primary_flag_label": FLAG_LABELS.get(a.primary_flag) if a and a.primary_flag else None,
        "flags": sorted({f["type"] for f in (a.flags or [])}) if a else [],
        "review_status": _review_status(session, p.id),
        "suggestion": _suggestion(session, p.id),
        "research_status": (last_run.status if last_run else "not_researched"),
        "stage": a.stage if a else "day0",
        "day30_available": bool(act and act.released_at),
        "data_quality_notes": p.data_quality_notes or [],
    }


# ---------------------------------------------------------------------------
# Prospects
# ---------------------------------------------------------------------------
@router.get("/meta")
def meta():
    return {
        "provider": research.provider_status(),
        "research_fields": RESEARCH_FIELDS,
        "flag_labels": FLAG_LABELS,
        "attention_labels": ATTENTION_LABELS,
        "auto_research_ids": config.AUTO_RESEARCH_IDS,
        "thresholds": {
            "tier1_gbv": config.TIER1_GBV_MIN, "tier2_gbv": config.TIER2_GBV_MIN,
            "tier2_employees": config.TIER2_EMPLOYEES_MIN,
            "day30_material_travelers": config.DAY30_MATERIAL_TRAVELERS,
            "day30_material_bookings": config.DAY30_MATERIAL_BOOKINGS,
            "day30_material_trend_pct": config.DAY30_MATERIAL_TREND_PCT,
            "stale_after_days": config.STALE_AFTER_DAYS,
        },
    }


@router.get("/prospects")
def list_prospects(session: Session = Depends(get_session)):
    rows = [_prospect_row(session, p) for p in session.exec(select(Prospect).order_by(Prospect.id))]
    return rows


@router.get("/prospects/{prospect_id}")
def get_prospect(prospect_id: str, session: Session = Depends(get_session)):
    p = session.get(Prospect, prospect_id)
    if p is None:
        raise HTTPException(404, "Prospect not found")
    assessments = list(session.exec(select(Assessment).where(Assessment.prospect_id == prospect_id)
                                    .order_by(Assessment.id.desc())))
    evidence = list(session.exec(select(Evidence).where(Evidence.prospect_id == prospect_id).order_by(Evidence.id)))
    runs = list(session.exec(select(ResearchRun).where(ResearchRun.prospect_id == prospect_id)
                             .order_by(ResearchRun.id.desc())))
    proposals = list(session.exec(select(TierProposal).where(TierProposal.prospect_id == prospect_id)
                                  .order_by(TierProposal.id.desc())))
    act = session.exec(select(PostSignupActivity).where(PostSignupActivity.prospect_id == prospect_id)).first()
    audit_rows = list(session.exec(select(AuditEvent).where(AuditEvent.prospect_id == prospect_id)
                                   .order_by(AuditEvent.id.desc())))
    return {
        "prospect": _prospect_row(session, p),
        "assessment": _assessment_dict(assessments[0] if assessments else None),
        "history": [
            {"id": a.id, "stage": a.stage, "trigger": a.trigger, "created_at": a.created_at.isoformat(),
             "applied_tier": a.applied_tier, "baseline_tier": (a.baseline or {}).get("tier"),
             "attention": a.attention, "flags": [f["type"] for f in (a.flags or [])],
             "accepted_employees": (a.accepted_values or {}).get("employees")}
            for a in assessments
        ],
        "evidence": [_evidence_dict(e) for e in evidence],
        "research_runs": [_run_dict(r) for r in runs],
        "proposals": [_proposal_dict(x) for x in proposals],
        "day30": (
            {"received": act.released_at is not None,
             "released_at": act.released_at.isoformat() if act.released_at else None,
             **({"raw_text": act.raw_text, "travelers": act.travelers, "bookings": act.bookings,
                 "trend_pct": act.trend_pct, "trend_basis": act.trend_basis, "remarks": act.remarks} if act.released_at else {})}
            if act else {"received": False, "exists": False}
        ),
        "day30_pending": bool(act and act.released_at is None),
        "audit": [
            {"id": e.id, "entity_type": e.entity_type, "entity_id": e.entity_id, "action": e.action,
             "actor": e.actor, "details": e.details, "created_at": e.created_at.isoformat()}
            for e in audit_rows
        ],
    }


@router.get("/assessments/{assessment_id}")
def get_assessment(assessment_id: int, session: Session = Depends(get_session)):
    a = session.get(Assessment, assessment_id)
    if a is None:
        raise HTTPException(404, "Assessment not found")
    return _assessment_dict(a)


@router.get("/research-runs/{run_id}")
def get_run(run_id: int, session: Session = Depends(get_session)):
    r = session.get(ResearchRun, run_id)
    if r is None:
        raise HTTPException(404, "Run not found")
    return _run_dict(r, include_raw=True)


class ResearchRequest(BaseModel):
    force: bool = False
    actor: str = "user"


@router.post("/prospects/{prospect_id}/research")
def post_research(prospect_id: str, body: ResearchRequest, session: Session = Depends(get_session)):
    if session.get(Prospect, prospect_id) is None:
        raise HTTPException(404, "Prospect not found")
    run = research.run_standard_research(session, prospect_id, force=body.force, actor=body.actor)
    return _run_dict(run)


@router.get("/prospects/{prospect_id}/deep-research/plan")
def get_deep_plan(prospect_id: str, session: Session = Depends(get_session)):
    return research.deep_research_plan(session, prospect_id)


class DeepRequest(BaseModel):
    confirm: bool = False
    focus_fields: Optional[list[str]] = None
    actor: str = "user"


@router.post("/prospects/{prospect_id}/deep-research")
def post_deep(prospect_id: str, body: DeepRequest, session: Session = Depends(get_session)):
    if not body.confirm:
        raise HTTPException(400, "Deep Research is an additional paid operation and requires confirm=true.")
    run, _ = research.start_deep_research(session, prospect_id, body.focus_fields, actor=body.actor)
    return _run_dict(run)


@router.get("/prospects/{prospect_id}/active-research")
def get_active_research(prospect_id: str, session: Session = Depends(get_session)):
    """Progress of a running research job (polled by the company page)."""
    r = research.active_run(session, prospect_id)
    if r is None:
        last = session.exec(select(ResearchRun).where(ResearchRun.prospect_id == prospect_id)
                            .order_by(ResearchRun.id.desc())).first()
        return {"running": False, "last": _run_dict(last) if last else None}
    return {"running": True, "run": _run_dict(r), "expected_seconds": research.DEEP_EXPECTED_SECONDS}


class EnrichmentRequest(BaseModel):
    param: str
    value: str
    entered_by: str
    source_url: Optional[str] = None
    note: Optional[str] = None
    verified: bool = False
    accepted: bool = True


@router.post("/prospects/{prospect_id}/enrichment")
def post_enrichment(prospect_id: str, body: EnrichmentRequest, session: Session = Depends(get_session)):
    try:
        e, after, before = add_enrichment(session, prospect_id, body.param, body.value, body.entered_by,
                                          body.source_url, body.note, body.verified, body.accepted)
    except EnrichmentError as err:
        raise HTTPException(400, str(err))
    return {"evidence": _evidence_dict(e), "before": _assessment_dict(before), "after": _assessment_dict(after),
            "llm_calls": 0}


class SyntheticRequest(BaseModel):
    field: str = "employee_count"
    claim: str
    value_number: Optional[float] = None
    signal_type: str = "descriptive"
    entered_by: str = "test"


@router.post("/prospects/{prospect_id}/synthetic-evidence")
def post_synthetic(prospect_id: str, body: SyntheticRequest, session: Session = Depends(get_session)):
    if body.field not in RESEARCH_FIELDS:
        raise HTTPException(400, "Unknown field")
    e = add_synthetic_evidence(session, prospect_id, body.field, body.claim, body.value_number,
                               body.signal_type, body.entered_by)
    return _evidence_dict(e)


class RetractRequest(BaseModel):
    actor: str
    reason: str


@router.post("/evidence/{evidence_id}/withdraw")
def post_withdraw(evidence_id: int, body: RetractRequest, session: Session = Depends(get_session)):
    try:
        e = retract_evidence(session, evidence_id, body.actor, body.reason)
    except EnrichmentError as err:
        raise HTTPException(400, str(err))
    return _evidence_dict(e)


@router.post("/prospects/{prospect_id}/reassess")
def post_reassess(prospect_id: str, session: Session = Depends(get_session)):
    if session.get(Prospect, prospect_id) is None:
        raise HTTPException(404, "Prospect not found")
    return _assessment_dict(reassess(session, prospect_id, trigger="manual", actor="user"))


@router.post("/prospects/{prospect_id}/day30/release")
def post_release(prospect_id: str, session: Session = Depends(get_session)):
    a = release_day30(session, prospect_id, actor="user")
    if a is None:
        raise HTTPException(404, "No post-signup activity exists for this prospect.")
    return _assessment_dict(a)


class Day30Update(BaseModel):
    travelers: int
    bookings: int
    trend_pct: Optional[float] = None
    remarks: Optional[str] = None
    actor: str = "user"


@router.put("/prospects/{prospect_id}/day30")
def put_day30(prospect_id: str, body: Day30Update, session: Session = Depends(get_session)):
    if session.get(Prospect, prospect_id) is None:
        raise HTTPException(404, "Prospect not found")
    try:
        return _assessment_dict(update_day30(session, prospect_id, body.travelers, body.bookings, body.trend_pct, body.actor, body.remarks))
    except ValueError as err:
        raise HTTPException(400, str(err))


@router.delete("/prospects/{prospect_id}/day30")
def delete_day30(prospect_id: str, actor: str = "user", session: Session = Depends(get_session)):
    try:
        return _assessment_dict(remove_day30(session, prospect_id, actor))
    except ValueError as err:
        raise HTTPException(400, str(err))


@router.post("/day30/release-all")
def post_release_all(session: Session = Depends(get_session)):
    return {"released": release_all(session, actor="user")}


# ---------------------------------------------------------------------------
# Proposals / reviews
# ---------------------------------------------------------------------------
@router.get("/proposals")
def list_proposals(status: Optional[str] = None, session: Session = Depends(get_session)):
    q = select(TierProposal).order_by(TierProposal.id.desc())
    if status:
        q = q.where(TierProposal.status == status)
    out = []
    for p in session.exec(q):
        d = _proposal_dict(p)
        pr = session.get(Prospect, p.prospect_id)
        d["company_name"] = pr.company_name if pr else p.prospect_id
        d["domain"] = pr.domain if pr else None
        out.append(d)
    return out


@router.get("/proposals/{proposal_id}")
def get_proposal(proposal_id: int, session: Session = Depends(get_session)):
    p = session.get(TierProposal, proposal_id)
    if p is None:
        raise HTTPException(404, "Proposal not found")
    prospect = session.get(Prospect, p.prospect_id)
    ev = [session.get(Evidence, i) for i in (p.evidence_ids or [])]
    linked = [session.get(Assessment, i) for i in (p.linked_assessment_ids or [])]
    decisions = list(session.exec(select(ReviewDecision).where(ReviewDecision.proposal_id == proposal_id)
                                  .order_by(ReviewDecision.id)))
    current = latest_assessment(session, p.prospect_id)
    history = list(session.exec(select(Assessment).where(Assessment.prospect_id == p.prospect_id)
                                .order_by(Assessment.id.desc())))
    audit_rows = list(session.exec(select(AuditEvent).where(AuditEvent.prospect_id == p.prospect_id)
                                   .order_by(AuditEvent.id.desc())))
    return {
        "proposal": _proposal_dict(p),
        "prospect": _prospect_row(session, prospect),
        "evidence": [_evidence_dict(e) for e in ev if e],
        "assessment_at_creation": _assessment_dict(session.get(Assessment, p.assessment_id)),
        "current_assessment": _assessment_dict(current),
        "linked_assessments": [_assessment_dict(a) for a in linked if a],
        "history": [
            {"id": a.id, "stage": a.stage, "trigger": a.trigger, "created_at": a.created_at.isoformat(),
             "applied_tier": a.applied_tier, "baseline_tier": (a.baseline or {}).get("tier"),
             "attention": a.attention, "flags": [f["type"] for f in (a.flags or [])]}
            for a in history
        ],
        "decisions": [
            {"id": d.id, "action": d.action, "reviewer": d.reviewer, "comment": d.comment,
             "tier_before": d.tier_before, "tier_after": d.tier_after, "created_at": d.created_at.isoformat()}
            for d in decisions
        ],
        "audit": [
            {"id": e.id, "entity_type": e.entity_type, "entity_id": e.entity_id, "action": e.action,
             "actor": e.actor, "details": e.details, "created_at": e.created_at.isoformat()}
            for e in audit_rows
        ],
    }


@router.post("/proposals/{proposal_id}/judge")
def post_judge(proposal_id: int, force: bool = False, session: Session = Depends(get_session)):
    from ..research.judge import get_or_create_judgement

    if session.get(TierProposal, proposal_id) is None:
        raise HTTPException(404, "Proposal not found")
    return get_or_create_judgement(session, proposal_id, force=force, actor="user")


class DecisionRequest(BaseModel):
    action: str
    reviewer: str
    comment: Optional[str] = None


@router.post("/proposals/{proposal_id}/decision")
def post_decision(proposal_id: int, body: DecisionRequest, session: Session = Depends(get_session)):
    try:
        p = decide(session, proposal_id, body.action, body.reviewer, body.comment)
    except ReviewError as err:
        raise HTTPException(400, str(err))
    return _proposal_dict(p)


# ---------------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------------
@router.get("/reports")
def reports(session: Session = Depends(get_session)):
    prospects = list(session.exec(select(Prospect)))
    latest = {p.id: latest_assessment(session, p.id) for p in prospects}
    runs = list(session.exec(select(ResearchRun)))
    proposals = list(session.exec(select(TierProposal)))
    decisions = list(session.exec(select(ReviewDecision)))
    evidence = list(session.exec(select(Evidence)))

    flag_counts = Counter(f["type"] for a in latest.values() if a for f in (a.flags or []))
    attention_counts = Counter((a.attention or "none") for a in latest.values() if a)
    coverage_counts: dict[str, Counter] = {f: Counter() for f in RESEARCH_FIELDS}
    researched = 0
    for a in latest.values():
        if a and (a.accepted_values or {}).get("research_ran"):
            researched += 1
            for f, v in (a.coverage or {}).items():
                coverage_counts[f][v["status"]] += 1

    ev_by_id = {e.id: e for e in evidence}
    unsupported = []
    for p in proposals:
        ev = [ev_by_id[i] for i in (p.evidence_ids or []) if i in ev_by_id]
        reasons = []
        if not ev and p.proposal_type == "evidence_override" and p.stage != "day30":
            reasons.append("No cited evidence")
        if ev and all(e.reliability in ("aggregator", "synthetic") for e in ev):
            reasons.append("Relies only on aggregator or synthetic evidence")
        if ev and all(e.observation == "inferred" for e in ev):
            reasons.append("Relies only on inferences")
        if reasons:
            unsupported.append({"proposal_id": p.id, "prospect_id": p.prospect_id, "title": p.title,
                                "reasons": reasons})

    # Retrospective Day 0 vs Day 30 comparison. Evaluation only; never used for Day 0 routing.
    retro = []
    for p in prospects:
        a = latest.get(p.id)
        if not a or a.stage != "day30" or not a.day30:
            continue
        day0 = latest_assessment(session, p.id, "day0")
        d0_flags = sorted({f["type"] for f in (day0.flags or [])}) if day0 else []
        # Only opportunity claims can be "missed" or "unnecessary". Insufficient Evidence and
        # Data Conflict describe data quality, not a prediction.
        d0_opp = [f for f in d0_flags if f in ("travel_potential", "growth_opportunity", "tier_mismatch")]
        researched = bool(day0 and (day0.accepted_values or {}).get("research_ran"))
        d30 = a.day30
        if (day0.applied_tier if day0 else None) == 1:
            label = "Already Tier 1 at signup; nothing to miss"
        elif d30.get("material") and not d0_opp:
            label = "Possible miss at Day 0 (strong activity, no opportunity flag)" + ("" if researched else "; not researched at Day 0")
        elif d30.get("material"):
            label = "Day 0 opportunity flag consistent with activity"
        elif d0_opp and (d30.get("weak") or d30.get("declining")):
            label = "Possible unnecessary Day 0 flag (activity weak or declining)"
        else:
            label = "No clear signal either way"
        retro.append({"prospect_id": p.id, "company_name": p.company_name, "day0_flags": d0_flags,
                      "day0_attention": day0.attention if day0 else None, "travelers": d30.get("travelers"),
                      "bookings": d30.get("bookings"), "trend_pct": d30.get("trend_pct"), "label": label})

    ok_runs = [r for r in runs if r.status in ("ok", "partial")]
    return {
        "totals": {
            "prospects": len(prospects),
            "assessed": sum(1 for a in latest.values() if a),
            "researched": researched,
            "research_runs": len(runs),
            "research_failed": sum(1 for r in runs if r.status == "failed"),
            "day30_received": sum(1 for a in latest.values() if a and a.stage == "day30"),
        },
        "attention": dict(attention_counts),
        "flags": {FLAG_LABELS[k]: v for k, v in flag_counts.items()},
        "proposals": dict(Counter(p.status for p in proposals)),
        "proposal_types": dict(Counter(p.proposal_type for p in proposals)),
        "decisions": dict(Counter(d.action for d in decisions)),
        "tier_changes": [
            {"proposal_id": d.proposal_id, "from": d.tier_before, "to": d.tier_after, "reviewer": d.reviewer,
             "created_at": d.created_at.isoformat()}
            for d in decisions if d.action == "approve"
        ],
        "missing_data": {
            "employee_estimate_missing": sum(1 for p in prospects if p.zi_employees is None),
            "provisional_baseline": sum(1 for a in latest.values() if a and (a.baseline or {}).get("provisional")),
            "coverage_by_field": {f: dict(c) for f, c in coverage_counts.items()},
        },
        "research_cost": {
            "total_usd": round(sum(r.approx_cost_usd for r in runs), 4),
            "per_researched_prospect_usd": round(sum(r.approx_cost_usd for r in runs) / researched, 4) if researched else None,
            "web_searches": sum(r.web_search_requests for r in runs),
            "llm_calls": sum(r.llm_calls for r in runs),
            "input_tokens": sum(r.input_tokens for r in runs),
            "output_tokens": sum(r.output_tokens for r in runs),
            "by_kind": {k: round(sum(r.approx_cost_usd for r in runs if r.kind == k), 4) for k in ("standard", "deep")},
        },
        "citation_validation": {
            "findings_dropped": sum(len(r.dropped_findings or []) for r in ok_runs),
            "runs_with_drops": sum(1 for r in ok_runs if r.dropped_findings),
            "examples": [d for r in ok_runs for d in (r.dropped_findings or [])][:10],
        },
        "unsupported_recommendations": unsupported,
        "review_outcomes": {
            "rejected_proposals_candidate_false_positives": [
                {"proposal_id": p.id, "prospect_id": p.prospect_id, "title": p.title}
                for p in proposals if p.status == "rejected"
            ],
            "note": "A rejection is reviewer judgment, not ground truth. It is a candidate false positive to analyse.",
        },
        "retrospective_day30": retro,
        "scenario_checks": scenarios.run_checks(),
    }
