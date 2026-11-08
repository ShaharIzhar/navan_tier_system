import pytest

from app.importer import parse_activity, parse_gbv, read_csv
from app.models import PostSignupActivity, Prospect
from app.rules.baseline import calculate_baseline
from sqlmodel import select

from .conftest import CSV


@pytest.mark.parametrize(
    "gbv,emp,tier,provisional",
    [
        (500_000, None, 1, False),
        (499_999, None, 2, False),
        (100_000, None, 2, False),
        (99_999, 150, 2, False),
        (99_999, 149, 3, False),
        (99_999, None, 3, True),
        (0, 10, 3, False),
        (850_000, 1200, 1, False),
    ],
)
def test_tier_boundaries(gbv, emp, tier, provisional):
    r = calculate_baseline(gbv, emp)
    assert r.tier == tier
    assert r.provisional is provisional


def test_missing_employees_with_high_gbv_is_not_provisional():
    r = calculate_baseline(120_000, None)
    assert r.tier == 2 and not r.provisional


def test_invalid_gbv_is_not_treated_as_zero():
    assert calculate_baseline(None, 500).tier is None
    neg = calculate_baseline(-1, 10)
    assert neg.tier is None and neg.data_quality_issues


def test_parse_gbv():
    assert parse_gbv("$28,000") == (28000.0, None)
    assert parse_gbv("")[0] is None
    assert parse_gbv("abc")[0] is None and parse_gbv("abc")[1]


def test_parse_activity_handles_unicode_minus_and_flat():
    a = parse_activity("5 travelers; 19 bookings in the first 30 days after signup; bookings −22% in days 16–30 versus days 1–15.")
    assert (a.travelers, a.bookings, a.trend_pct, a.parse_ok) == (5, 19, -22.0, True)
    b = parse_activity("1 traveler; 4 bookings in the first 30 days after signup; bookings were flat in days 16–30 versus days 1–15.")
    assert (b.travelers, b.bookings, b.trend_pct) == (1, 4, 0.0)
    c = parse_activity("83 travelers; 318 bookings ...; bookings +12% in days 16–30")
    assert c.trend_pct == 12.0


def test_csv_headers_are_normalized():
    rows = read_csv(CSV)
    assert len(rows) == 43
    assert "current_tier" in rows[0] and "navan_travel_activity_30d_post_signup" in rows[0]


def test_import_counts_match_dataset(session):
    prospects = session.exec(select(Prospect)).all()
    assert len(prospects) == 43
    assert sum(1 for p in prospects if p.zi_employees is None) == 20
    acts = session.exec(select(PostSignupActivity)).all()
    assert len(acts) == 10 and all(a.parse_ok for a in acts)
    assert all(a.released_at is None for a in acts)  # Day 30 data not "received" at import


def test_priority_cases_match_csv(session):
    expected = {"P-002": (47000, 24, 3), "P-007": (48000, 155, 2), "P-009": (460000, 280, 2),
                "P-018": (395000, 42, 2), "P-030": (85000, 580, 2), "P-033": (7500, 11, 3)}
    for pid, (gbv, emp, tier) in expected.items():
        p = session.get(Prospect, pid)
        assert (p.entered_gbv_usd, p.zi_employees, p.original_tier) == (gbv, emp, tier)


def test_import_is_idempotent(session):
    from app import config
    from app.importer import import_prospects

    result = import_prospects(session, config.CSV_PATH)
    assert result["created"] == 0 and result["skipped_existing"] == 43


def test_every_dataset_tier_matches_baseline(session):
    """Documented finding: no standard-rule mismatches exist in the raw data."""
    from app.assessment.engine import latest_assessment

    for p in session.exec(select(Prospect)).all():
        assert latest_assessment(session, p.id).baseline["tier"] == p.original_tier
