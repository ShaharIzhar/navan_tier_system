"""The archived prompt versions (docs/llm_experiments/prompts) must still reproduce exactly what was sent in the
saved experiment runs, and the app must load only the live prompt."""
import json
from pathlib import Path

import pytest

from app.research import prompts
from app.research.schema import RESEARCH_FIELDS

DOCS = Path(__file__).resolve().parents[2] / "docs" / "llm_experiments"
ARCHIVE = DOCS / "prompts"
SHAPE = {"v1": "research_shape_v1.json", "v2": "research_shape_v1.json", "v3": "research_shape_v3.json"}
CASES = [("v1", "P-007-standard", "IMU Biosciences", "imubiosciences.com"),
         ("v2", "P-009-standard", "NexGen Cloud", "nexgencloud.com"),
         ("v2", "P-025-standard", "Bionical Solutions", "bionical.com"),
         ("v3", "P-009-standard", "NexGen Cloud", "nexgencloud.com"),
         ("v3", "P-025-standard", "Bionical Solutions", "bionical.com")]


def _archived_prompt(version: str, name: str, domain: str) -> tuple[str, str]:
    fields = "\n".join(f"- {k}: {d}" for k, d in RESEARCH_FIELDS.items())  # v1-v3 covered all 8 fields
    shape = json.dumps(json.loads((ARCHIVE / SHAPE[version]).read_text()), indent=2)
    user = (ARCHIVE / f"research_{version}.user.txt").read_text().format(
        company_name=name, domain=domain, fields=fields, shape=shape)
    return (ARCHIVE / f"research_{version}.system.txt").read_text(), user


@pytest.mark.parametrize("version,case,name,domain", CASES)
def test_archived_prompts_match_saved_runs(version, case, name, domain):
    saved = json.loads((DOCS / "runs" / version / f"{case}.json").read_text())
    system, user = _archived_prompt(version, name, domain)
    assert system == saved["system_prompt"]
    assert user == saved["user_prompt"]


def test_live_prompt_is_the_archived_v4():
    _, system, user = prompts.build_standard_prompt("Acme", "acme.com")
    assert system == (ARCHIVE / "research_v4.system.txt").read_text()
    assert (ARCHIVE / "research_v4.user.txt").read_text() == (prompts.PROMPTS_DIR / "research.user.txt").read_text()


def test_app_loads_only_the_live_prompt():
    names = {p.name for p in prompts.PROMPTS_DIR.iterdir()}
    assert not any(n.startswith("research_v") or "shape_v" in n for n in names), names
    assert "versions" not in prompts.manifest()["research"]
