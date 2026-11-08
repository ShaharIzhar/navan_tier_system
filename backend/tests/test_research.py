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
    run = rs.run_standard_research(session, "P-007")
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
    run = rs.run_standard_research(session, "P-018")
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
    assert r["kind"] == "deep" and r["status"] == "ok"
    assert "Biotech" in client.calls[1]["user"]  # existing evidence passed as context
    ev = session.exec(select(Evidence).where(Evidence.prospect_id == "P-007", Evidence.origin == "ai_research")).all()
    assert len(ev) == 2  # standard evidence kept alongside deep evidence


def test_extract_json_variants():
    assert extract_json('```json\n{"a": 1}\n```') == {"a": 1}
    assert extract_json('Sure! {"a": 2} hope that helps') == {"a": 2}
    for bad in ("", "no json", "[1,2]"):
        try:
            extract_json(bad)
            assert False
        except ParseError:
            pass


def test_normalize_url():
    assert normalize_url("https://www.Example.com/a/?utm_source=x") == normalize_url("http://example.com/a")
