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
from .evidence import (ParseError, classify_reliability, clear_band_headcounts, is_future, is_stale,
                       parse_research_output, recover_company_site_headcount, validate_citations)
from .schema import RESEARCH_FIELDS, ResearchOutput

ClientFactory = Callable[[], LLMClient]
def _default_client() -> LLMClient:
    from .replay import ReplayClient, provider_mode

    if provider_mode() == "replay":
        return ReplayClient()
    return AnthropicResearchClient()


_client_factory: ClientFactory = _default_client


def set_client_factory(factory: ClientFactory) -> None:
    """Used by tests to inject a fake LLM client."""
    global _client_factory
    _client_factory = factory


def provider_status() -> dict:
    from .replay import provider_mode, recorded_domains

    mode = provider_mode()
    return {
        "configured": mode != "off",
        "mode": mode,  # live | replay | off
        "recorded_companies": recorded_domains() if mode == "replay" else [],
        "model": config.RESEARCH_MODEL,
        "web_search_tool": config.WEB_SEARCH_TOOL_TYPE,
        "standard_max_searches": config.STANDARD_MAX_SEARCHES,
        "deep_max_searches": config.DEEP_MAX_SEARCHES,
        "prompt_version": prompts.current_version(),
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
) -> ResearchRun:
    prospect = session.get(Prospect, prospect_id)
    if prospect is None:
        raise ValueError(f"Unknown prospect {prospect_id}")
    version, system, user = prompts.build_standard_prompt(prospect.company_name, prospect.domain)
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
    """What Deep Research would target, shown to the user before they confirm. Always all 8 fields."""
    from ..assessment.engine import latest_assessment

    a = latest_assessment(session, prospect_id)
    coverage = (a.coverage if a else None) or {}
    why_by_status = {
        "not_searched": "not covered by standard research",
        "not_found": "nothing found yet",
        "conflicting": "sources disagree",
        "stale": "evidence may be out of date",
        "found": "look for stronger or more recent sources",
        "not_applicable": "re-check",
    }
    focus = {f: why_by_status.get((coverage.get(f) or {}).get("status", "not_searched"), "re-check")
             for f in RESEARCH_FIELDS}
    est_max = (config.DEEP_MAX_SEARCHES * config.PRICE_PER_WEB_SEARCH
               + 60_000 / 1e6 * config.PRICE_INPUT_PER_MTOK + 8_000 / 1e6 * config.PRICE_OUTPUT_PER_MTOK)
    return {
        "focus": focus,
        "max_searches": config.DEEP_MAX_SEARCHES,
        "estimated_max_cost_usd": round(est_max, 3),
        "note": "Deep Research is an additional paid research operation covering all fields. Existing evidence is reused and kept.",
    }


def run_deep_research(session: Session, prospect_id: str, focus_fields: Optional[list[str]] = None,
                      actor: str = "user", run_id: Optional[int] = None) -> ResearchRun:
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
    # Day 0 inputs only (never Day 30 activity).
    signup = "\n".join([
        f"- Reported annual GBV: ${prospect.entered_gbv_usd:,.0f}" if prospect.entered_gbv_usd is not None else "- Reported annual GBV: not given",
        f"- Employee estimate from data provider (ZoomInfo): {prospect.zi_employees:,}" if prospect.zi_employees else "- Employee estimate from data provider: none",
    ])
    system, user = prompts.build_deep_prompt(prospect.company_name, prospect.domain, focus, existing, signup)
    return _execute(session, prospect, "deep", f"deep-{prompts.current_version()}", system, user,
                    config.DEEP_MAX_SEARCHES, focus=list(focus), actor=actor,
                    existing_run=session.get(ResearchRun, run_id) if run_id else None)


def _set_stage(session: Session, run: ResearchRun, stage: str) -> None:
    run.stage = stage
    session.add(run)
    session.commit()


def _execute(session, prospect, kind, version, system, user, max_searches, focus, actor, from_run=None,
             existing_run: Optional[ResearchRun] = None) -> ResearchRun:
    run = existing_run or ResearchRun(prospect_id=prospect.id, kind=kind, prompt_version=version,
                                      model=config.RESEARCH_MODEL, focus_fields=focus)
    run.prompt_version, run.focus_fields = version, focus
    if from_run is not None:  # reprocessing a stored run: keep its identity and research date
        run.model, run.replayed, run.research_cutoff = from_run.model, from_run.replayed, from_run.research_cutoff
    session.add(run)
    session.commit()
    session.refresh(run)
    audit.record(session, entity_type="research_run", entity_id=run.id, prospect_id=prospect.id, actor=actor,
                 action="research_started", details={"kind": kind, "prompt_version": version})

    try:
        client = _client_factory()
        if getattr(client, "replayed", False):
            from .replay import recorded_run

            rec = recorded_run(prospect.domain, kind)
            run.replayed = True
            run.model = f"{rec['model']} (recorded)" if rec else "recorded"
            if rec:
                from datetime import datetime

                run.research_cutoff = datetime.fromisoformat(rec["research_cutoff"])
                run.prompt_version = rec["prompt_version"]
            session.add(run)
            session.commit()
        _set_stage(session, run, "searching")
        result = client.complete(system, user, max_searches)
        _set_stage(session, run, "checking")
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
                f"Original answer:\n{result.text}\n\n" + prompts.repair_prompt(str(first_error)),
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
    run.normalized_findings = clear_band_headcounts(output) + recover_company_site_headcount(output, prospect.domain)
    run.search_queries = result.search_queries
    run.parsed = output.model_dump()
    run.summary = output.summary
    run.limitations = output.research_limitations
    if not output.company_identity_confirmed:
        run.limitations = (run.limitations or []) + [f"Company identity not confirmed: {output.identity_note}"]

    _set_stage(session, run, "saving")
    _store_evidence(session, prospect, run, output, kind, focus)
    run.stage = "done"
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
    run.stage = "failed"
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
    if kind == "standard":
        # Only the fields this prompt version covers; the rest stay "Not searched".
        fields_in_scope = prompts.fields_for_run(run.prompt_version)
    else:
        fields_in_scope = focus or list(reported)

    # A new run supersedes earlier evidence from runs of the same kind for the fields it covers
    # (kept, not deleted). A Deep Research pass leaves standard-run evidence as is, and vice versa.
    old = session.exec(select(Evidence).where(Evidence.prospect_id == prospect.id,
                                              Evidence.origin == "ai_research",
                                              Evidence.superseded_by == None))  # noqa: E711
    old_rows = [e for e in old if e.run_id != run.id and e.field in fields_in_scope
                and _run_kind(session, e.run_id) == kind]

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
                travel_scope=f.travel_scope if f.signal_type == "direct_travel" else None,
                source_title=f.source_title, source_url=f.source_url, publisher=f.publisher,
                published_date=f.published_date, reliability=classify_reliability(f.source_url, prospect.domain),
                origin="ai_research", is_stale=stale, retrieved_at=cutoff,
            )
            session.add(e)
            session.flush()
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


