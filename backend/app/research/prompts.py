"""Prompt loader.

All prompt text lives in plain files under backend/prompts/ (see prompts/manifest.json), so prompts
can be read and updated without touching Python. Files are read on every call: an edit applies on
the next AI call, no restart needed.

There is one live prompt per task. Its label (manifest "version", e.g. "v4") is stored on every
research run for caching and history. Earlier versions are archived in docs/experiments/prompts/
and are never loaded by the app.
"""
from __future__ import annotations

import json
from pathlib import Path

from .schema import RESEARCH_FIELDS

PROMPTS_DIR = Path(__file__).resolve().parents[2] / "prompts"


def manifest() -> dict:
    return json.loads((PROMPTS_DIR / "manifest.json").read_text(encoding="utf-8"))


def read(name: str) -> str:
    return (PROMPTS_DIR / name).read_text(encoding="utf-8")


def _shape(name: str) -> str:
    # Re-serialise exactly as the original code did (indent=2, ASCII escapes).
    return json.dumps(json.loads(read(name)), indent=2)


def current_version() -> str:
    """Label of the live research prompt, stored on each run."""
    return manifest()["research"]["version"]


def standard_fields() -> list[str]:
    """Fields the live standard-research prompt covers."""
    return manifest()["research"].get("fields") or list(RESEARCH_FIELDS)


def fields_for_run(label: str | None) -> list[str]:
    """Fields a stored standard run covered. Runs from earlier prompt versions covered all 8."""
    return standard_fields() if label == current_version() else list(RESEARCH_FIELDS)


def _field_list(fields: list[str]) -> str:
    return "\n".join(f"- {k}: {RESEARCH_FIELDS[k]}" for k in fields)


def build_standard_prompt(company_name: str, domain: str) -> tuple[str, str, str]:
    """Return (version, system, user). Only Day 0 inputs are allowed here: name + domain."""
    spec = manifest()["research"]
    user = read(spec["user"]).format(company_name=company_name, domain=domain, fields=_field_list(standard_fields()),
                                     shape=_shape(spec["shape"]))
    return current_version(), read(spec["system"]), user


def build_deep_prompt(company_name: str, domain: str, focus: dict[str, str], existing: list[dict],
                      signup: str = "(not provided)") -> tuple[str, str]:
    spec = manifest()["deep"]
    focus_txt = "\n".join(f"- {f} ({RESEARCH_FIELDS.get(f, f)}): {why}" for f, why in focus.items())
    existing_txt = json.dumps(existing, indent=1)[:12000] if existing else "(none)"
    user = read(spec["user"]).format(company_name=company_name, domain=domain, signup=signup, focus=focus_txt,
                                     existing=existing_txt, shape=_shape(spec["shape"]))
    return read(spec["system"]), user


def repair_prompt(error: str) -> str:
    return read(manifest()["repair"]["user"]).format(error=error)


def judge_prompt(facts_json: str) -> tuple[str, str, str]:
    """Return (version, system, user) for the AI judge."""
    spec = manifest()["judge"]
    return spec["version"], read(spec["system"]), read(spec["user"]).format(facts=facts_json)
