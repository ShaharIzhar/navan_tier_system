import pytest
from sqlmodel import select

from app.assessment.engine import latest_assessment, reassess
from app.enrichment import EnrichmentError, add_enrichment, add_synthetic_evidence, retract_evidence
from app.models import Assessment, AuditEvent, Evidence, PostSignupActivity, Prospect, ReviewDecision, TierProposal
from app.postsignup import release_day30
from app.research import service as rs
from app.reviews.service import ReviewError, decide

from .conftest import finding, llm_result, research_json


def flag_types(a):
    return {f["type"] for f in a.flags}


def flag(a, t):
    return next(f for f in a.flags if f["type"] == t)


# --- Synthetic conflict on P-007 (the PRD's suggested hard case) ---------------------

def test_synthetic_conflict_crossing_150_is_material(session):
    add_synthetic_evidence(session, "P-007", "employee_count", "Alternative estimate: 90 employees", 90,
                           "descriptive", "tester")
    a = latest_assessment(session, "P-007")
    f = flag(a, "data_conflict")
    assert f["severity"] == "material"
    assert any("SYNTHETIC" in u for u in f["uncertainty"])
    assert "tier_mismatch" in flag_types(a)
    assert a.attention == "review_now"
    p = session.exec(select(TierProposal).where(TierProposal.prospect_id == "P-007")).one()
    assert (p.proposal_type, p.from_tier, p.proposed_tier) == ("standard_rule_correction", 2, 3)
    ev = session.exec(select(Evidence).where(Evidence.origin == "synthetic_test")).one()
    assert ev.reliability == "synthetic" and ev.claim.startswith("[SYNTHETIC TEST]")


def test_conflict_not_material_when_gbv_sets_tier(session):
    add_synthetic_evidence(session, "P-018", "employee_count", "Estimate: 200 employees", 200, "descriptive", "t")
    f = flag(latest_assessment(session, "P-018"), "data_conflict")
    assert f["severity"] == "moderate"
    assert not session.exec(select(TierProposal).where(TierProposal.prospect_id == "P-018")).all()


# --- Manual enrichment -----------------------------------------------------------------

def test_manual_enrichment_reassesses_without_llm(session, fake_llm):
    client = fake_llm()  # any LLM call would raise IndexError
    e, after, before = add_enrichment(session, "P-011", "employee_count", "180", "Dana")
    assert len(client.calls) == 0
    assert before.baseline["provisional"] is True and before.baseline["tier"] == 3
    assert after.baseline["tier"] == 2 and after.trigger == "manual_enrichment"
    assert e.reliability == "manual_unverified" and e.origin == "human"
    # Applied tier never changes automatically
    assert session.get(Prospect, "P-011").applied_tier == 3
    p = session.exec(select(TierProposal).where(TierProposal.prospect_id == "P-011")).one()
    assert p.proposal_type == "standard_rule_correction" and p.proposed_tier == 2
    assert "unverified" in " ".join(p.uncertainties)
    # Audit + previous assessment preserved
    assert session.exec(select(AuditEvent).where(AuditEvent.action == "manual_enrichment")).first()
    assert session.get(Assessment, before.id).baseline["tier"] == 3


def test_verified_requires_source(session):
    e, *_ = add_enrichment(session, "P-011", "employee_count", "120", "Dana", verified=True)
    assert e.reliability == "manual_unverified"
    e2, *_ = add_enrichment(session, "P-011", "employee_count", "125", "Dana", verified=True,
                            source_url="https://example.com/about")
    assert e2.reliability == "manual_verified"


def test_verified_manual_value_resolves_conflict(session):
    add_synthetic_evidence(session, "P-007", "employee_count", "90 employees", 90, "descriptive", "t")
    add_enrichment(session, "P-007", "employee_count", "160", "Dana", verified=True,
                   source_url="https://example.com/team")
    a = latest_assessment(session, "P-007")
    assert flag(a, "data_conflict")["severity"] == "low"
    assert a.accepted_values["employees"] == 160


