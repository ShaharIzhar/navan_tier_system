"""Prompt loader.

All prompt text lives in plain files under backend/prompts/ (see prompts/manifest.json), so prompts
can be read and updated without touching Python. Files are read on every call: an edit applies on
the next AI call, no restart needed.

Rule of thumb: never edit a version that has been run. Add a new version file, register it in the
manifest and set "active" (or set RESEARCH_PROMPT_VERSION in backend/.env). Old versions stay
reproducible; tests/test_prompts.py checks they still match the prompts sent in saved experiments.
"""
from __future__ import annotations

import json
import os
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
    return os.getenv("RESEARCH_PROMPT_VERSION") or manifest()["research"]["active"]


def research_versions() -> list[str]:
    return list(manifest()["research"]["versions"])


def standard_fields(version: str | None = None) -> list[str]:
    """Fields a standard-research prompt version covers (all 8 unless the manifest narrows it)."""
    spec = manifest()["research"]["versions"][version or current_version()]
    return spec.get("fields") or list(RESEARCH_FIELDS)


def _field_list(fields: list[str]) -> str:
    return "\n".join(f"- {k}: {RESEARCH_FIELDS[k]}" for k in fields)


def build_standard_prompt(company_name: str, domain: str, version: str | None = None) -> tuple[str, str, str]:
    """Return (version, system, user). Only Day 0 inputs are allowed here: name + domain."""
    v = version or current_version()
    spec = manifest()["research"]["versions"][v]
    user = read(spec["user"]).format(company_name=company_name, domain=domain, fields=_field_list(standard_fields(v)),
                                     shape=_shape(spec["shape"]))
    return v, read(spec["system"]), user


def build_deep_prompt(company_name: str, domain: str, focus: dict[str, str], existing: list[dict]) -> tuple[str, str]:
    spec = manifest()["deep"]
    focus_txt = "\n".join(f"- {f} ({RESEARCH_FIELDS.get(f, f)}): {why}" for f, why in focus.items())
    existing_txt = json.dumps(existing, indent=1)[:12000] if existing else "(none)"
    user = read(spec["user"]).format(company_name=company_name, domain=domain, focus=focus_txt,
                                     existing=existing_txt, shape=_shape(spec["shape"]))
    return read(spec["system"]), user


def repair_prompt(error: str) -> str:
    return read(manifest()["repair"]["user"]).format(error=error)


def judge_prompt(facts_json: str) -> tuple[str, str, str]:
    """Return (version, system, user) for the AI judge."""
    spec = manifest()["judge"]
    return spec["version"], read(spec["system"]), read(spec["user"]).format(facts=facts_json)
