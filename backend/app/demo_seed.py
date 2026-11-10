"""Demo mode only (no API key): give a fresh database a little history, so every screen has something to show.

Runs once, after the recorded research has been replayed. Everything it does goes through the normal
code paths and is labelled in the audit trail:
- Day 30 activity is received for half of the companies that have it. The rest stay pending, so
  "Receive all Day 30 activity" still has work to do.
- One proposal backed by recorded research (Retail Merchant Services, Tier 3 -> Tier 2) is approved by
  a reviewer named "Demo reviewer (seeded)", so an applied tier change is visible. IMU Biosciences'
  proposal stays open for you to review.
"""
from __future__ import annotations

from sqlmodel import Session, select

from . import audit
from .models import AuditEvent, TierProposal
from .postsignup import release_day30
from .reviews.service import decide

SEED_ACTION = "demo_seed"
SEED_ACTOR = "system:demo-seed"
DEMO_REVIEWER = "Demo reviewer (seeded)"
DAY30_RECEIVED = ["P-002", "P-009", "P-018", "P-021", "P-025"]
APPROVE = ("P-026", 3, 2)


def seed_demo(session: Session) -> bool:
    if session.exec(select(AuditEvent).where(AuditEvent.action == SEED_ACTION)).first():
        return False
    for pid in DAY30_RECEIVED:
        release_day30(session, pid, actor=SEED_ACTOR)

    pid, from_tier, to_tier = APPROVE
    proposal = session.exec(select(TierProposal).where(
        TierProposal.prospect_id == pid, TierProposal.from_tier == from_tier,
        TierProposal.proposed_tier == to_tier, TierProposal.status == "open")).first()
    if proposal:
        decide(session, proposal.id, "approve", DEMO_REVIEWER,
               "Seeded demo decision, made automatically so the demo shows an applied tier change.")

    audit.record(session, entity_type="system", action=SEED_ACTION, actor=SEED_ACTOR,
                 details={"day30_received": DAY30_RECEIVED, "approved": pid if proposal else None})
    session.commit()
    return True