def test_enrichment_validation(session):
    with pytest.raises(EnrichmentError):
        add_enrichment(session, "P-011", "employee_count", "lots", "Dana")
    with pytest.raises(EnrichmentError):
        add_enrichment(session, "P-011", "employee_count", "10", "")
    with pytest.raises(EnrichmentError):
        add_enrichment(session, "P-011", "salary", "10", "Dana")


def test_free_text_note_does_not_change_signals(session):
    before = latest_assessment(session, "P-033")
    _, after, _ = add_enrichment(session, "P-033", "note", "Owner mentioned frequent trade shows", "Dana")
    assert flag_types(after) == flag_types(before)


def test_withdrawing_manual_value_restores_previous_state(session):
    e, *_ = add_enrichment(session, "P-011", "employee_count", "180", "Dana")
    retract_evidence(session, e.id, "Dana", "typo")
    a = latest_assessment(session, "P-011")
    assert a.baseline["provisional"] is True
    assert session.exec(select(TierProposal).where(TierProposal.prospect_id == "P-011")).one().status == "superseded"


# --- Flags from research ---------------------------------------------------------------

def test_growth_without_travel_is_not_travel_potential(session, fake_llm):
    u1, u2 = "https://a.example.com/1", "https://b.example.com/2"
    text = research_json({
        "funding_financial": ("found", [finding("Raised Series B", u1, signal="indirect_growth"),
                                        finding("Series B coverage", u2, signal="indirect_growth")]),
        "recent_expansion": ("found", [finding("Opened New York office", u2, signal="indirect_growth")]),
    })
    fake_llm(llm_result(text, [u1, u2]))
    rs.run_standard_research(session, "P-002", prompt_version="v3")
    a = latest_assessment(session, "P-002")
    assert "growth_opportunity" in flag_types(a)
    assert "travel_potential" not in flag_types(a) and "tier_mismatch" not in flag_types(a)
    assert any("not evidence of higher travel spend" in u for u in flag(a, "growth_opportunity")["uncertainty"])


def test_duplicate_sources_count_once(session, fake_llm):
    u1 = "https://news.example.com/story"
    text = research_json({"funding_financial": ("found", [
        finding("Raised $10M", u1, signal="indirect_growth"),
        finding("Raised $10M (same story)", u1 + "?utm_source=x", signal="indirect_growth")])})
    fake_llm(llm_result(text, [u1]))
    rs.run_standard_research(session, "P-001")
    # One growth field from one source -> below the 2-independent-signal threshold
    assert "growth_opportunity" not in flag_types(latest_assessment(session, "P-001"))


def test_strong_travel_evidence_on_tier3_creates_override_proposal(session, fake_llm):
    u1, u2 = "https://jobs.example.com/eng", "https://moorsideengineering.com/services"
    text = research_json({"travel_indicators": ("found", [
        finding("Field service engineers travel to customer sites across the UK", u1, signal="direct_travel"),
        finding("Installation teams work on-site nationwide", u2, signal="direct_travel")])})
    fake_llm(llm_result(text, [u1, u2]))
    rs.run_standard_research(session, "P-033", prompt_version="v3")
    a = latest_assessment(session, "P-033")
    assert flag(a, "travel_potential")["severity"] == "material"
    p = session.exec(select(TierProposal).where(TierProposal.prospect_id == "P-033")).one()
    assert (p.proposal_type, p.from_tier, p.proposed_tier) == ("evidence_override", 3, 2)


def test_aggregator_or_inferred_travel_does_not_flag(session, fake_llm):
    u1 = "https://www.linkedin.com/company/x"
    text = research_json({"travel_indicators": ("found", [
        finding("Sales team likely travels", u1, signal="direct_travel", obs="inferred")])})
    fake_llm(llm_result(text, [u1]))
    rs.run_standard_research(session, "P-033")
    assert "travel_potential" not in flag_types(latest_assessment(session, "P-033"))


