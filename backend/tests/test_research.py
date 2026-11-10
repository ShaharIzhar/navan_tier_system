import json
import pytest
from sqlmodel import select

from app.assessment.engine import latest_assessment
from app.models import Evidence, PostSignupActivity, ResearchRun
from app.research import prompts
from app.research import service as rs
from app.research.client import ResearchProviderError
from app.research.evidence import ParseError, extract_json, normalize_url

from .conftest import finding, llm_result, research_json


def test_missing_api_key_fails_visibly(session, monkeypatch):
    from app import config

    monkeypatch.setattr(config, "ANTHROPIC_API_KEY", "")
    rs.set_client_factory(lambda: rs.AnthropicResearchClient())
    run = rs.run_standard_research(session, "P-033")
    assert run.status == "failed" and "not configured" in run.error
    assert session.exec(select(Evidence).where(Evidence.prospect_id == "P-033")).all() == []


def test_valid_research_creates_evidence_and_reassesses(session, fake_llm):
    url = "https://www.example-news.com/attio-raises"
    text = research_json({"funding_financial": ("found", [finding("Raised $52M Series B", url, signal="indirect_growth", date="2025-08-01")])})
    fake_llm(llm_result(text, [url]))
    run = rs.run_standard_research(session, "P-002")
    assert run.status == "ok"
    ev = session.exec(select(Evidence).where(Evidence.run_id == run.id)).all()
    assert len(ev) == 1 and ev[0].reliability == "secondary" and ev[0].origin == "ai_research"
    a = latest_assessment(session, "P-002")
    assert a.trigger == "research"
    assert a.coverage["funding_financial"]["status"] == "found"
    assert a.coverage["employee_count"]["status"] == "not_found"


def test_fabricated_citation_is_dropped(session, fake_llm):
    real, fake = "https://real.example.com/a", "https://invented.example.com/b"
    text = research_json({
        "travel_indicators": ("found", [finding("Field engineers travel to client sites", fake, signal="direct_travel")]),
        "industry_business_model": ("found", [finding("Biotech company", real)]),
    })
    fake_llm(llm_result(text, [real]))
    run = rs.run_deep_research(session, "P-007")
    assert run.status == "partial"
    assert len(run.dropped_findings) == 1 and "unsupported_citation" in run.dropped_findings[0]["reason"]
    a = latest_assessment(session, "P-007")
    assert a.coverage["travel_indicators"]["status"] == "not_found"
    assert not any(f["type"] == "travel_potential" for f in a.flags)


def test_malformed_output_is_repaired_once(session, fake_llm):
    url = "https://x.example.com/p"
    good = research_json({"industry_business_model": ("found", [finding("Makes audio gear", url)])})
    client = fake_llm(llm_result("Here is my research: {not json", [url]), llm_result(good, [], searches=0))
    run = rs.run_standard_research(session, "P-030")
    assert run.status == "ok" and "repaired" in run.error
    assert len(client.calls) == 2 and client.calls[1]["max_searches"] is None  # repair uses no web search
    assert run.llm_calls == 2


def test_malformed_twice_fails_without_evidence(session, fake_llm):
    fake_llm(llm_result("garbage", []), llm_result('{"summary": "missing fields"}', []))
    run = rs.run_standard_research(session, "P-030")
    assert run.status == "failed" and "Malformed" in run.error
    assert session.exec(select(Evidence).where(Evidence.prospect_id == "P-030")).all() == []


def test_timeout_is_recorded(session, fake_llm):
    fake_llm(ResearchProviderError("Research timed out after 120s."))
    run = rs.run_standard_research(session, "P-009")
    assert run.status == "failed" and "timed out" in run.error
    assert latest_assessment(session, "P-009").baseline["tier"] == 2  # rules still work


def test_cache_prevents_repeat_llm_call(session, fake_llm):
    url = "https://x.example.com/p"
    client = fake_llm(llm_result(research_json({"industry_business_model": ("found", [finding("Cloud GPU provider", url)])}), [url]))
    first = rs.run_standard_research(session, "P-009")
    second = rs.run_standard_research(session, "P-009")
    assert first.id == second.id and len(client.calls) == 1


