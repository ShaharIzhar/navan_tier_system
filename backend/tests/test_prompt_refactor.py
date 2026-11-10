"""Guards for the single-live-prompt refactor: what the app sends and stores must not change."""
import json
from pathlib import Path

from sqlmodel import select

from app.models import ResearchRun
from app.research import prompts
from app.research import service as rs
from app.research.schema import RESEARCH_FIELDS

from .conftest import finding, llm_result, research_json
from .golden_prompts import snapshot

GOLDEN = json.loads((Path(__file__).parent / "fixtures" / "prompt_golden.json").read_text(encoding="utf-8"))
FIVE = ["industry_business_model", "geographic_footprint", "employee_count", "funding_financial", "hiring_trends"]


def test_live_prompts_are_byte_for_byte_unchanged():
    now = snapshot()
    for key in ("standard", "standard_fields", "deep", "judge", "repair"):
        assert now[key] == GOLDEN[key], f"{key} prompt changed"


def test_standard_research_covers_the_five_basics():
    assert prompts.standard_fields() == FIVE


def test_old_run_labels_keep_their_field_scope():
    assert prompts.fields_for_run("v4") == FIVE
    for old in ("v1", "v2", "v3", "deep-v4", "something-else", None, ""):
        assert prompts.fields_for_run(old) == list(RESEARCH_FIELDS), old


def test_new_runs_keep_the_same_labels_and_cache(session, fake_llm):
    url = "https://x.example.com/a"
    text = research_json({"industry_business_model": ("found", [finding("Biotech", url)])})
    client = fake_llm(llm_result(text, [url]), llm_result(text, [url]))
    run = rs.run_standard_research(session, "P-007")
    assert run.prompt_version == "v4"
    again = rs.run_standard_research(session, "P-007")  # cached: no second AI call
    assert again.id == run.id and len(client.calls) == 1
    sent_system, sent_user = client.calls[0]["system"], client.calls[0]["user"]
    _, system, user = prompts.build_standard_prompt("IMU Biosciences", "imubiosciences.com")
    assert (sent_system, sent_user) == (system, user)


def test_deep_run_label_is_unchanged(session, fake_llm):
    url = "https://x.example.com/a"
    fake_llm(llm_result(research_json({"industry_business_model": ("found", [finding("Biotech", url)])}), [url]))
    rs.run_standard_research(session, "P-007")
    fake_llm(llm_result(research_json({"travel_indicators": ("not_found", [])}), [url]))
    rs.run_deep_research(session, "P-007")
    deep = session.exec(select(ResearchRun).where(ResearchRun.kind == "deep")).one()
    assert deep.prompt_version == "deep-v4"
