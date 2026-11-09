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


def update_day30(session: Session, prospect_id: str, travelers: int, bookings: int, trend_pct: float | None,
                 actor: str, remarks: str | None = None) -> Assessment:
    """Correct the 30-day activity numbers (e.g. from an updated export). Marks them received and reruns the rules."""
    act = session.exec(select(PostSignupActivity).where(PostSignupActivity.prospect_id == prospect_id)).first()
    if act is None:
        act = PostSignupActivity(prospect_id=prospect_id, raw_text="(entered manually)")
    if travelers < 0 or bookings < 0:
        raise ValueError("Travelers and bookings can’t be negative.")
    before = {"travelers": act.travelers, "bookings": act.bookings, "trend_pct": act.trend_pct,
              "remarks": act.remarks, "received": act.released_at is not None}
    act.travelers, act.bookings, act.trend_pct, act.parse_ok = travelers, bookings, trend_pct, True
    act.remarks = (remarks or "").strip() or None
    act.released_at = act.released_at or utcnow()
    session.add(act)
    audit.record(session, entity_type="activity", entity_id=act.id, prospect_id=prospect_id, actor=actor,
                 action="day30_activity_updated",
                 details={"before": before, "after": {"travelers": travelers, "bookings": bookings,
                                                     "trend_pct": trend_pct, "remarks": act.remarks}})
    session.commit()
    return reassess(session, prospect_id, trigger="day30", actor=actor)


def remove_day30(session: Session, prospect_id: str, actor: str) -> Assessment:
    """Take the 30-day activity out again: back to the original file values, not received. Rules rerun."""
    from .importer import parse_activity

    act = session.exec(select(PostSignupActivity).where(PostSignupActivity.prospect_id == prospect_id)).first()
    if act is None or act.released_at is None:
        raise ValueError("There is no Day 30 data to remove.")
    before = {"travelers": act.travelers, "bookings": act.bookings, "trend_pct": act.trend_pct}
    if act.raw_text and act.raw_text != "(entered manually)":
        parsed = parse_activity(act.raw_text)
        act.travelers, act.bookings, act.trend_pct = parsed.travelers, parsed.bookings, parsed.trend_pct
        act.remarks = None
        act.released_at = None
        session.add(act)
    else:
        session.delete(act)
    audit.record(session, entity_type="activity", entity_id=act.id, prospect_id=prospect_id, actor=actor,
                 action="day30_activity_removed", details={"before": before})
    session.commit()
    return reassess(session, prospect_id, trigger="day30", actor=actor)