def test_force_rerun_supersedes_but_keeps_old_evidence(session, fake_llm):
    url = "https://x.example.com/p"
    text = research_json({"industry_business_model": ("found", [finding("Cloud GPU provider", url)])})
    fake_llm(llm_result(text, [url]), llm_result(text, [url]))
    r1 = rs.run_standard_research(session, "P-009")
    r2 = rs.run_standard_research(session, "P-009", force=True)
    old = session.exec(select(Evidence).where(Evidence.run_id == r1.id)).all()
    assert old and all(e.superseded_by == f"run:{r2.id}" for e in old)


def test_stale_and_future_dates(session, fake_llm):
    url = "https://x.example.com/p"
    text = research_json({
        "employee_count": ("found", [finding("About 40 employees", url, value=40, date="2019-01-01")]),
        "recent_expansion": ("found", [finding("Opens office", url, signal="indirect_growth", date="2099-01-01")]),
    })
    fake_llm(llm_result(text, [url]))
    run = rs.run_deep_research(session, "P-018")
    ev = session.exec(select(Evidence).where(Evidence.run_id == run.id)).all()
    assert len(ev) == 1 and ev[0].is_stale
    assert any("cutoff" in d["reason"] for d in run.dropped_findings)
    assert latest_assessment(session, "P-018").coverage["employee_count"]["status"] == "stale"


def test_day0_prompt_contains_no_post_signup_data(session):
    acts = session.exec(select(PostSignupActivity)).all()
    from app.models import Prospect

    for act in acts:
        p = session.get(Prospect, act.prospect_id)
        _, system, user = prompts.build_standard_prompt(p.company_name, p.domain)
        text = system + user
        assert act.raw_text not in text
        assert "bookings" not in text.lower() and "traveler" not in text.lower()
        assert str(int(p.entered_gbv_usd)) not in text  # research is independent of reported GBV


def test_deep_research_requires_confirmation_and_reuses_evidence(session, fake_llm):
    from fastapi.testclient import TestClient
    from app.main import app

    url = "https://x.example.com/p"
    client = fake_llm(
        llm_result(research_json({"industry_business_model": ("found", [finding("Biotech", url)])}), [url]),
        llm_result(research_json({"employee_count": ("found", [finding("~160 staff", url, value=160)])}), [url]),
    )
    rs.run_standard_research(session, "P-007")
    with TestClient(app) as c:
        assert c.post("/api/prospects/P-007/deep-research", json={}).status_code == 400
        assert len(client.calls) == 1  # nothing ran without confirmation
        plan = c.get("/api/prospects/P-007/deep-research/plan").json()
        assert "employee_count" in plan["focus"] and plan["max_searches"] > 0
        r = c.post("/api/prospects/P-007/deep-research", json={"confirm": True}).json()
        assert r["kind"] == "deep" and r["status"] == "running"  # runs in the background
        import time
        for _ in range(100):
            prog = c.get("/api/prospects/P-007/active-research").json()
            if not prog["running"]:
                break
            time.sleep(0.05)
    assert prog["last"]["kind"] == "deep" and prog["last"]["status"] == "ok" and prog["last"]["stage"] == "done"
    assert "Biotech" in client.calls[1]["user"]  # existing evidence passed as context
    ev = session.exec(select(Evidence).where(Evidence.prospect_id == "P-007", Evidence.origin == "ai_research")).all()
    assert len(ev) == 2  # standard evidence kept alongside deep evidence


def test_extract_json_variants():
    assert extract_json('```json\n{"a": 1}\n```') == {"a": 1}
    assert extract_json('Sure! {"a": 2} hope that helps') == {"a": 2}
    for bad in ("", "no json", "[1,2]"):
        with pytest.raises(ParseError):
            extract_json(bad)


def test_normalize_url():
    assert normalize_url("https://www.Example.com/a/?utm_source=x") == normalize_url("http://example.com/a")


def test_headcount_band_is_not_used_as_exact_number(session, fake_llm):
    """Regression for an observed v1 failure: '101-250' was stored as value_number=101."""
    u = "https://www.crunchbase.com/organization/x"
    text = research_json({"employee_count": ("found", [
        finding("Crunchbase shows a headcount band of 101-250.", u, value=101),
        finding("ZoomInfo lists fewer than 25 employees.", u, value=25),
        finding("BuiltIn lists 92 total employees.", u, value=92)])})
    fake_llm(llm_result(text, [u]))
    run = rs.run_standard_research(session, "P-009")
    vals = sorted(e.value_number for e in session.exec(select(Evidence).where(Evidence.run_id == run.id))
                  if e.value_number is not None)
    assert vals == [92]
    assert len(run.normalized_findings) == 2


