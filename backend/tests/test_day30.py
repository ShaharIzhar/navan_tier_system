

def test_day30_rationale_names_threshold_and_trend_basis():
    from app.assessment.day30 import evaluate_day30
    d = evaluate_day30(20, 50, 59, 3, [], trend_basis="vs_previous", gbv=46000)
    why = " ".join(d["proposal"]["rationale"])
    assert "vs the previous summary" in why and "days 1–15" not in why
    assert "15+" in why and "$46K" in why
    d = evaluate_day30(20, 50, 30, 3, [])
    assert "days 16–30 vs days 1–15" in d["proposal"]["rationale"][0]


def test_day30_strong_activity_on_tier2_never_proposes_tier1():
    from app.assessment.day30 import evaluate_day30
    d = evaluate_day30(83, 318, 12, 2, [], gbv=460000)
    assert d["proposal"] is None
    assert [f["type"] for f in d["flags"]] == ["travel_potential"]
    assert "Tier 1 depends on reported GBV" in " ".join(d["flags"][0]["reasons"])


def test_import_puts_file_day30_note_in_remarks(tmp_path):
    from sqlmodel import Session, SQLModel, create_engine, select
    from app.importer import import_prospects
    from app.models import PostSignupActivity
    from app import config
    eng = create_engine(f"sqlite:///{tmp_path/'t.db'}")
    SQLModel.metadata.create_all(eng)
    with Session(eng) as s:
        import_prospects(s, config.CSV_PATH)
        a = s.exec(select(PostSignupActivity).where(PostSignupActivity.prospect_id == "P-002")).one()
        assert a.remarks == a.raw_text and "21 bookings" in a.remarks
