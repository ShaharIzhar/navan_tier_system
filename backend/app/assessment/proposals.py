"""Create / update / supersede tier proposals without duplicates.

Rules:
- At most one unresolved (open or needs_info) proposal per company per proposed tier.
- A reassessment with the same conclusion links to the existing proposal.
- A proposal rejected by a human is not re-raised unless new evidence appears.
- An unresolved proposal that the latest evidence no longer supports is marked superseded.
"""
from __future__ import annotations

from sqlmodel import Session, select

from .. import audit
from ..models import TierProposal, utcnow

UNRESOLVED = ("open", "needs_info")


def sync_proposals(
    session: Session, prospect_id: str, assessment_id: int, stage: str, candidates: list[dict]
) -> tuple[list[int], list[dict]]:
    """Returns (ids of proposals supported by this assessment, suppressed candidates)."""
    existing = list(session.exec(select(TierProposal).where(TierProposal.prospect_id == prospect_id)))
    supported: list[int] = []
    suppressed: list[dict] = []

    # Merge candidates with the same target tier.
    merged: dict[int, dict] = {}
    for c in candidates:
        t = c["proposed_tier"]
        if t in merged:
            m = merged[t]
            m["rationale"] = m["rationale"] + [r for r in c["rationale"] if r not in m["rationale"]]
            m["evidence_ids"] = sorted(set(m["evidence_ids"]) | set(c["evidence_ids"]))
            m["uncertainties"] = sorted(set(m["uncertainties"]) | set(c["uncertainties"]))
            if c["proposal_type"] == "standard_rule_correction":
                m["proposal_type"], m["title"], m["basis"] = c["proposal_type"], c["title"], c.get("basis") or {}
        else:
            merged[t] = {**c, "evidence_ids": sorted(set(c["evidence_ids"])), "basis": c.get("basis") or {}}

    for target, c in merged.items():
        open_match = next(
            (p for p in existing if p.proposed_tier == target and p.status in UNRESOLVED), None
        )
        if open_match:
            changed = (
                set(open_match.evidence_ids or []) != set(c["evidence_ids"])
                or (open_match.uncertainties or []) != c["uncertainties"]
                or (open_match.rationale or []) != c["rationale"]
            )
            open_match.linked_assessment_ids = (open_match.linked_assessment_ids or []) + [assessment_id]
            if changed:
                open_match.evidence_ids = c["evidence_ids"]
                open_match.rationale = c["rationale"]
                open_match.uncertainties = c["uncertainties"]
                open_match.basis = c["basis"]
                open_match.updated_at = utcnow()
                audit.record(session, entity_type="proposal", entity_id=open_match.id, prospect_id=prospect_id,
                             action="proposal_updated", details={"assessment_id": assessment_id})
            session.add(open_match)
            supported.append(open_match.id)
            continue

        rejected = [p for p in existing if p.proposed_tier == target and p.status == "rejected"]
        if any(set(c["evidence_ids"]) <= set(p.evidence_ids or []) and p.proposal_type == c["proposal_type"]
               for p in rejected):
            suppressed.append({**c, "reason": "A reviewer already rejected this proposal and no new evidence has appeared."})
            continue

        p = TierProposal(
            prospect_id=prospect_id,
            assessment_id=assessment_id,
            stage=stage,
            proposal_type=c["proposal_type"],
            from_tier=c["from_tier"],
            proposed_tier=target,
            title=c["title"],
            basis=c["basis"],
            rationale=c["rationale"],
            evidence_ids=c["evidence_ids"],
            uncertainties=c["uncertainties"],
            linked_assessment_ids=[assessment_id],
        )
        session.add(p)
        session.flush()
        audit.record(session, entity_type="proposal", entity_id=p.id, prospect_id=prospect_id,
                     action="proposal_created",
                     details={"type": p.proposal_type, "from": p.from_tier, "to": p.proposed_tier,
                              "assessment_id": assessment_id})
        supported.append(p.id)

    for p in existing:
        if p.status in UNRESOLVED and p.id not in supported:
            p.status = "superseded"
            p.updated_at = utcnow()
            session.add(p)
            audit.record(session, entity_type="proposal", entity_id=p.id, prospect_id=prospect_id,
                         action="proposal_superseded",
                         details={"reason": "Latest assessment no longer supports this proposal.",
                                  "assessment_id": assessment_id})
    return supported, suppressed
