"""Builds the exact prompts the live app sends. Used to prove prompt refactors change nothing.

Regenerate the fixture ONLY when a prompt change is intended:
    .venv/bin/python -m tests.golden_prompts > tests/fixtures/prompt_golden.json
"""
import json

from app.research import prompts

COMPANIES = [("IMU Biosciences", "imubiosciences.com"), ("NexGen Cloud", "nexgencloud.com"),
             ("Moorside Manufacturing", "moorside-manufacturing.co.uk")]
DEEP_FOCUS = {"employee_count": "conflicting", "travel_indicators": "not searched yet"}
DEEP_EXISTING = [{"field": "employee_count", "claim": "About 120 employees", "source_url": "https://x.example.com",
                  "published_date": "2026-01-01"}]
SIGNUP = "- Reported annual GBV: $48,000\n- Employee estimate from data provider (ZoomInfo): 155"


def snapshot() -> dict:
    out = {"standard": {}, "standard_fields": prompts.standard_fields()}
    for name, domain in COMPANIES:
        version, system, user = prompts.build_standard_prompt(name, domain)
        out["standard"][domain] = {"version": version, "system": system, "user": user}
    system, user = prompts.build_deep_prompt("IMU Biosciences", "imubiosciences.com", DEEP_FOCUS, DEEP_EXISTING, SIGNUP)
    out["deep"] = {"system": system, "user": user}
    jv, js, ju = prompts.judge_prompt(json.dumps({"company": "IMU", "proposed_tier": 3}, indent=1))
    out["judge"] = {"version": jv, "system": js, "user": ju}
    out["repair"] = prompts.repair_prompt("summary: Field required")
    return out


if __name__ == "__main__":
    print(json.dumps(snapshot(), indent=1, ensure_ascii=False))
