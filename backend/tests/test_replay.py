"""Demo mode without an API key: recorded real runs are replayed through the normal pipeline."""
import json

from sqlmodel import select

from app import config
from app.assessment.engine import latest_assessment
from app.models import Evidence
from app.research import replay
from app.research import service as rs

from .conftest import finding, research_json


def _snapshot(tmp_path, monkeypatch):
    url = "https://www.example-news.com/imu"
    snap = {"runs": [{
        "prospect_id": "P-007", "domain": "imubiosciences.com", "company_name": "IMU Biosciences", "kind": "standard",
        "prompt_version": "v3", "model": "claude-haiku-5-5", "focus_fields": None,
        "research_cutoff": "2026-11-08T18:49:00+00:00", "recorded_at": "2026-11-08T18:49:30+00:00",
        "raw_text": research_json({"employee_count": ("found", [finding("PitchBook lists 25 employees", url, value=25)])}),
        "search_results": [{"url": url, "title": "t", "page_age": None}], "search_queries": ["IMU Biosciences"],
        "input_tokens": 1000, "output_tokens": 200, "web_search_requests": 1,
    }], "judges": []}
    path = tmp_path / "snap.json"
    path.write_text(json.dumps(snap))
    monkeypatch.setattr(replay, "SNAPSHOT_PATH", path)
    monkeypatch.setattr(config, "ANTHROPIC_API_KEY", "")
    monkeypatch.setattr(config, "DEMO_REPLAY", True)
    rs.set_client_factory(rs._default_client)


def test_replay_runs_the_normal_pipeline_and_is_labelled(session, tmp_path, monkeypatch):
    _snapshot(tmp_path, monkeypatch)
    assert replay.provider_mode() == "replay"
    run = rs.run_standard_research(session, "P-007")
    assert run.status == "ok" and run.replayed and "(recorded)" in run.model
    assert run.prompt_version == "v3" and run.research_cutoff.year == 2026
    ev = session.exec(select(Evidence).where(Evidence.run_id == run.id)).one()
    assert ev.value_number == 25 and ev.reliability == "secondary"
    a = latest_assessment(session, "P-007")
    assert {f["type"] for f in a.flags} >= {"data_conflict"}  # same rules as a live run


def test_replay_without_recording_fails_clearly(session, tmp_path, monkeypatch):
    _snapshot(tmp_path, monkeypatch)
    run = rs.run_standard_research(session, "P-033")
    assert run.status == "failed" and "no recorded" in run.error and "ANTHROPIC_API_KEY" in run.error
    assert not session.exec(select(Evidence).where(Evidence.prospect_id == "P-033")).all()


def test_no_key_and_no_snapshot_is_off(monkeypatch, tmp_path):
    monkeypatch.setattr(replay, "SNAPSHOT_PATH", tmp_path / "missing.json")
    monkeypatch.setattr(config, "ANTHROPIC_API_KEY", "")
    assert replay.provider_mode() == "off"


def test_committed_snapshot_is_valid_and_has_no_secrets():
    raw = replay.SNAPSHOT_PATH.read_text()
    assert "sk-ant" not in raw
    snap = json.loads(raw)
    from app.research.evidence import parse_research_output

    for r in snap["runs"]:
        parse_research_output(r["raw_text"])  # every recording still parses with the current schema
        assert r["search_results"], r["prospect_id"]
