"""Standard and Deep research orchestration.

Flow: build prompt (Day 0 inputs only) -> LLM + web search -> parse/validate JSON
(one repair retry) -> drop citations not returned by search -> store evidence and
field statuses -> deterministic reassessment.
"""
from __future__ import annotations

from typing import Callable, Optional

from sqlmodel import Session, select

from .. import audit, config
from ..assessment.engine import reassess
from ..models import Evidence, FieldStatus, Prospect, ResearchRun, utcnow
from . import prompts
from .client import AnthropicResearchClient, LLMClient, LLMResult, ResearchProviderError, estimate_cost
from .evidence import ParseError, classify_reliability, is_future, is_stale, parse_research_output, validate_citations
from .schema import RESEARCH_FIELDS, ResearchOutput

ClientFactory = Callable[[], LLMClient]
_client_factory: ClientFactory = lambda: AnthropicResearchClient()  # noqa: E731


def set_client_factory(factory: ClientFactory) -> None:
    """Used by tests to inject a fake LLM client."""
    global _client_factory
    _client_factory = factory


def provider_status() -> dict:
    return {
        "configured": bool(config.ANTHROPIC_API_KEY),
        "model": config.RESEARCH_MODEL,
        "web_search_tool": config.WEB_SEARCH_TOOL_TYPE,
        "standard_max_searches": config.STANDARD_MAX_SEARCHES,
        "deep_max_searches": config.DEEP_MAX_SEARCHES,
        "prompt_version": prompts.CURRENT_VERSION,
    }


def find_cached_run(session: Session, prospect_id: str, kind: str, version: str) -> Optional[ResearchRun]:
    return session.exec(
        select(ResearchRun)
        .where(ResearchRun.prospect_id == prospect_id, ResearchRun.kind == kind,
               ResearchRun.prompt_version == version, ResearchRun.status.in_(("ok", "partial")))
        .order_by(ResearchRun.id.desc())
    ).first()


def run_standard_research(
    session: Session, prospect_id: str, force: bool = False, actor: str = "system",
    prompt_version: Optional[str] = None,
) -> ResearchRun:
    prospect = session.get(Prospect, prospect_id)
    if prospect is None:
        raise ValueError(f"Unknown prospect {prospect_id}")
    version, system, user = prompts.build_standard_prompt(prospect.company_name, prospect.domain, prompt_version)
    if not force:
        cached = find_cached_run(session, prospect_id, "standard", version)
        if cached:
            audit.record(session, entity_type="research_run", entity_id=cached.id, prospect_id=prospect_id,
                         actor=actor, action="research_cache_hit", details={"kind": "standard"})
            session.commit()
            return cached
    return _execute(session, prospect, "standard", version, system, user, config.STANDARD_MAX_SEARCHES,
                    focus=None, actor=actor)


def deep_research_plan(session: Session, prospect_id: str) -> dict:
    """What Deep Research would target, shown to the user before they confirm."""
    from ..assessment.engine import latest_assessment

    a = latest_assessment(session, prospect_id)
    coverage = (a.coverage if a else None) or {}
    focus: dict[str, str] = {}
    for f, v in coverage.items():
        if v["status"] in ("not_found", "conflicting", "stale", "not_searched"):
            focus[f] = {"not_found": "not found in standard research",
                        "conflicting": "sources disagree",
                        "stale": "evidence may be out of date",
                        "not_searched": "not researched yet"}[v["status"]]
    # Routing-relevant fields are always worth a second look.
    focus.setdefault("employee_count", "decides Tier 2 eligibility; cross-check with independent sources")
    focus.setdefault("travel_indicators", "direct travel evidence carries the most weight")
    est_max = (config.DEEP_MAX_SEARCHES * config.PRICE_PER_WEB_SEARCH
               + 60_000 / 1e6 * config.PRICE_INPUT_PER_MTOK + 8_000 / 1e6 * config.PRICE_OUTPUT_PER_MTOK)
    return {
        "focus": focus,
        "max_searches": config.DEEP_MAX_SEARCHES,
        "estimated_max_cost_usd": round(est_max, 3),
        "note": "Deep Research is an additional paid research operation. Existing evidence is reused and kept.",
    }


