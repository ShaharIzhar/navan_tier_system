"""Export recorded real research runs (and AI judge summaries) for the no-API-key demo mode.

Usage (from backend/): .venv/bin/python -m scripts.export_demo_snapshot
Writes data/demo_snapshot.json. Only successful runs are exported, unedited: the model's raw text,
the search results the tool actually returned, the queries, usage and the original research cutoff.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlmodel import Session, select  # noqa: E402

from app import config  # noqa: E402
from app.db import get_engine, init_db  # noqa: E402
from app.models import Prospect, TierProposal  # noqa: E402
from app.research import prompts  # noqa: E402
from scripts._runs import latest_successful_runs  # noqa: E402

OUT = config.REPO_DIR / "data" / "demo_snapshot.json"

# Kept from the existing snapshot instead of the latest run: the README walkthrough and docs/cases.md
# describe these 8 November recordings (later reruns of IMU found fewer headcount figures). IMU's Deep Research
# was recorded separately, on top of that standard recording, so its context matches the demo.
PINNED_RUNS = {("P-007", "standard"), ("P-007", "deep"), ("P-033", "standard")}
PINNED_JUDGES = {"P-007"}


def run_record(p: Prospect, r) -> dict:
    """One recorded run, unedited, in the snapshot format."""
    return {
        "prospect_id": p.id, "domain": p.domain, "company_name": p.company_name, "kind": r.kind,
        "prompt_version": r.prompt_version, "model": r.model, "focus_fields": r.focus_fields,
        "research_cutoff": r.research_cutoff.isoformat(), "recorded_at": (r.finished_at or r.started_at).isoformat(),
        "raw_text": r.raw_text, "search_results": r.searched_results or [], "search_queries": r.search_queries or [],
        "input_tokens": r.input_tokens, "output_tokens": r.output_tokens,
        "web_search_requests": r.web_search_requests,
    }


def main() -> None:
    previous = json.loads(OUT.read_text()) if OUT.exists() else {"runs": [], "judges": []}
    pinned_runs = {(r["prospect_id"], r["kind"]): r for r in previous["runs"] if (r["prospect_id"], r["kind"]) in PINNED_RUNS}
    pinned_judges = [j for j in previous["judges"] if j["prospect_id"] in PINNED_JUDGES]
    init_db()
    with Session(get_engine()) as s:
        latest = latest_successful_runs(s, skip_repaired=True)  # keep the snapshot to single-call runs
        runs = []
        for (pid, kind), r in sorted(latest.items()):
            if pid not in config.AUTO_RESEARCH_IDS:
                continue  # the demo set only
            if (pid, kind) in pinned_runs:
                continue
            runs.append(run_record(s.get(Prospect, pid), r))
        judges = []
        for tp in s.exec(select(TierProposal)):
            j = tp.judge or {}
            # Only current-version summaries for open demo proposals.
            if tp.prospect_id in PINNED_JUDGES:
                continue
            if (j.get("status") == "ok" and tp.prospect_id in config.AUTO_RESEARCH_IDS and tp.status == "open"
                    and j.get("prompt_version") == prompts.manifest()["judge"]["version"]):
                p = s.get(Prospect, tp.prospect_id)
                judges.append({"prospect_id": tp.prospect_id, "company_name": p.company_name, "from_tier": tp.from_tier,
                               "proposed_tier": tp.proposed_tier, "prompt_version": j.get("prompt_version"),
                               "recorded_at": j.get("created_at"),
                               "response": {k: j[k] for k in ("summary", "support", "main_doubt")}})
    runs = sorted(runs + list(pinned_runs.values()), key=lambda x: (x["prospect_id"], x["kind"]))
    judges = pinned_judges + judges
    OUT.write_text(json.dumps({"description": "Recorded real Claude runs for the no-API-key demo mode. Not live research.",
                               "runs": runs, "judges": judges}, indent=1, ensure_ascii=False))
    print(f"wrote {OUT.relative_to(config.REPO_DIR)}: {len(runs)} runs, {len(judges)} judge summaries")


if __name__ == "__main__":
    main()