def test_missing_public_info_is_insufficient_evidence_not_negative(session, fake_llm):
    fake_llm(llm_result(research_json({}), []))
    rs.run_standard_research(session, "P-033")
    a = latest_assessment(session, "P-033")
    f = flag(a, "insufficient_evidence")
    assert any("not evidence that the company does not travel" in u for u in f["uncertainty"])
    assert a.attention == "monitor"
    # Standard v4 covers 5 fields; the other 3 stay "Not searched", never "Not found".
    from app.research import prompts
    covered = set(prompts.standard_fields())
    assert all(v["status"] == "not_found" for f, v in a.coverage.items() if f in covered)
    assert all(v["status"] == "not_searched" for f, v in a.coverage.items() if f not in covered)


# --- Reviews -----------------------------------------------------------------------------

def _make_p007_proposal(session):
    add_synthetic_evidence(session, "P-007", "employee_count", "90 employees", 90, "descriptive", "t")
    return session.exec(select(TierProposal).where(TierProposal.prospect_id == "P-007")).one()


def test_reject_keeps_tier_and_suppresses_duplicate(session):
    p = _make_p007_proposal(session)
    with pytest.raises(ReviewError):
        decide(session, p.id, "reject", "Sam", "")  # comment required
    decide(session, p.id, "reject", "Sam", "Synthetic source; enrichment is credible")
    assert session.get(Prospect, "P-007").applied_tier == 2
    reassess(session, "P-007", trigger="manual")
    reassess(session, "P-007", trigger="manual")
    props = session.exec(select(TierProposal).where(TierProposal.prospect_id == "P-007")).all()
    assert len(props) == 1 and props[0].status == "rejected"
    a = latest_assessment(session, "P-007")
    assert a.accepted_values["suppressed_proposals"]
    assert flag(a, "tier_mismatch")["severity"] == "low"
    assert flag(a, "data_conflict")["severity"] == "moderate"
    assert a.attention == "review_suggested"


def test_approve_applies_tier_and_is_stable(session):
    p = _make_p007_proposal(session)
    decide(session, p.id, "approve", "Sam", "Checked")
    pr = session.get(Prospect, "P-007")
    assert pr.applied_tier == 3 and pr.original_tier == 2 and pr.applied_tier_source == f"proposal:{p.id}"
    a = latest_assessment(session, "P-007")
    # Approval records the accepted headcount, so rules agree and no reverse proposal appears.
    assert a.baseline["tier"] == 3 and a.accepted_values["employees"] == 90
    assert all(x.status != "open" for x in session.exec(select(TierProposal)).all())
    d = session.exec(select(ReviewDecision)).one()
    assert (d.tier_before, d.tier_after) == (2, 3)
    assert session.exec(select(AuditEvent).where(AuditEvent.action == "tier_changed")).one()
    with pytest.raises(ReviewError):
        decide(session, p.id, "approve", "Sam", "again")


def test_request_info_keeps_proposal_open(session):
    p = _make_p007_proposal(session)
    decide(session, p.id, "request_info", "Sam", "Need a verified headcount")
    assert session.get(TierProposal, p.id).status == "needs_info"
    assert session.get(Prospect, "P-007").applied_tier == 2
    reassess(session, "P-007", trigger="manual")
    assert session.get(TierProposal, p.id).status == "needs_info"
    assert latest_assessment(session, "P-007").attention == "review_now"


def test_reassess_does_not_duplicate_proposals(session):
    _make_p007_proposal(session)
    for _ in range(3):
        reassess(session, "P-007", trigger="manual")
    assert len(session.exec(select(TierProposal).where(TierProposal.prospect_id == "P-007")).all()) == 1


def test_reviewer_required(session):
    p = _make_p007_proposal(session)
    with pytest.raises(ReviewError):
        decide(session, p.id, "approve", " ", None)


# --- Day 30 ----------------------------------------------------------------------------

