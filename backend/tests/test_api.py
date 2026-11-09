from fastapi.testclient import TestClient

from app.db import init_db
from app.main import app


def test_end_to_end_review_persists_across_restart(session, db_url):
    with TestClient(app) as c:
        rows = c.get("/api/prospects").json()
        assert len(rows) == 43
        r = c.post("/api/prospects/P-007/synthetic-evidence",
                   json={"field": "employee_count", "claim": "90 employees", "value_number": 90})
        assert r.status_code == 200
        detail = c.get("/api/prospects/P-007").json()
        assert detail["assessment"]["attention_label"] == "Review Now"
        pid = detail["proposals"][0]["id"]
        bad = c.post(f"/api/proposals/{pid}/decision", json={"action": "reject", "reviewer": "Sam"})
        assert bad.status_code == 400
        ok = c.post(f"/api/proposals/{pid}/decision",
                    json={"action": "reject", "reviewer": "Sam", "comment": "Synthetic source"})
        assert ok.json()["status"] == "rejected"

    # Simulate a restart: new engine + new app lifespan on the same SQLite file.
    init_db(db_url)
    with TestClient(app) as c:
        prop = c.get(f"/api/proposals/{pid}").json()
        assert prop["proposal"]["status"] == "rejected"
        assert prop["decisions"][0]["comment"] == "Synthetic source"
        assert any(e["action"] == "review_reject" for e in prop["audit"])
        assert c.get("/api/prospects/P-007").json()["prospect"]["applied_tier"] == 2


def test_enrichment_endpoint_reports_before_after(session):
    with TestClient(app) as c:
        r = c.post("/api/prospects/P-011/enrichment",
                   json={"param": "employee_count", "value": "200", "entered_by": "Dana"}).json()
        assert r["llm_calls"] == 0
        assert r["before"]["baseline"]["tier"] == 3 and r["after"]["baseline"]["tier"] == 2
        assert c.post("/api/prospects/P-011/enrichment",
                      json={"param": "employee_count", "value": "x", "entered_by": "Dana"}).status_code == 400


def test_reports_and_scenario_checks(session):
    with TestClient(app) as c:
        c.post("/api/day30/release-all")
        rep = c.get("/api/reports").json()
        assert rep["totals"]["prospects"] == 43 and rep["totals"]["day30_received"] == 10
        assert all(x["passed"] for x in rep["scenario_checks"]), [x for x in rep["scenario_checks"] if not x["passed"]]
        assert len(rep["retrospective_day30"]) == 10
        assert rep["missing_data"]["employee_estimate_missing"] == 20


def test_day30_details_hidden_until_received(session):
    with TestClient(app) as c:
        d = c.get("/api/prospects/P-002").json()
        assert d["day30"]["received"] is False and "travelers" not in d["day30"]
        assert d["day30_pending"] is True
        c.post("/api/prospects/P-002/day30/release")
        d = c.get("/api/prospects/P-002").json()
        assert d["day30"]["travelers"] == 6 and d["assessment"]["stage"] == "day30"
