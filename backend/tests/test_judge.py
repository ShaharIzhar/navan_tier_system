import json

from sqlmodel import select

from app.enrichment import add_synthetic_evidence
from app.models import AuditEvent, TierProposal
from app.research.judge import get_or_create_judgement, ungrounded_numbers

from .conftest import llm_result


def _proposal(session):
    add_synthetic_evidence(session, "P-007", "employee_count", "90 employees", 90, "descriptive", "t")
    return session.exec(select(TierProposal).where(TierProposal.prospect_id == "P-007")).one()


def _answer(summary, support="partial", doubt="Only a synthetic source disagrees"):
    return llm_result(json.dumps({"summary": summary, "support": support, "main_doubt": doubt}), [], searches=0)


def test_judge_summary_is_stored_and_cached(session, fake_llm):
    p = _proposal(session)
    client = fake_llm(_answer("Downgrade: IMU is Tier 2 only because enrichment says 155 employees, but another source says 90."))
    j = get_or_create_judgement(session, p.id)
    assert j["status"] == "ok" and j["grounded"] and j["support"] == "partial"
    assert client.calls[0]["max_searches"] is None  # no web search
    assert "155" in client.calls[0]["user"] and "90" in client.calls[0]["user"]
    again = get_or_create_judgement(session, p.id)
    assert again["from_cache"] and len(client.calls) == 1
    assert session.exec(select(AuditEvent).where(AuditEvent.action == "ai_judge_summary")).first()


def test_judge_flags_numbers_not_in_the_facts(session, fake_llm):
    p = _proposal(session)
    fake_llm(_answer("Downgrade because the company has 40 staff."))
    j = get_or_create_judgement(session, p.id)
    assert j["status"] == "ok" and not j["grounded"] and j["ungrounded_numbers"] == ["40"]


def test_judge_failure_is_visible_not_fatal(session, fake_llm):
    p = _proposal(session)
    fake_llm(llm_result("not json at all", [], searches=0))
    j = get_or_create_judgement(session, p.id)
    assert j["status"] == "failed" and "unusable" in j["error"]
    assert session.get(TierProposal, p.id).status == "open"  # judge never changes the proposal


def test_judge_reruns_when_evidence_changes(session, fake_llm):
    p = _proposal(session)
    client = fake_llm(_answer("Downgrade: 155 vs 90 employees."), _answer("Downgrade: 155 vs 90 and 80 employees."))
    get_or_create_judgement(session, p.id)
    add_synthetic_evidence(session, "P-007", "employee_count", "80 employees", 80, "descriptive", "t")
    get_or_create_judgement(session, p.id)
    assert len(client.calls) == 2


def test_ungrounded_number_check():
    facts = {"gbv": 48000.0, "employees": 155}
    assert ungrounded_numbers("GBV of $48K and 155 staff, Tier 3", facts) == []
    assert ungrounded_numbers("about 200 staff", facts) == ["200"]
