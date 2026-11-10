"""Shared helper for the maintenance scripts."""
from sqlmodel import Session, select

from app.models import ResearchRun


def latest_successful_runs(s: Session, skip_repaired: bool = False) -> dict[tuple[str, str], ResearchRun]:
    """The newest ok/partial research run per (company, kind). With skip_repaired, runs that needed a
    repair retry are left out."""
    latest: dict[tuple[str, str], ResearchRun] = {}
    for r in s.exec(select(ResearchRun).where(ResearchRun.status.in_(("ok", "partial"))).order_by(ResearchRun.id)):
        if skip_repaired and "--- repair attempt ---" in (r.raw_text or ""):
            continue
        latest[(r.prospect_id, r.kind)] = r
    return latest
