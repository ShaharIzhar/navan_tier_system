from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from sqlmodel import Session

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import config  # noqa: E402
from app.db import get_engine, init_db  # noqa: E402
from app.research import service as research_service  # noqa: E402
from app.research.client import LLMResult, ResearchProviderError  # noqa: E402

CSV = Path(__file__).resolve().parents[2] / "data" / "prospects.csv"


@pytest.fixture()
def db_url(tmp_path):
    return f"sqlite:///{tmp_path / 'test.db'}"


@pytest.fixture()
def session(db_url, monkeypatch):
    monkeypatch.setattr(config, "CSV_PATH", CSV)
    monkeypatch.setattr(config, "DEMO_REPLAY", False)  # tests never depend on the recorded snapshot
    init_db(db_url)
    from app.main import bootstrap

    with Session(get_engine()) as s:
        bootstrap(s)
        yield s


class FakeClient:
    """Records calls; returns queued responses (LLMResult or Exception)."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def complete(self, system, user, max_searches):
        self.calls.append({"system": system, "user": user, "max_searches": max_searches})
        r = self.responses.pop(0)
        if isinstance(r, Exception):
            raise r
        return r


@pytest.fixture()
def fake_llm():
    holder = {}

    def install(*responses):
        client = FakeClient(responses)
        holder["client"] = client
        research_service.set_client_factory(lambda: client)
        return client

    yield install
    research_service.set_client_factory(lambda: (_ for _ in ()).throw(ResearchProviderError("no client")))


def finding(claim, url, *, value=None, signal="descriptive", obs="observed", date=None, title="Page"):
    return {"claim": claim, "value_number": value, "signal_type": signal, "observation": obs,
            "source_url": url, "source_title": title, "publisher": None, "published_date": date}


def research_json(fields: dict, conflicts=None, identity=True) -> str:
    """fields: {field_name: (status, [findings])}; unspecified fields -> not_found."""
    from app.research.schema import RESEARCH_FIELDS

    out = []
    for f in RESEARCH_FIELDS:
        status, findings = fields.get(f, ("not_found", []))
        out.append({"field": f, "status": status, "summary": f"{f} summary", "findings": findings})
    return json.dumps({"company_identity_confirmed": identity, "identity_note": "matched domain",
                       "fields": out, "conflicts": conflicts or [], "summary": "Test summary.",
                       "research_limitations": []})


def llm_result(text, urls=(), searches=2):
    return LLMResult(text=text, search_results=[{"url": u, "title": "t", "page_age": None} for u in urls],
                     input_tokens=1000, output_tokens=500, web_search_requests=searches, llm_calls=1)
