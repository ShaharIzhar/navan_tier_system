"""Prompts must stay byte-identical to what was actually sent in the saved experiment runs."""
import json
from pathlib import Path

import pytest

from app.research import prompts

EXP = Path(__file__).resolve().parents[2] / "docs" / "experiments"
CASES = [("v1", "P-007-standard", "IMU Biosciences", "imubiosciences.com"),
         ("v2", "P-009-standard", "NexGen Cloud", "nexgencloud.com"),
         ("v2", "P-025-standard", "Bionical Solutions", "bionical.com"),
         ("v3", "P-009-standard", "NexGen Cloud", "nexgencloud.com"),
         ("v3", "P-025-standard", "Bionical Solutions", "bionical.com")]


@pytest.mark.parametrize("version,case,name,domain", CASES)
def test_standard_prompts_match_saved_runs(version, case, name, domain):
    saved = json.loads((EXP / version / f"{case}.json").read_text())
    _, system, user = prompts.build_standard_prompt(name, domain, version)
    assert system == saved["system_prompt"]
    assert user == saved["user_prompt"]


def test_active_version_can_be_overridden(monkeypatch):
    monkeypatch.setenv("RESEARCH_PROMPT_VERSION", "v2")
    assert prompts.current_version() == "v2"
    assert prompts.build_standard_prompt("A", "a.com")[0] == "v2"
