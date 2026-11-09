"""AI judge: a one-sentence plain-English summary of WHY a tier proposal exists, plus a
categorical view of how well its cited evidence supports it.

The judge reads only the proposal's own structured data (no web search, no other company data).
It cannot change anything: the summary is advisory and the human still decides.
A deterministic check flags any number in the summary that does not appear in the input facts.
"""
from __future__ import annotations

import hashlib
import json
import re
from typing import Literal, Optional

from pydantic import BaseModel, Field, ValidationError
from sqlmodel import Session

from .. import audit, config
from ..models import Assessment, Evidence, Prospect, TierProposal, utcnow
from . import service as research_service
from .client import ResearchProviderError, estimate_cost
from .evidence import ParseError, extract_json, host_of

PROMPT_VERSION = "judge-v2"  # v2: must state the rule the evidence triggers (v1 listed facts without the "so")

SYSTEM = """You review proposed account-tier changes for a B2B sales team at a business-travel company.
You are given the facts behind one proposal. Use ONLY these facts. Do not add knowledge.
Respond with a single JSON object and nothing else."""

USER = """Tier rules: Tier 1 = annual GBV $500K+. Tier 2 = GBV $100K-$500K OR 150+ employees. Tier 3 = everything else.

Facts about this proposal:
{facts}

Return JSON:
{{
  "summary": "ONE plain-English sentence, max 35 words, explaining why the tier change is proposed. Structure: what the current tier rests on, what the evidence shows instead, and so which tier the rules or evidence point to. Example shape: 'Downgrade: Tier 2 rests only on X; sources show Y, which is below Z, so the rules give Tier 3.' A salesperson must understand it in five seconds.",
  "support": "strong | partial | weak  (how well the cited evidence supports the change)",
  "main_doubt": "the single biggest reason it could be wrong, max 15 words"
}}

Rules:
- Only use numbers that appear in the facts.
- Say "downgrade" when the proposed tier number is higher (less support), "upgrade" when lower.
- If evidence comes only from data aggregators, a synthetic test, or a single source, support cannot be "strong".
- No confidence percentages."""


class JudgeOutput(BaseModel):
    summary: str = Field(min_length=10, max_length=400)
    support: Literal["strong", "partial", "weak"]
    main_doubt: str = Field(min_length=3, max_length=200)


def build_facts(session: Session, p: TierProposal) -> dict:
    prospect = session.get(Prospect, p.prospect_id)
    a = session.get(Assessment, (p.linked_assessment_ids or [p.assessment_id])[-1])
    av = (a.accepted_values or {}) if a else {}
    evidence = []
    for eid in p.evidence_ids or []:
        e = session.get(Evidence, eid)
        if e:
            evidence.append({
                "claim": e.claim, "source": e.publisher or host_of(e.source_url) or e.origin,
                "reliability": e.reliability, "date": e.published_date,
            })
    facts = {
        "company": prospect.company_name if prospect else p.prospect_id,
        "current_applied_tier": p.from_tier,
        "proposed_tier": p.proposed_tier,
        "proposal_type": p.proposal_type,
        "reported_annual_gbv_usd": prospect.entered_gbv_usd if prospect else None,
        "employee_count_currently_used": av.get("employees"),
        "employee_count_source": av.get("employee_source"),
        "employee_figures_from_all_sources": [
            {"value": s["value"], "source": s["label"], "reliability": s["reliability"]}
            for s in av.get("employee_sources", [])
        ],
        "reasons": p.rationale or [],
        "cited_evidence": evidence,
        "open_uncertainties": p.uncertainties or [],
    }
    if p.stage == "day30" and a and a.day30:
        facts["day30_activity"] = {k: a.day30.get(k) for k in ("travelers", "bookings", "trend_pct")}
        facts["note"] = "Booking counts are not dollar GBV."
    return facts


def facts_hash(facts: dict) -> str:
    return hashlib.sha256(json.dumps(facts, sort_keys=True, default=str).encode()).hexdigest()[:16]


_NUM = re.compile(r"\d[\d,]*(?:\.\d+)?")


def ungrounded_numbers(summary: str, facts: dict) -> list[str]:
    """Numbers in the summary that do not appear in the facts (tier numbers 1-3 always allowed)."""
    blob = json.dumps(facts, default=str).replace(",", "")
    allowed_raw = set(_NUM.findall(blob))
    allowed = set()
    for n in allowed_raw:
        allowed.add(n)
        try:
            v = float(n)
            allowed.add(str(int(v)) if v == int(v) else n)
            if v >= 1000:  # "$48K" / "48,000" style
                allowed.add(str(int(v // 1000)))
        except ValueError:
            pass
    bad = []
    for n in _NUM.findall(summary):
        k = n.replace(",", "")
        if k in {"1", "2", "3"} or k in allowed:
            continue
        bad.append(n)
    return bad


def get_or_create_judgement(session: Session, proposal_id: int, force: bool = False, actor: str = "system") -> dict:
    p = session.get(TierProposal, proposal_id)
    if p is None:
        raise ValueError("Proposal not found")
    facts = build_facts(session, p)
    h = facts_hash(facts)
    cached = p.judge or {}
    if (not force and cached.get("input_hash") == h and cached.get("status") == "ok"
            and cached.get("prompt_version") == PROMPT_VERSION):
        return {**cached, "from_cache": True}

    result: dict = {"input_hash": h, "prompt_version": PROMPT_VERSION, "model": config.RESEARCH_MODEL,
                    "created_at": utcnow().isoformat()}
    try:
        client = research_service._client_factory()
        res = client.complete(SYSTEM, USER.format(facts=json.dumps(facts, indent=1, default=str)), None)
        result["approx_cost_usd"] = estimate_cost(res.input_tokens, res.output_tokens, 0)
        out = JudgeOutput.model_validate(extract_json(res.text))
        bad = ungrounded_numbers(out.summary, facts)
        result.update(status="ok", summary=out.summary.strip(), support=out.support,
                      main_doubt=out.main_doubt.strip(), grounded=not bad, ungrounded_numbers=bad)
    except ResearchProviderError as e:
        result.update(status="failed", error=str(e))
    except (ParseError, ValidationError) as e:
        result.update(status="failed", error=f"AI judge returned an unusable answer: {str(e)[:200]}")
    except Exception as e:  # never break the review page
        result.update(status="failed", error=f"AI judge error: {type(e).__name__}")

    p.judge = result
    session.add(p)
    audit.record(session, entity_type="proposal", entity_id=p.id, prospect_id=p.prospect_id, actor=actor,
                 action="ai_judge_summary", details={k: result.get(k) for k in ("status", "support", "grounded", "error")})
    session.commit()
    return {**result, "from_cache": False}
