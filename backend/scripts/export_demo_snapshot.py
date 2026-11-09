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
from app.models import Prospect, ResearchRun, TierProposal  # noqa: E402

OUT = config.REPO_DIR / "data" / "demo_snapshot.json"


def main() -> None:
    init_db()
    with Session(get_engine()) as s:
        latest: dict[tuple[str, str], ResearchRun] = {}
        for r in s.exec(select(ResearchRun).where(ResearchRun.status.in_(("ok", "partial"))).order_by(ResearchRun.id)):
            if "--- repair attempt ---" in (r.raw_text or ""):
                continue  # keep the snapshot to single-call runs
            latest[(r.prospect_id, r.kind)] = r
        runs = []
        for (pid, kind), r in sorted(latest.items()):
            p = s.get(Prospect, pid)
            runs.append({
                "prospect_id": pid, "domain": p.domain, "company_name": p.company_name, "kind": kind,
                "prompt_version": r.prompt_version, "model": r.model, "focus_fields": r.focus_fields,
                "research_cutoff": r.research_cutoff.isoformat(), "recorded_at": (r.finished_at or r.started_at).isoformat(),
                "raw_text": r.raw_text, "search_results": r.searched_results or [], "search_queries": r.search_queries or [],
                "input_tokens": r.input_tokens, "output_tokens": r.output_tokens,
                "web_search_requests": r.web_search_requests,
            })
        judges = []
        for tp in s.exec(select(TierProposal)):
            j = tp.judge or {}
            if j.get("status") == "ok":
                p = s.get(Prospect, tp.prospect_id)
                judges.append({"prospect_id": tp.prospect_id, "company_name": p.company_name, "from_tier": tp.from_tier,
                               "proposed_tier": tp.proposed_tier, "prompt_version": j.get("prompt_version"),
                               "recorded_at": j.get("created_at"),
                               "response": {k: j[k] for k in ("summary", "support", "main_doubt")}})
    OUT.write_text(json.dumps({"description": "Recorded real Claude runs for the no-API-key demo mode. Not live research.",
                               "runs": runs, "judges": judges}, indent=1, ensure_ascii=False))
    print(f"wrote {OUT.relative_to(config.REPO_DIR)}: {len(runs)} runs, {len(judges)} judge summaries")


if __name__ == "__main__":
    main()
