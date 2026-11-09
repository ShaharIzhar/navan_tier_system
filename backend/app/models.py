"""Persistence model.

Design rule: history is append-only. Assessments, evidence, review decisions and audit
events are never edited in place; newer rows supersede older ones so every earlier
state stays reconstructable.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def json_col() -> Any:
    return Field(default=None, sa_column=Column(JSON))


class Prospect(SQLModel, table=True):
    id: str = Field(primary_key=True)  # scenario_id, e.g. "P-007"
    company_name: str
    domain: str
    entered_gbv_raw: Optional[str] = None
    entered_gbv_usd: Optional[float] = None
    zi_employees: Optional[int] = None
    original_tier: Optional[int] = None  # tier from the CSV; never modified
    applied_tier: Optional[int] = None   # tier currently in effect inside the prototype
    applied_tier_source: str = "dataset"  # "dataset" | "proposal:<id>"
    data_quality_notes: Optional[list] = json_col()
    imported_at: datetime = Field(default_factory=utcnow)


class PostSignupActivity(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    prospect_id: str = Field(foreign_key="prospect.id", index=True)
    raw_text: str
    travelers: Optional[int] = None
    bookings: Optional[int] = None
    trend_pct: Optional[float] = None  # second half vs first half of the 30 days
    parse_ok: bool = True
    released_at: Optional[datetime] = None  # None = not yet "received" by the system


class ResearchRun(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    prospect_id: str = Field(foreign_key="prospect.id", index=True)
    kind: str  # "standard" | "deep"
    status: str = "running"  # running | ok | partial | failed
    prompt_version: str = ""
    model: str = ""
    focus_fields: Optional[list] = json_col()
    started_at: datetime = Field(default_factory=utcnow)
    finished_at: Optional[datetime] = None
    research_cutoff: datetime = Field(default_factory=utcnow)
    input_tokens: int = 0
    output_tokens: int = 0
    web_search_requests: int = 0
    llm_calls: int = 0
    approx_cost_usd: float = 0.0
    error: Optional[str] = None
    raw_text: Optional[str] = None
    parsed: Optional[dict] = json_col()
    searched_results: Optional[list] = json_col()   # what the search tool actually returned
    dropped_findings: Optional[list] = json_col()   # findings removed by validation, with reason
    normalized_findings: Optional[list] = json_col()  # findings changed by deterministic post-processing
    search_queries: Optional[list] = json_col()     # queries the model actually ran
    summary: Optional[str] = None
    limitations: Optional[list] = json_col()


class Evidence(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    prospect_id: str = Field(foreign_key="prospect.id", index=True)
    run_id: Optional[int] = Field(default=None, foreign_key="researchrun.id")
    field: str
    claim: str
    value_number: Optional[float] = None
    signal_type: str = "descriptive"  # direct_travel | indirect_growth | descriptive
    observation: str = "observed"     # observed | inferred
    travel_scope: Optional[str] = None  # business_travel | local_field_travel | unclear (direct_travel only)
    source_title: Optional[str] = None
    source_url: Optional[str] = None
    publisher: Optional[str] = None
    published_date: Optional[str] = None
    retrieved_at: datetime = Field(default_factory=utcnow)
    reliability: str = "secondary"
    # primary | secondary | aggregator | manual_verified | manual_unverified | synthetic
    origin: str = "ai_research"  # ai_research | human | synthetic_test | dataset
    is_stale: bool = False
    accepted_for_reassessment: bool = False
    entered_by: Optional[str] = None
    note: Optional[str] = None
    superseded_by: Optional[str] = None  # "run:<id>" or "evidence:<id>"; row kept for history
    created_at: datetime = Field(default_factory=utcnow)


class FieldStatus(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    run_id: int = Field(foreign_key="researchrun.id", index=True)
    prospect_id: str = Field(foreign_key="prospect.id", index=True)
    field: str
    status: str  # found | not_found | not_searched | conflicting | stale | not_applicable
    summary: Optional[str] = None


class Assessment(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    prospect_id: str = Field(foreign_key="prospect.id", index=True)
    stage: str  # day0 | day30
    trigger: str  # import | research | deep_research | manual_enrichment | day30 | review | manual
    created_at: datetime = Field(default_factory=utcnow)
    applied_tier: Optional[int] = None
    baseline: Optional[dict] = json_col()
    accepted_values: Optional[dict] = json_col()
    flags: Optional[list] = json_col()
    attention: Optional[str] = None  # review_now | review_suggested | monitor | None
    priority_score: int = 0
    priority_reasons: Optional[list] = json_col()
    primary_flag: Optional[str] = None
    recommended_action: Optional[str] = None
    coverage: Optional[dict] = json_col()
    day30: Optional[dict] = json_col()
    proposal_ids: Optional[list] = json_col()
    supersedes_id: Optional[int] = None


class TierProposal(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    prospect_id: str = Field(foreign_key="prospect.id", index=True)
    assessment_id: int = Field(foreign_key="assessment.id")
    stage: str
    proposal_type: str  # standard_rule_correction | evidence_override
    from_tier: Optional[int] = None
    proposed_tier: int
    title: str
    basis: Optional[dict] = json_col()  # structured values the proposal relies on, e.g. {"employees": 90}
    rationale: Optional[list] = json_col()
    evidence_ids: Optional[list] = json_col()
    uncertainties: Optional[list] = json_col()
    linked_assessment_ids: Optional[list] = json_col()
    judge: Optional[dict] = json_col()  # cached AI judge summary (advisory only)
    status: str = "open"  # open | needs_info | approved | rejected | superseded
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class ReviewDecision(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    proposal_id: int = Field(foreign_key="tierproposal.id", index=True)
    action: str  # approve | reject | request_info | comment
    reviewer: str
    comment: Optional[str] = None
    tier_before: Optional[int] = None
    tier_after: Optional[int] = None
    created_at: datetime = Field(default_factory=utcnow)


class AuditEvent(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    prospect_id: Optional[str] = Field(default=None, index=True)
    entity_type: str
    entity_id: Optional[str] = None
    action: str
    actor: str = "system"
    details: Optional[dict] = json_col()
    created_at: datetime = Field(default_factory=utcnow)
