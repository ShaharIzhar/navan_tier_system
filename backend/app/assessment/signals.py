"""Turn stored evidence into structured, reusable signals.

This is what makes reassessment possible without another LLM call: the decision logic
reads these structured values, not free text.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from statistics import median
from typing import Optional

from sqlmodel import Session, select

from ..models import Evidence, FieldStatus, PostSignupActivity, Prospect, ResearchRun
from ..research.evidence import host_of, parse_date
from ..research.schema import RESEARCH_FIELDS

USABLE_RELIABILITY = {"primary", "secondary", "manual_verified", "manual_unverified", "synthetic"}


@dataclass
class EmployeeSource:
    value: int
    origin: str        # dataset | human | ai_research | synthetic_test
    reliability: str
    label: str
    evidence_id: Optional[int] = None
    as_of: Optional[str] = None
    stale: bool = False
    company_site: bool = False  # from the company's own website
    url: Optional[str] = None


@dataclass
class Signals:
    prospect: Prospect
    gbv: Optional[float]
    employee_sources: list[EmployeeSource] = field(default_factory=list)
    accepted_employee: Optional[EmployeeSource] = None
    research_employee_value: Optional[int] = None
    research_employee_sources: list[EmployeeSource] = field(default_factory=list)
    direct_travel: list[Evidence] = field(default_factory=list)
    weak_travel: list[Evidence] = field(default_factory=list)  # aggregator-only or inferred
    growth: list[Evidence] = field(default_factory=list)
    coverage: dict = field(default_factory=dict)
    research_ran: bool = False
    research_failed_last: bool = False
    llm_conflicts: list[dict] = field(default_factory=list)
    activity: Optional[PostSignupActivity] = None
    headcount_history: list[dict] = field(default_factory=list)

    @property
    def accepted_employees(self) -> Optional[int]:
        return self.accepted_employee.value if self.accepted_employee else None


def active_evidence(session: Session, prospect_id: str) -> list[Evidence]:
    rows = session.exec(
        select(Evidence).where(Evidence.prospect_id == prospect_id, Evidence.superseded_by == None)  # noqa: E711
    )
    return list(rows)


def _counts(e: Evidence) -> bool:
    """Human evidence counts only when explicitly accepted for reassessment."""
    if e.origin == "human":
        return e.accepted_for_reassessment
    return True


def build_signals(session: Session, prospect: Prospect) -> Signals:
    s = Signals(prospect=prospect, gbv=prospect.entered_gbv_usd)
    evidence = [e for e in active_evidence(session, prospect.id) if _counts(e)]

    # --- employee sources ----------------------------------------------------
    if prospect.zi_employees is not None:
        s.employee_sources.append(
            EmployeeSource(prospect.zi_employees, "dataset", "enrichment", "Enrichment estimate (dataset)")
        )
    manual_verified, manual_unverified = [], []
    for e in evidence:
        if e.field != "employee_count" or e.value_number is None:
            continue
        own = e.origin == "ai_research" and _is_company_site(e.source_url, prospect.domain)
        src = EmployeeSource(
            value=int(round(e.value_number)),
            origin=e.origin,
            reliability=e.reliability,
            label=f"Company website ({host_of(e.source_url)})" if own else _source_label(e),
            evidence_id=e.id,
            as_of=e.published_date,
            stale=e.is_stale,
            company_site=own,
            url=e.source_url,
        )
        s.employee_sources.append(src)
        if e.origin == "human":
            (manual_verified if e.reliability == "manual_verified" else manual_unverified).append((e, src))
        elif e.origin in ("ai_research", "synthetic_test"):
            s.research_employee_sources.append(src)

    # Accepted value precedence: verified manual > accepted unverified manual > dataset.
    # Research values never silently replace the dataset value.
    def latest(pairs):
        return max(pairs, key=lambda p: p[0].id)[1]

    if manual_verified:
        s.accepted_employee = latest(manual_verified)
    elif manual_unverified:
        s.accepted_employee = latest(manual_unverified)
    elif prospect.zi_employees is not None:
        s.accepted_employee = s.employee_sources[0]

    # Most trustworthy first: company website, then registries, independent sources, aggregators.
    s.research_employee_sources.sort(key=_trust_rank)
    s.employee_sources.sort(key=lambda x: (0 if x.company_site else 1, 0 if x.origin in ("dataset", "human") else 1, _trust_rank(x)))

    fresh = [x.value for x in s.research_employee_sources if not x.stale] or [
        x.value for x in s.research_employee_sources
    ]
    if fresh:
        s.research_employee_value = int(median(fresh))

    # A trend needs two dated figures from the SAME source. Comparing different databases
    # (e.g. PitchBook 90 vs Pomanda 422) would show fake growth.
    by_source: dict[str, dict[str, dict]] = {}
    for x in s.research_employee_sources:
        if x.origin == "ai_research" and parse_date(x.as_of):
            by_source.setdefault(x.label, {})[x.as_of] = {"date": x.as_of, "value": x.value, "label": x.label}
    best: list[dict] = []
    for points in by_source.values():
        if len(points) >= 2 and len(points) > len(best):
            best = sorted(points.values(), key=lambda d: parse_date(d["date"]))
    s.headcount_history = best

    # --- travel and growth signals --------------------------------------------
    for e in evidence:
        if e.signal_type == "direct_travel":
            if e.observation == "observed" and e.reliability in USABLE_RELIABILITY and not e.is_stale:
                s.direct_travel.append(e)
            else:
                s.weak_travel.append(e)
        elif e.signal_type == "indirect_growth" and e.observation == "observed" and not e.is_stale:
            s.growth.append(e)

    # --- research coverage (latest run that covered each field wins) -------------
    runs = list(session.exec(select(ResearchRun).where(ResearchRun.prospect_id == prospect.id).order_by(ResearchRun.id)))
    s.research_ran = any(r.status in ("ok", "partial") for r in runs)
    s.research_failed_last = bool(runs) and runs[-1].status == "failed"
    statuses = list(
        session.exec(select(FieldStatus).where(FieldStatus.prospect_id == prospect.id).order_by(FieldStatus.id))
    )
    coverage = {f: {"status": "not_searched", "summary": None, "run_id": None} for f in RESEARCH_FIELDS}
    for fs in statuses:
        coverage[fs.field] = {"status": fs.status, "summary": fs.summary, "run_id": fs.run_id}
    for f in coverage:
        coverage[f]["evidence_count"] = sum(1 for e in evidence if e.field == f and e.origin != "human")
        coverage[f]["manual"] = any(e.field == f and e.origin == "human" for e in evidence)
        coverage[f]["synthetic"] = any(e.field == f and e.origin == "synthetic_test" for e in evidence)
    s.coverage = coverage

    # Conflicts the research itself reported: only from the latest run of each kind, one per field
    # (newest wins), so repeated runs don't stack near-identical notes.
    latest_by_kind: dict[str, ResearchRun] = {}
    for r in runs:
        if r.status in ("ok", "partial") and r.parsed:
            latest_by_kind[r.kind] = r
    by_field: dict[str, dict] = {}
    for r in sorted(latest_by_kind.values(), key=lambda r: r.id):
        for c in r.parsed.get("conflicts", []) or []:
            by_field[c.get("field", "")] = {**c, "run_id": r.id}
    s.llm_conflicts = list(by_field.values())

    # --- post-signup activity (only once "received") ---------------------------
    act = session.exec(select(PostSignupActivity).where(PostSignupActivity.prospect_id == prospect.id)).first()
    if act is not None and act.released_at is not None:
        s.activity = act
    return s


_TRUST = {"primary": 0, "manual_verified": 1, "secondary": 2, "manual_unverified": 3, "aggregator": 4, "synthetic": 5}


def _trust_rank(x: "EmployeeSource") -> tuple:
    return (0 if x.company_site else 1, _TRUST.get(x.reliability, 6))


def _is_company_site(url: Optional[str], domain: str) -> bool:
    h = host_of(url)
    d = (domain or "").lower().removeprefix("www.")
    return bool(h and d and (h == d or h.endswith("." + d)))


def _source_label(e: Evidence) -> str:
    if e.origin == "human":
        who = e.entered_by or "Growth team"
        status = "verified" if e.reliability == "manual_verified" else "unverified"
        return f"Manual entry by {who} ({status})"
    if e.origin == "synthetic_test":
        return "SYNTHETIC test observation"
    return e.publisher or host_of(e.source_url) or "Public source"


def independent_hosts(items: list[Evidence]) -> set[str]:
    """Count sources by origin host; several pages on one site are one source.
    Manual entries without a URL count as one source per entry."""
    hosts = set()
    for e in items:
        h = host_of(e.source_url)
        hosts.add(h or f"manual:{e.id}")
    return hosts