def test_day30_does_not_rewrite_day0(session):
    day0 = latest_assessment(session, "P-018")
    snapshot = (day0.id, day0.flags, day0.attention, day0.baseline)
    a = release_day30(session, "P-018")
    assert a.stage == "day30" and a.id != day0.id
    again = session.get(Assessment, day0.id)
    assert (again.id, again.flags, again.attention, again.baseline) == snapshot
    assert a.day30["compared_with_assessment_id"] == day0.id
    p = session.exec(select(TierProposal).where(TierProposal.prospect_id == "P-018")).one()
    assert (p.proposal_type, p.stage, p.proposed_tier) == ("evidence_override", "day30", 1)
    assert a.accepted_values["gbv_usd"] == 395000  # bookings never become GBV


def test_day30_not_used_before_release(session):
    a = latest_assessment(session, "P-009")
    assert a.stage == "day0" and a.day30 is None
    assert not session.exec(select(TierProposal).where(TierProposal.prospect_id == "P-009")).all()


def test_day30_release_is_idempotent(session):
    release_day30(session, "P-009")
    release_day30(session, "P-009")
    assert len(session.exec(select(TierProposal).where(TierProposal.prospect_id == "P-009")).all()) == 1


def test_day30_outcomes_on_all_rows(session):
    expected = {
        "P-002": ("review_suggested", None), "P-004": ("monitor", None), "P-007": ("review_suggested", None),
        "P-009": ("review_now", 1), "P-014": (None, None), "P-015": ("monitor", None),
        "P-018": ("review_now", 1), "P-021": (None, None), "P-025": (None, None), "P-028": ("review_now", 1),
    }
    for pid, (attention, tier) in expected.items():
        a = release_day30(session, pid)
        props = session.exec(select(TierProposal).where(TierProposal.prospect_id == pid,
                                                        TierProposal.status == "open")).all()
        assert a.attention == attention, pid
        assert (props[0].proposed_tier if props else None) == tier, pid


def test_approved_override_is_not_reverted_by_rules(session):
    release_day30(session, "P-009")
    p = session.exec(select(TierProposal).where(TierProposal.prospect_id == "P-009")).one()
    decide(session, p.id, "approve", "Sam", "Activity supports dedicated AE")
    reassess(session, "P-009", trigger="manual")
    assert session.get(Prospect, "P-009").applied_tier == 1
    assert len(session.exec(select(TierProposal).where(TierProposal.prospect_id == "P-009")).all()) == 1


# --- Regressions found by live-research error analysis --------------------------------

def test_disagreeing_research_headcounts_do_not_create_proposal(session, fake_llm):
    """Live P-025 run: aggregators said 219 / 90 / 152 (median 152) -> must not propose Tier 2."""
    u1, u2, u3 = "https://craft.co/x", "https://pitchbook.com/x", "https://rocketreach.co/x"
    text = research_json({"employee_count": ("found", [
        finding("Craft lists 219 employees", u1, value=219),
        finding("PitchBook lists 90 employees", u2, value=90),
        finding("RocketReach lists 152 employees", u3, value=152)])})
    fake_llm(llm_result(text, [u1, u2, u3]))
    rs.run_standard_research(session, "P-025")
    a = latest_assessment(session, "P-025")
    assert flag(a, "data_conflict")["severity"] == "material"
    assert not session.exec(select(TierProposal).where(TierProposal.prospect_id == "P-025")).all()
    assert a.accepted_values["deep_research"]["suggested"] is True


def test_travel_on_tier1_is_informational(session, fake_llm):
    """Live P-041/P-021 runs: Tier 1 accounts were sent to Review Suggested for travel evidence."""
    u1, u2 = "https://www.anthropic.com/careers/jobs", "https://builtin.com/company/anthropic/jobs"
    text = research_json({"travel_indicators": ("found", [
        finding("Roles marked Remote-Friendly (Travel-Required)", u1, signal="direct_travel"),
        finding("Role requires 25-50% travel to customer sites", u2, signal="direct_travel")])})
    fake_llm(llm_result(text, [u1, u2]))
    rs.run_standard_research(session, "P-041", prompt_version="v3")
    a = latest_assessment(session, "P-041")
    assert flag(a, "travel_potential")["severity"] == "low"
    assert a.attention == "monitor"


