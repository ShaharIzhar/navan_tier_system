

def test_day30_rationale_names_threshold_and_trend_basis():
    from app.assessment.day30 import evaluate_day30
    d = evaluate_day30(83, 318, 59, 2, [], trend_basis="vs_previous", gbv=460000)
    why = " ".join(d["proposal"]["rationale"])
    assert "vs the previous summary" in why and "days 1–15" not in why
    assert "40+" in why and "Tier 1-level" in why and "$460K" in why
    d = evaluate_day30(83, 318, 12, 2, [])
    assert "days 16–30 vs days 1–15" in d["proposal"]["rationale"][0]