class _StoredRunClient:
    """Returns a stored run's original model output. Used to re-apply updated validation rules."""
    replayed = False

    def __init__(self, run: ResearchRun):
        self.run = run

    def complete(self, system: str, user: str, max_searches: Optional[int]) -> LLMResult:
        # Original answer, or the repaired one when only that is valid JSON.
        parts = (self.run.raw_text or "").split("\n\n--- repair attempt ---\n")
        text = parts[0]
        for candidate in parts:
            try:
                parse_research_output(candidate)
                text = candidate
                break
            except Exception:  # noqa: BLE001
                continue
        return LLMResult(text=text, search_results=self.run.searched_results or [],
                         search_queries=self.run.search_queries or [], llm_calls=0)


def reprocess_run(session: Session, run_id: int, actor: str = "system:reprocess") -> ResearchRun:
    """Re-run validation and evidence storage on a stored run's raw output. No AI call, no cost."""
    old = session.get(ResearchRun, run_id)
    # Failed runs can be recovered too when the search results were saved (e.g. after a validation fix).
    if old is None or not old.raw_text or (old.status not in ("ok", "partial") and not old.searched_results):
        raise ValueError("Run cannot be reprocessed.")
    prospect = session.get(Prospect, old.prospect_id)
    global _client_factory
    saved_factory = _client_factory
    _client_factory = lambda: _StoredRunClient(old)  # noqa: E731
    try:
        new = _execute(session, prospect, old.kind, old.prompt_version, "", "", None, focus=old.focus_fields,
                       actor=actor, from_run=old)
    finally:
        _client_factory = saved_factory
    new.input_tokens = new.output_tokens = new.web_search_requests = new.llm_calls = 0
    new.approx_cost_usd = 0.0
    new.error = f"Reprocessed from run #{old.id} with updated validation (no new AI call)."
    session.add(new)
    session.commit()
    return new


# ---------------------------------------------------------------------------
# Background Deep Research
# ---------------------------------------------------------------------------
DEEP_EXPECTED_SECONDS = 90  # typical duration, used only for the progress estimate


def active_run(session: Session, prospect_id: str) -> Optional[ResearchRun]:
    return session.exec(select(ResearchRun).where(ResearchRun.prospect_id == prospect_id,
                                                  ResearchRun.status == "running")
                        .order_by(ResearchRun.id.desc())).first()


def start_deep_research(session: Session, prospect_id: str, focus_fields: Optional[list[str]] = None,
                        actor: str = "user"):
    """Start Deep Research in a background thread. Returns (run, thread). One running run per company."""
    import threading

    from ..db import get_engine

    if session.get(Prospect, prospect_id) is None:
        raise ValueError(f"Unknown prospect {prospect_id}")
    running = active_run(session, prospect_id)
    if running is not None:
        return running, None
    run = ResearchRun(prospect_id=prospect_id, kind="deep", status="running", stage="queued",
                      model=config.RESEARCH_MODEL, focus_fields=focus_fields)
    session.add(run)
    session.commit()
    session.refresh(run)
    run_id = run.id

    def work():
        with Session(get_engine()) as s:
            try:
                run_deep_research(s, prospect_id, focus_fields, actor=actor, run_id=run_id)
            except Exception as e:  # never leave a run stuck in "running"
                r = s.get(ResearchRun, run_id)
                if r is not None and r.status == "running":
                    _fail(s, r, f"Deep Research stopped unexpectedly: {type(e).__name__}")

    t = threading.Thread(target=work, name=f"deep-research-{prospect_id}", daemon=True)
    t.start()
    return run, t


def mark_interrupted_runs(session: Session) -> int:
    """On startup, runs still marked 'running' were cut off by a restart."""
    stuck = list(session.exec(select(ResearchRun).where(ResearchRun.status == "running")))
    for r in stuck:
        _fail(session, r, "Interrupted by a server restart. Please run it again.")
    return len(stuck)