def test_job_board_search_page_is_aggregator():
    from app.research.evidence import classify_reliability

    assert classify_reliability("https://uk.indeed.com/q-bionical-solutions-jobs.html", "bionical.com") == "aggregator"
    assert classify_reliability("https://www.jobs.nhs.uk/candidate/jobadvert/E0393-24-0010", "bionical.com") == "secondary"


def test_local_field_travel_does_not_create_override(session, fake_llm):
    """Live P-025 deep research: community nurses driving to patients' homes were counted as
    business travel and produced a Tier 3 -> Tier 2 override. v3 labels travel scope."""
    u1, u2, u3 = "https://www.jobs.nhs.uk/a", "https://bebee.com/b", "https://jobs.example.com/c"
    def ft(claim, url, scope):
        f = finding(claim, url, signal="direct_travel")
        f["travel_scope"] = scope
        return f
    text = research_json({"travel_indicators": ("found", [
        ft("Community nurse role with car allowance and mileage", u1, "local_field_travel"),
        ft("Nurses travel to patients' homes", u2, "local_field_travel")])})
    fake_llm(llm_result(text, [u1, u2]))
    rs.run_standard_research(session, "P-033", prompt_version="v3")
    a = latest_assessment(session, "P-033")
    assert flag(a, "travel_potential")["severity"] == "low"
    assert not session.exec(select(TierProposal).where(TierProposal.prospect_id == "P-033")).all()
    # Business travel from two hosts still qualifies.
    text2 = research_json({"travel_indicators": ("found", [
        ft("Engineers travel to customer sites across Europe", u1, "business_travel"),
        ft("Sales role with 40% travel", u3, "unclear")])})
    fake_llm(llm_result(text2, [u1, u3]))
    rs.run_standard_research(session, "P-033", force=True, prompt_version="v3")
    a = latest_assessment(session, "P-033")
    assert flag(a, "travel_potential")["severity"] == "material"
    assert session.exec(select(TierProposal).where(TierProposal.prospect_id == "P-033")).one().proposed_tier == 2


def test_unknown_travel_scope_label_is_lenient():
    from app.research.schema import Finding

    assert Finding(claim="abc travel", source_url="https://x", travel_scope="regional").travel_scope == "unclear"


def test_recommendation_uses_most_severe_flag_of_each_type():
    """Live P-025: a low LLM conflict listed after a material headcount conflict hid the
    'confirm the employee count' recommendation."""
    from app.assessment.engine import recommend

    flags = [{"type": "data_conflict", "severity": "material"}, {"type": "travel_potential", "severity": "moderate"},
             {"type": "data_conflict", "severity": "low"}]
    assert recommend(flags, [], True, False, {}, None).startswith("Confirm the employee count")


def test_headcount_trend_only_compares_the_same_source(session, fake_llm):
    """Live P-025: PitchBook 90 (2026) vs Pomanda 422 (2026-09) was shown as +369% growth."""
    u1, u2 = "https://pitchbook.com/x", "https://pomanda.com/y"
    text = research_json({"employee_count": ("found", [
        finding("PitchBook lists 90 employees", u1, value=90, date="2026-01"),
        finding("Pomanda lists 422 employees", u2, value=422, date="2026-09")])})
    fake_llm(llm_result(text, [u1, u2]))
    rs.run_standard_research(session, "P-025")
    assert latest_assessment(session, "P-025").accepted_values["headcount_history"] == []