def run_deep_research(session: Session, prospect_id: str, focus_fields: Optional[list[str]] = None,
                      actor: str = "user") -> ResearchRun:
    prospect = session.get(Prospect, prospect_id)
    if prospect is None:
        raise ValueError(f"Unknown prospect {prospect_id}")
    plan = deep_research_plan(session, prospect_id)
    focus = plan["focus"]
    if focus_fields:
        focus = {f: focus.get(f, "requested by user") for f in focus_fields if f in RESEARCH_FIELDS}
    existing = [
        {"field": e.field, "claim": e.claim, "source_url": e.source_url, "published_date": e.published_date}
        for e in session.exec(select(Evidence).where(Evidence.prospect_id == prospect_id,
                                                      Evidence.superseded_by == None,  # noqa: E711
                                                      Evidence.origin == "ai_research"))
    ]
    system, user = prompts.build_deep_prompt(prospect.company_name, prospect.domain, focus, existing)
    return _execute(session, prospect, "deep", f"deep-{prompts.CURRENT_VERSION}", system, user,
                    config.DEEP_MAX_SEARCHES, focus=list(focus), actor=actor)


def _execute(session, prospect, kind, version, system, user, max_searches, focus, actor) -> ResearchRun:
    run = ResearchRun(prospect_id=prospect.id, kind=kind, prompt_version=version, model=config.RESEARCH_MODEL,
                      focus_fields=focus)
    session.add(run)
    session.commit()
    session.refresh(run)
    audit.record(session, entity_type="research_run", entity_id=run.id, prospect_id=prospect.id, actor=actor,
                 action="research_started", details={"kind": kind, "prompt_version": version})

    try:
        client = _client_factory()
        result = client.complete(system, user, max_searches)
    except ResearchProviderError as e:
        return _fail(session, run, str(e))
    except Exception as e:  # never let an unexpected provider error crash the request
        return _fail(session, run, f"Unexpected research error: {type(e).__name__}: {e}")

    totals = LLMResult(text=result.text, search_results=result.search_results, cited_urls=result.cited_urls,
                       input_tokens=result.input_tokens, output_tokens=result.output_tokens,
                       web_search_requests=result.web_search_requests, llm_calls=result.llm_calls)
    run.raw_text = result.text
    run.searched_results = result.search_results

    output: Optional[ResearchOutput] = None
    try:
        output = parse_research_output(result.text)
    except ParseError as first_error:
        # One repair attempt, without web search, reusing the same findings.
        try:
            repair = client.complete(
                "You fix JSON formatting. Return only a JSON object.",
                f"Original answer:\n{result.text}\n\n" + prompts.REPAIR_PROMPT.format(error=str(first_error)),
                None,
            )
            totals.input_tokens += repair.input_tokens
            totals.output_tokens += repair.output_tokens
            totals.llm_calls += repair.llm_calls
            run.raw_text = (run.raw_text or "") + "\n\n--- repair attempt ---\n" + repair.text
            output = parse_research_output(repair.text)
            run.error = f"First response failed validation and was repaired: {first_error}"
        except (ParseError, ResearchProviderError) as second_error:
            _apply_usage(run, totals)
            return _fail(session, run, f"Malformed research output after one repair attempt: {second_error}")

    _apply_usage(run, totals)
    allowed = {r["url"] for r in result.search_results} | set(result.cited_urls)
    output, dropped = validate_citations(output, allowed)
    run.dropped_findings = dropped
    run.parsed = output.model_dump()
    run.summary = output.summary
    run.limitations = output.research_limitations
    if not output.company_identity_confirmed:
        run.limitations = (run.limitations or []) + [f"Company identity not confirmed: {output.identity_note}"]

    _store_evidence(session, prospect, run, output, kind, focus)
    run.status = "partial" if (dropped or not output.company_identity_confirmed) else "ok"
    run.finished_at = utcnow()
    session.add(run)
    audit.record(session, entity_type="research_run", entity_id=run.id, prospect_id=prospect.id, actor=actor,
                 action="research_completed",
                 details={"kind": kind, "status": run.status, "web_searches": run.web_search_requests,
                          "approx_cost_usd": run.approx_cost_usd, "dropped_findings": len(dropped)})
    session.commit()
    reassess(session, prospect.id, trigger="deep_research" if kind == "deep" else "research", actor=actor)
    session.refresh(run)
    return run


