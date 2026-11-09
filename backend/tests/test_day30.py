

def test_day30_rationale_names_threshold_and_trend_basis():
    from app.assessment.day30 import evaluate_day30
    d = evaluate_day30(83, 318, 59, 2, [], trend_basis="vs_previous", gbv=460000)
    why = " ".join(d["proposal"]["rationale"])
    assert "vs the previous summary" in why and "days 1–15" not in why
    assert "40+" in why and "Tier 1-level" in why and "$460K" in why
    d = evaluate_day30(83, 318, 12, 2, [])
    assert "days 16–30 vs days 1–15" in d["proposal"]["rationale"][0]


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
