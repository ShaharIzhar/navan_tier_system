"""Manual enrichment and synthetic test evidence.

Manual values are stored as new evidence rows (origin=human); original research evidence
is never edited or deleted. Saving triggers a deterministic reassessment: no LLM call.
"""
from __future__ import annotations

from typing import Optional

from sqlmodel import Session

from . import audit
from .assessment.engine import reassess
from .models import Assessment, Evidence, Prospect, utcnow
from .research.evidence import host_of

# Structured parameters a Growth employee can set, and how each maps to signals.
ENRICHMENT_FIELDS = {
    "employee_count": {"label": "Employee count", "kind": "number", "field": "employee_count",
                       "signal_type": "descriptive"},
    "travel_requirement": {"label": "Direct travel requirement observed", "kind": "text",
                           "field": "travel_indicators", "signal_type": "direct_travel"},
    "funding": {"label": "Funding or financial development", "kind": "text", "field": "funding_financial",
                "signal_type": "indirect_growth"},
    "expansion": {"label": "Expansion (new office / market)", "kind": "text", "field": "recent_expansion",
                  "signal_type": "indirect_growth"},
    "geographic_footprint": {"label": "Geographic footprint", "kind": "text", "field": "geographic_footprint",
                             "signal_type": "indirect_growth"},
    "note": {"label": "Free-text note (explanatory only)", "kind": "text", "field": "note",
             "signal_type": "descriptive"},
}


class EnrichmentError(ValueError):
    pass


def add_enrichment(
    session: Session, prospect_id: str, param: str, value: str, entered_by: str,
    source_url: Optional[str] = None, note: Optional[str] = None, verified: bool = False,
    accepted: bool = True,
) -> tuple[Evidence, Assessment, Optional[Assessment]]:
    if param not in ENRICHMENT_FIELDS:
        raise EnrichmentError(f"Unsupported field '{param}'.")
    entered_by = (entered_by or "").strip()
    if not entered_by:
        raise EnrichmentError("Your name is required for the audit trail.")
    prospect = session.get(Prospect, prospect_id)
    if prospect is None:
        raise EnrichmentError("Unknown prospect.")
    spec = ENRICHMENT_FIELDS[param]
    value = (value or "").strip()
    if not value:
        raise EnrichmentError("A value is required.")
    number = None
    if spec["kind"] == "number":
        try:
            number = float(value.replace(",", ""))
        except ValueError as e:
            raise EnrichmentError("Employee count must be a number.") from e
        if number < 0 or number != int(number):
            raise EnrichmentError("Employee count must be a non-negative whole number.")
    source_url = (source_url or "").strip() or None
    # Verified requires a source the reviewer checked; otherwise it is unverified.
    is_verified = bool(verified and source_url)
    free_text = param == "note"

    from .assessment.engine import latest_assessment
    before = latest_assessment(session, prospect_id)

    claim = f"{spec['label']}: {int(number):,}" if number is not None else value
    e = Evidence(
        prospect_id=prospect_id, field=spec["field"], claim=claim, value_number=number,
        signal_type=spec["signal_type"], observation="observed",
        source_url=source_url, source_title=None, publisher=host_of(source_url) or None,
        reliability="manual_verified" if is_verified else "manual_unverified",
        origin="human", accepted_for_reassessment=bool(accepted and not free_text),
        entered_by=entered_by, note=note,
    )
    session.add(e)
    session.flush()
    audit.record(session, entity_type="evidence", entity_id=e.id, prospect_id=prospect_id, actor=entered_by,
                 action="manual_enrichment",
                 details={"param": param, "value": value, "verified": is_verified, "accepted": e.accepted_for_reassessment,
                          "source_url": source_url,
                          "previous_accepted_employees": (before.accepted_values or {}).get("employees") if before else None})
    session.commit()
    after = reassess(session, prospect_id, trigger="manual_enrichment", actor=entered_by)
    session.refresh(e)
    return e, after, before


def add_synthetic_evidence(session: Session, prospect_id: str, field: str, claim: str,
                           value_number: Optional[float], signal_type: str, entered_by: str) -> Evidence:
    """Clearly labelled synthetic observation for controlled tests. Never public research."""
    e = Evidence(
        prospect_id=prospect_id, field=field, claim=f"[SYNTHETIC TEST] {claim}", value_number=value_number,
        signal_type=signal_type, observation="observed", source_title="Synthetic test observation",
        source_url=None, publisher="Synthetic (not a real source)", reliability="synthetic",
        origin="synthetic_test", entered_by=entered_by, published_date=utcnow().strftime("%Y-%m-%d"),
        note="Introduced deliberately to test conflict handling. Not a claim about the real company.",
    )
    session.add(e)
    session.flush()
    audit.record(session, entity_type="evidence", entity_id=e.id, prospect_id=prospect_id, actor=entered_by,
                 action="synthetic_evidence_added", details={"field": field, "claim": claim, "value": value_number})
    session.commit()
    reassess(session, prospect_id, trigger="manual", actor=entered_by)
    session.refresh(e)
    return e


def retract_evidence(session: Session, evidence_id: int, actor: str, reason: str) -> Evidence:
    """Mark a manual or synthetic entry as withdrawn (kept for history)."""
    e = session.get(Evidence, evidence_id)
    if e is None or e.origin not in ("human", "synthetic_test"):
        raise EnrichmentError("Only manual or synthetic entries can be withdrawn.")
    e.superseded_by = f"withdrawn:{utcnow().isoformat()}"
    session.add(e)
    audit.record(session, entity_type="evidence", entity_id=e.id, prospect_id=e.prospect_id, actor=actor,
                 action="evidence_withdrawn", details={"reason": reason})
    session.commit()
    reassess(session, e.prospect_id, trigger="manual_enrichment", actor=actor)
    return e
