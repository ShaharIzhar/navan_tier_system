"""Structured contract for LLM research output. Validated with Pydantic.

The LLM's job ends here: it returns findings with sources. Flags, tiers and attention
are computed elsewhere by deterministic code.
"""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

RESEARCH_FIELDS: dict[str, str] = {
    "industry_business_model": "Industry and business model",
    "geographic_footprint": "Locations and geographic footprint",
    "employee_count": "Employee count",
    "hiring_trends": "Hiring and workforce trends",
    "travel_indicators": "Direct travel-requirement indicators",
    "funding_financial": "Funding and financial developments",
    "recent_expansion": "Recent expansion",
    "support_complexity": "Support-complexity indicators",
}
FieldName = Literal[
    "industry_business_model",
    "geographic_footprint",
    "employee_count",
    "hiring_trends",
    "travel_indicators",
    "funding_financial",
    "recent_expansion",
    "support_complexity",
]
LLMFieldStatus = Literal["found", "not_found", "conflicting", "not_applicable"]


class Finding(BaseModel):
    model_config = ConfigDict(extra="ignore")

    claim: str = Field(min_length=3)
    value_number: Optional[float] = None
    signal_type: Literal["direct_travel", "indirect_growth", "descriptive"] = "descriptive"
    observation: Literal["observed", "inferred"] = "observed"
    source_url: str
    source_title: Optional[str] = None
    publisher: Optional[str] = None
    published_date: Optional[str] = None

    @field_validator("published_date", mode="before")
    @classmethod
    def _blank_date(cls, v):
        if v in ("", "unknown", "Unknown", "n/a", "N/A"):
            return None
        return v


class FieldResult(BaseModel):
    model_config = ConfigDict(extra="ignore")

    field: FieldName
    status: LLMFieldStatus
    summary: str = ""
    findings: list[Finding] = Field(default_factory=list)


class Conflict(BaseModel):
    model_config = ConfigDict(extra="ignore")

    field: FieldName
    description: str
    source_urls: list[str] = Field(default_factory=list)


class ResearchOutput(BaseModel):
    model_config = ConfigDict(extra="ignore")

    company_identity_confirmed: bool
    identity_note: str = ""
    fields: list[FieldResult]
    conflicts: list[Conflict] = Field(default_factory=list)
    summary: str
    research_limitations: list[str] = Field(default_factory=list)
