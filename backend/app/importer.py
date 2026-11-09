"""CSV import and normalisation.

Day 0 fields go to `Prospect`. The post-signup activity column is stored separately in
`PostSignupActivity` with `released_at=None`, so it cannot leak into Day 0 logic.
"""
from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from sqlmodel import Session

from . import audit
from .models import PostSignupActivity, Prospect


def normalize_header(h: str) -> str:
    return re.sub(r"\s+", "_", h.strip().lower())


def parse_gbv(raw: Optional[str]) -> tuple[Optional[float], Optional[str]]:
    """Return (value, issue). Never coerces invalid input to 0."""
    if raw is None or not raw.strip():
        return None, "Annual GBV is missing."
    cleaned = raw.strip().replace("$", "").replace(",", "").replace("USD", "").strip()
    cleaned = cleaned.replace("−", "-")
    try:
        value = float(cleaned)
    except ValueError:
        return None, f"Annual GBV '{raw}' could not be parsed."
    if value < 0:
        return value, f"Annual GBV '{raw}' is negative."
    return value, None


def parse_employees(raw: Optional[str]) -> tuple[Optional[int], Optional[str]]:
    if raw is None or not raw.strip():
        return None, None  # missing is normal (20 rows), not a data-quality error
    try:
        value = int(float(raw.strip().replace(",", "")))
    except ValueError:
        return None, f"Employee estimate '{raw}' could not be parsed."
    if value < 0:
        return None, f"Employee estimate '{raw}' is negative and was ignored."
    return value, None


def parse_tier(raw: Optional[str]) -> Optional[int]:
    if not raw:
        return None
    m = re.search(r"([123])", raw)
    return int(m.group(1)) if m else None


@dataclass
class ParsedActivity:
    travelers: Optional[int]
    bookings: Optional[int]
    trend_pct: Optional[float]
    parse_ok: bool


_TRAVELERS = re.compile(r"(\d+)\s+travel(?:l)?ers?", re.I)
_BOOKINGS = re.compile(r"(\d+)\s+bookings?", re.I)
_TREND = re.compile(r"bookings\s+([+\-−])\s*(\d+(?:\.\d+)?)\s*%", re.I)
_FLAT = re.compile(r"\bflat\b", re.I)


def parse_activity(text: str) -> ParsedActivity:
    t = _TRAVELERS.search(text)
    b = _BOOKINGS.search(text)
    trend: Optional[float] = None
    m = _TREND.search(text)
    if m:
        sign = -1 if m.group(1) in ("-", "−") else 1
        trend = sign * float(m.group(2))
    elif _FLAT.search(text):
        trend = 0.0
    travelers = int(t.group(1)) if t else None
    bookings = int(b.group(1)) if b else None
    return ParsedActivity(travelers, bookings, trend, parse_ok=None not in (travelers, bookings, trend))


def read_csv(path: Path) -> list[dict]:
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        headers = [normalize_header(h) for h in next(reader)]
        return [dict(zip(headers, row)) for row in reader if any(c.strip() for c in row)]


def import_prospects(session: Session, path: Path) -> dict:
    rows = read_csv(path)
    created, skipped = 0, 0
    for row in rows:
        pid = row.get("scenario_id", "").strip()
        if not pid:
            continue
        if session.get(Prospect, pid):
            skipped += 1  # idempotent: never overwrite an existing prospect's history
            continue
        notes: list[str] = []
        gbv, gbv_issue = parse_gbv(row.get("entered_gbv_usd"))
        if gbv_issue:
            notes.append(gbv_issue)
        emp, emp_issue = parse_employees(row.get("zi_company_size_est"))
        if emp_issue:
            notes.append(emp_issue)
        tier = parse_tier(row.get("current_tier"))
        if tier is None:
            notes.append("Current tier missing or unrecognised.")
        prospect = Prospect(
            id=pid,
            company_name=row.get("company_name", "").strip(),
            domain=row.get("company_domain", "").strip().lower(),
            entered_gbv_raw=row.get("entered_gbv_usd"),
            entered_gbv_usd=gbv,  # negative kept so rules flag it as invalid
            zi_employees=emp,
            original_tier=tier,
            applied_tier=tier,
            data_quality_notes=notes,
        )
        session.add(prospect)
        activity_text = (row.get("navan_travel_activity_30d_post_signup") or "").strip()
        if activity_text:
            parsed = parse_activity(activity_text)
            session.add(
                PostSignupActivity(
                    prospect_id=pid,
                    raw_text=activity_text,
                    travelers=parsed.travelers,
                    bookings=parsed.bookings,
                    trend_pct=parsed.trend_pct,
                    parse_ok=parsed.parse_ok,
                    remarks=activity_text,  # the file's own Day 30 note, shown under Remarks
                )
            )
        audit.record(session, entity_type="prospect", entity_id=pid, prospect_id=pid,
                     action="imported", details={"source": str(path.name)})
        created += 1
    session.commit()
    return {"created": created, "skipped_existing": skipped, "rows": len(rows)}
