"""PR-style review workflow for tier proposals.

approve      -> applies the proposed tier inside the prototype, keeps original/previous tier
reject       -> tier unchanged, reason required
request_info -> proposal stays unresolved (needs_info); more evidence can be added
comment      -> discussion only
"""
from __future__ import annotations

from typing import Optional

from sqlmodel import Session

from .. import audit
from ..assessment.engine import reassess
from ..models import Evidence, Prospect, ReviewDecision, TierProposal, utcnow


class ReviewError(ValueError):
    pass


ACTIONS = ("approve", "reject", "request_info", "comment")


def decide(session: Session, proposal_id: int, action: str, reviewer: str, comment: Optional[str]) -> TierProposal:
    if action not in ACTIONS:
        raise ReviewError(f"Unknown action '{action}'.")
    reviewer = (reviewer or "").strip()
    if not reviewer:
        raise ReviewError("Reviewer name is required.")
    comment = (comment or "").strip() or None
    proposal = session.get(TierProposal, proposal_id)
    if proposal is None:
        raise ReviewError("Proposal not found.")
    if action in ("reject", "request_info", "comment") and not comment:
        raise ReviewError("A comment is required for this action.")
    if action != "comment" and proposal.status not in ("open", "needs_info"):
        raise ReviewError(f"Proposal is already {proposal.status}; it cannot be {action}d.")

    prospect = session.get(Prospect, proposal.prospect_id)
    before = prospect.applied_tier
    after = before

    if action == "approve":
        if proposal.from_tier is not None and before != proposal.from_tier:
            raise ReviewError(
                f"Applied tier changed since this proposal was made (now Tier {before}); reassess first."
            )
        prospect.applied_tier = proposal.proposed_tier
        prospect.applied_tier_source = f"proposal:{proposal.id}"
        after = proposal.proposed_tier
        proposal.status = "approved"
        # A standard-rule correction based on research headcount: approving it means the
        # reviewer accepts that headcount, so record it as reviewer-accepted evidence.
        basis = proposal.basis or {}
        if proposal.proposal_type == "standard_rule_correction" and basis.get("employee_source") == "research":
            session.add(Evidence(
                prospect_id=prospect.id, field="employee_count",
                claim=f"Employee count {basis['employees']:,} accepted by {reviewer} when approving proposal #{proposal.id}.",
                value_number=basis["employees"], origin="human", reliability="manual_verified",
                accepted_for_reassessment=True, entered_by=reviewer,
                note=f"Accepted from research evidence ids {proposal.evidence_ids}.",
            ))
        session.add(prospect)
        audit.record(session, entity_type="prospect", entity_id=prospect.id, prospect_id=prospect.id, actor=reviewer,
                     action="tier_changed",
                     details={"from": before, "to": after, "original_tier": prospect.original_tier,
                              "proposal_id": proposal.id, "proposal_type": proposal.proposal_type,
                              "policy_override": proposal.proposal_type == "evidence_override",
                              "comment": comment})
    elif action == "reject":
        proposal.status = "rejected"
    elif action == "request_info":
        proposal.status = "needs_info"

    proposal.updated_at = utcnow()
    session.add(proposal)
    session.add(ReviewDecision(proposal_id=proposal.id, action=action, reviewer=reviewer, comment=comment,
                               tier_before=before, tier_after=after))
    audit.record(session, entity_type="proposal", entity_id=proposal.id, prospect_id=proposal.prospect_id,
                 actor=reviewer, action=f"review_{action}", details={"comment": comment, "tier_before": before,
                                                                     "tier_after": after})
    session.commit()
    if action in ("approve", "reject"):
        reassess(session, proposal.prospect_id, trigger="review", actor=reviewer)
    session.refresh(proposal)
    return proposal