def _apply_usage(run: ResearchRun, t: LLMResult) -> None:
    run.input_tokens = t.input_tokens
    run.output_tokens = t.output_tokens
    run.web_search_requests = t.web_search_requests
    run.llm_calls = t.llm_calls
    run.approx_cost_usd = estimate_cost(t.input_tokens, t.output_tokens, t.web_search_requests)


def _fail(session: Session, run: ResearchRun, message: str) -> ResearchRun:
    run.status = "failed"
    run.error = message
    run.finished_at = utcnow()
    session.add(run)
    audit.record(session, entity_type="research_run", entity_id=run.id, prospect_id=run.prospect_id,
                 action="research_failed", details={"error": message})
    session.commit()
    session.refresh(run)
    return run


def _store_evidence(session, prospect, run, output: ResearchOutput, kind, focus) -> None:
    cutoff = run.research_cutoff
    reported = {fr.field for fr in output.fields}
    fields_in_scope = list(RESEARCH_FIELDS) if kind == "standard" else (focus or list(reported))

    if kind == "standard":
        # A fresh standard run supersedes earlier standard-run evidence (kept, not deleted).
        old = session.exec(select(Evidence).where(Evidence.prospect_id == prospect.id,
                                                  Evidence.origin == "ai_research",
                                                  Evidence.superseded_by == None))  # noqa: E711
        old_rows = [e for e in old if e.run_id != run.id and _run_kind(session, e.run_id) == "standard"]
    else:
        old_rows = []

    first_new_id = None
    for fr in output.fields:
        if fr.field not in fields_in_scope:
            continue
        stale_flags = []
        for f in fr.findings:
            if is_future(f.published_date, cutoff):
                run.dropped_findings = (run.dropped_findings or []) + [
                    {"field": fr.field, "claim": f.claim, "source_url": f.source_url,
                     "reason": "published after the research cutoff"}]
                continue
            stale = is_stale(f.published_date, cutoff)
            stale_flags.append(stale)
            e = Evidence(
                prospect_id=prospect.id, run_id=run.id, field=fr.field, claim=f.claim,
                value_number=f.value_number if fr.field == "employee_count" else None,
                signal_type=f.signal_type, observation=f.observation,
                source_title=f.source_title, source_url=f.source_url, publisher=f.publisher,
                published_date=f.published_date, reliability=classify_reliability(f.source_url, prospect.domain),
                origin="ai_research", is_stale=stale, retrieved_at=cutoff,
            )
            session.add(e)
            session.flush()
            first_new_id = first_new_id or e.id
        status = fr.status
        if status in ("found", "conflicting") and not stale_flags:
            status = "not_found"
            summary = (fr.summary + " " if fr.summary else "") + "(No finding survived citation validation.)"
        else:
            summary = fr.summary
        if status == "found" and stale_flags and all(stale_flags):
            status = "stale"
        session.add(FieldStatus(run_id=run.id, prospect_id=prospect.id, field=fr.field, status=status,
                                summary=summary))
    for f in fields_in_scope:
        if f not in reported:
            session.add(FieldStatus(run_id=run.id, prospect_id=prospect.id, field=f, status="not_found",
                                    summary="Research returned no result for this field."))
    for e in old_rows:
        e.superseded_by = f"run:{run.id}"
        session.add(e)


def _run_kind(session: Session, run_id: Optional[int]) -> Optional[str]:
    if run_id is None:
        return None
    r = session.get(ResearchRun, run_id)
    return r.kind if r else None