def test_non_routing_llm_conflicts_do_not_raise_flags(session, fake_llm):
    """Regression for observed v1 noise: funding-total differences became Data Conflict flags."""
    u = "https://a.example.com/x"
    text = research_json(
        {"funding_financial": ("conflicting", [finding("Raised $45M", u, signal="indirect_growth")])},
        conflicts=[{"field": "funding_financial", "description": "Totals differ by source", "source_urls": [u]}],
    )
    fake_llm(llm_result(text, [u]))
    rs.run_standard_research(session, "P-009")
    a = latest_assessment(session, "P-009")
    assert "data_conflict" not in {f["type"] for f in a.flags}


def test_band_check_ignores_dates():
    """Live P-025: '703 people ... period ending 2023-12-31' was cleared because 2023-12 looked like a range."""
    from app.research.evidence import clear_band_headcounts
    from app.research.schema import ResearchOutput

    out = ResearchOutput.model_validate(json.loads(research_json({"employee_count": ("found", [
        finding("Employs 703 people, based on accounts for the period ending 2023-12-31.", "https://x.example/a", value=703)])})))
    assert clear_band_headcounts(out) == []
    assert out.fields[2].findings[0].value_number == 703


def test_company_site_headcount_is_recovered_and_listed_first(session, fake_llm):
    """Live P-021: the company's own '26,000 employees' had no number; it should be used and shown first."""
    own, agg = "https://www.balfourbeatty.com/about-us/", "https://tracxn.com/d/balfour"
    text = research_json({"employee_count": ("found", [
        finding("Tracxn reports 14,941 employees", agg, value=14941),
        finding("The company describes itself as having 26,000 employees (rounded figure).", own),
        finding("Over 700 staff worldwide", own)])})
    fake_llm(llm_result(text, [own, agg]))
    run = rs.run_standard_research(session, "P-021")
    assert any("recovered" in n["reason"] for n in run.normalized_findings)
    srcs = latest_assessment(session, "P-021").accepted_values["employee_sources"]
    research = [s for s in srcs if s["origin"] == "ai_research"]
    assert research[0]["value"] == 26000 and research[0]["company_site"] and research[0]["label"].startswith("Company website")
    assert srcs[0]["company_site"]  # company website listed before everything else
    assert 700 not in [s["value"] for s in srcs]  # bands are never recovered


def test_reprocess_rebuilds_evidence_without_ai(session, fake_llm):
    own = "https://www.balfourbeatty.com/about-us/"
    client = fake_llm(llm_result(research_json({"employee_count": ("found", [
        finding("The company has 26,000 employees.", own)])}), [own]))
    first = rs.run_standard_research(session, "P-021")
    new = rs.reprocess_run(session, first.id)
    assert len(client.calls) == 1  # no second AI call
    assert new.status == "ok" and new.llm_calls == 0 and new.approx_cost_usd == 0 and "Reprocessed" in new.error
    assert new.research_cutoff == first.research_cutoff



def test_only_one_deep_research_runs_at_a_time_and_restart_cleans_up(session, fake_llm):
    import threading

    gate = threading.Event()
    url = "https://x.example.com/p"

    class SlowClient:
        def complete(self, system, user, max_searches):
            gate.wait(5)
            return llm_result(research_json({"employee_count": ("found", [finding("53 staff", url, value=53)])}), [url])

    rs.set_client_factory(lambda: SlowClient())
    first, t = rs.start_deep_research(session, "P-007")
    again, t2 = rs.start_deep_research(session, "P-007")
    assert again.id == first.id and t2 is None  # no duplicate run
    assert rs.active_run(session, "P-007").id == first.id
    gate.set()
    t.join(5)
    session.expire_all()
    done = session.get(ResearchRun, first.id)
    assert done.status == "ok" and done.stage == "done"

    stuck = ResearchRun(prospect_id="P-009", kind="deep", status="running", stage="searching")
    session.add(stuck)
    session.commit()
    assert rs.mark_interrupted_runs(session) == 1
    assert session.get(ResearchRun, stuck.id).status == "failed"



def test_research_output_without_summary_is_accepted():
    from app.research.schema import ResearchOutput
    out = ResearchOutput.model_validate({"company_identity_confirmed": True, "fields": [], "conflicts": []})
    assert out.summary == ""