def test_standard_v4_covers_five_fields_and_deep_covers_all(session, fake_llm):
    from app.research import prompts

    assert prompts.standard_fields("v4") == ["industry_business_model", "geographic_footprint", "employee_count",
                                             "funding_financial", "hiring_trends"]
    _, _, user = prompts.build_standard_prompt("Acme", "acme.com", "v4")
    assert "travel_indicators:" not in user and "employee_count:" in user
    u = "https://news.example.com/a"
    text = research_json({"industry_business_model": ("found", [finding("Makes widgets", u)]),
                          "travel_indicators": ("found", [finding("Staff travel weekly", u, signal="direct_travel")])})
    fake_llm(llm_result(text, [u]))
    rs.run_standard_research(session, "P-033", prompt_version="v4")
    a = latest_assessment(session, "P-033")
    assert a.coverage["industry_business_model"]["status"] == "found"
    assert a.coverage["travel_indicators"]["status"] == "not_searched"  # out of scope: ignored, not "not found"
    assert "travel_potential" not in flag_types(a)
    plan = rs.deep_research_plan(session, "P-033")
    assert set(plan["focus"]) == set(prompts.RESEARCH_FIELDS)
    assert plan["focus"]["travel_indicators"] == "not covered by standard research"


def test_standard_rerun_keeps_evidence_for_fields_it_does_not_cover(session, fake_llm):
    u = "https://jobs.example.com/x"
    v3 = research_json({"travel_indicators": ("found", [finding("Engineers travel to client sites", u, signal="direct_travel")])})
    v4 = research_json({"industry_business_model": ("found", [finding("Makes widgets", u)])})
    fake_llm(llm_result(v3, [u]), llm_result(v4, [u]))
    rs.run_standard_research(session, "P-033", prompt_version="v3")
    rs.run_standard_research(session, "P-033", force=True, prompt_version="v4")
    travel = session.exec(select(Evidence).where(Evidence.prospect_id == "P-033", Evidence.field == "travel_indicators")).all()
    assert travel and all(e.superseded_by is None for e in travel)


def test_update_and_remove_day30_data(session):
    from app.postsignup import remove_day30, update_day30

    day0 = latest_assessment(session, "P-002")
    a = update_day30(session, "P-002", travelers=50, bookings=200, trend_pct=30, actor="Sam")
    assert a.stage == "day30" and a.day30["travelers"] == 50
    p = session.exec(select(TierProposal).where(TierProposal.prospect_id == "P-002", TierProposal.status == "open")).one()
    assert (p.from_tier, p.proposed_tier) == (3, 2)
    assert session.exec(select(AuditEvent).where(AuditEvent.action == "day30_activity_updated")).one()

    a2 = remove_day30(session, "P-002", actor="Sam")
    assert a2.stage == "day0" and a2.day30 is None
    assert session.get(TierProposal, p.id).status == "superseded"
    act = session.exec(select(PostSignupActivity).where(PostSignupActivity.prospect_id == "P-002")).one()
    assert act.released_at is None and act.travelers == 6  # back to the original file values
    assert session.get(Assessment, day0.id).stage == "day0"  # signup history untouched


def test_research_conflict_notes_do_not_stack_across_runs(session, fake_llm):
    """Live P-019: three runs each reported an employee-count conflict and the page showed three rows."""
    u = "https://a.example.com/x"
    def text(desc):
        return research_json({"employee_count": ("conflicting", [finding("Bands differ", u)])},
                             conflicts=[{"field": "employee_count", "description": desc, "source_urls": [u]}])
    fake_llm(llm_result(text("first"), [u]), llm_result(text("second"), [u]), llm_result(text("third"), [u]))
    rs.run_standard_research(session, "P-019")
    rs.run_standard_research(session, "P-019", force=True)
    rs.run_deep_research(session, "P-019")
    a = latest_assessment(session, "P-019")
    notes = [f for f in a.flags if f["type"] == "data_conflict" and "Research reported" in f["reasons"][0]]
    assert len(notes) == 1 and "third" in notes[0]["reasons"][0]
