"""Re-apply the current validation rules to each company's latest stored research (no AI call, $0).

Usage (from backend/): .venv/bin/python -m scripts.reprocess_runs
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlmodel import Session, select  # noqa: E402

from app.db import get_engine, init_db  # noqa: E402
from app.models import ResearchRun  # noqa: E402
from app.research.service import reprocess_run  # noqa: E402


def main() -> None:
    init_db()
    with Session(get_engine()) as s:
        latest: dict[tuple[str, str], ResearchRun] = {}
        for r in s.exec(select(ResearchRun).where(ResearchRun.status.in_(("ok", "partial"))).order_by(ResearchRun.id)):
            latest[(r.prospect_id, r.kind)] = r
        for kind in ("standard", "deep"):
            for (pid, k), r in sorted(latest.items()):
                if k == kind:
                    new = reprocess_run(s, r.id)
                    print(f"{pid} {kind}: run #{r.id} -> #{new.id} ({new.status}); "
                          f"{len(new.normalized_findings or [])} normalised finding(s)")


if __name__ == "__main__":
    main()
