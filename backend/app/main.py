from __future__ import annotations

import logging
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import Session, select

from . import config
from .api.routes import router
from .assessment.engine import latest_assessment, reassess
from .db import get_engine, init_db
from .importer import import_prospects
from .models import Prospect

log = logging.getLogger("navan")


def bootstrap(session: Session) -> dict:
    """Import the CSV (idempotent) and give every prospect an initial rules-only assessment."""
    result = import_prospects(session, config.CSV_PATH)
    for p in session.exec(select(Prospect)).all():
        if latest_assessment(session, p.id) is None:
            reassess(session, p.id, trigger="import")
    return result


def _auto_research() -> None:
    from .research.service import run_standard_research

    with Session(get_engine()) as session:
        for pid in config.AUTO_RESEARCH_IDS:
            try:
                run_standard_research(session, pid, actor="system:auto")
            except Exception:  # keep going; failures are recorded on the run
                log.exception("auto research failed for %s", pid)


def _replay_recordings(session: Session) -> None:
    """Demo mode: replay recorded standard runs (then deep runs) for companies with no research yet."""
    from .models import ResearchRun
    from .research.replay import load_snapshot
    from .research.service import run_deep_research, run_standard_research

    snap = load_snapshot() or {}
    for kind in ("standard", "deep"):
        for rec in snap.get("runs", []):
            if rec["kind"] != kind:
                continue
            done = session.exec(select(ResearchRun).where(ResearchRun.prospect_id == rec["prospect_id"],
                                                          ResearchRun.kind == kind)).first()
            if done:
                continue
            if kind == "standard":
                run_standard_research(session, rec["prospect_id"], actor="system:demo-replay")
            else:
                run_deep_research(session, rec["prospect_id"], rec.get("focus_fields"), actor="system:demo-replay")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    with Session(get_engine()) as session:
        bootstrap(session)
        from .research.service import mark_interrupted_runs

        mark_interrupted_runs(session)
        from .research.replay import provider_mode

        if provider_mode() == "replay":
            _replay_recordings(session)
            from .demo_seed import seed_demo

            seed_demo(session)
    if config.AUTO_RESEARCH_ON_IMPORT and config.ANTHROPIC_API_KEY:
        threading.Thread(target=_auto_research, daemon=True).start()
    yield


app = FastAPI(title="Navan Growth Intelligence", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router)


@app.get("/api/health")
def health():
    return {"ok": True}
