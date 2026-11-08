"""Simulates post-signup (Day 30) activity becoming available.

The CSV contains the activity up front, but the system treats it as unknown until it is
"released". Release triggers a lightweight, rules-only reassessment that compares the
activity with the previous Day 0 assessment. Day 0 rows are never modified.
"""
from __future__ import annotations

from sqlmodel import Session, select

from . import audit
from .assessment.engine import reassess
from .models import Assessment, PostSignupActivity, utcnow


def release_day30(session: Session, prospect_id: str, actor: str = "system") -> Assessment | None:
    act = session.exec(select(PostSignupActivity).where(PostSignupActivity.prospect_id == prospect_id)).first()
    if act is None:
        return None
    if act.released_at is None:
        act.released_at = utcnow()
        session.add(act)
        audit.record(session, entity_type="activity", entity_id=act.id, prospect_id=prospect_id, actor=actor,
                     action="day30_activity_received",
                     details={"travelers": act.travelers, "bookings": act.bookings, "trend_pct": act.trend_pct})
        session.commit()
    return reassess(session, prospect_id, trigger="day30", actor=actor)


def release_all(session: Session, actor: str = "system") -> list[str]:
    ids = [a.prospect_id for a in session.exec(select(PostSignupActivity).where(PostSignupActivity.released_at == None))]  # noqa: E711
    for pid in ids:
        release_day30(session, pid, actor)
    return ids
