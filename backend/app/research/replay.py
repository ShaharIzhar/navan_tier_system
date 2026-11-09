"""Demo mode without an API key: replay RECORDED real Claude runs.

The recordings (data/demo_snapshot.json) contain the model's original raw text and the search
results the web-search tool actually returned. Replaying them runs the same validation, evidence
storage and rules as a live run. Every replayed run is labelled as recorded; nothing is generated.
"""
from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Optional

from .. import config
from .client import LLMResult, ResearchProviderError

SNAPSHOT_PATH = Path(config.REPO_DIR / "data" / "demo_snapshot.json")


@lru_cache(maxsize=4)
def _read(path: str) -> Optional[dict]:
    p = Path(path)
    if not p.exists():
        return None
    return json.loads(p.read_text())


def load_snapshot() -> Optional[dict]:
    return _read(str(SNAPSHOT_PATH))


def snapshot_available() -> bool:
    return load_snapshot() is not None


def recorded_run(domain: str, kind: str) -> Optional[dict]:
    snap = load_snapshot() or {}
    return next((r for r in snap.get("runs", []) if r["domain"] == domain and r["kind"] == kind), None)


def recorded_domains() -> list[str]:
    snap = load_snapshot() or {}
    return sorted({r["prospect_id"] for r in snap.get("runs", []) if r["kind"] == "standard"})


_DOMAIN = re.compile(r"Website domain:\s*(\S+)")
_COMPANY = re.compile(r'"company":\s*"([^"]+)"')
_TIERS = re.compile(r'"current_applied_tier":\s*(\d).*?"proposed_tier":\s*(\d)', re.S)


class ReplayClient:
    """Implements the LLMClient interface by returning recorded responses."""

    replayed = True
    model = "recorded"

    def complete(self, system: str, user: str, max_searches: Optional[int]) -> LLMResult:
        if '"proposed_tier"' in user and "current_applied_tier" in user:
            return self._judge(user)
        m = _DOMAIN.search(user)
        if not m:
            raise ResearchProviderError("Demo mode: no recording matches this request.")
        kind = "deep" if "focused follow-up research pass" in system else "standard"
        rec = recorded_run(m.group(1), kind)
        if rec is None:
            raise ResearchProviderError(
                f"No API key is configured and there is no recorded {kind} research for {m.group(1)}. "
                "Add ANTHROPIC_API_KEY to backend/.env to research this company live."
            )
        return LLMResult(
            text=rec["raw_text"], search_results=rec["search_results"], search_queries=rec["search_queries"],
            input_tokens=rec["input_tokens"], output_tokens=rec["output_tokens"],
            web_search_requests=rec["web_search_requests"], llm_calls=1, stop_reason="end_turn",
        )

    def _judge(self, user: str) -> LLMResult:
        snap = load_snapshot() or {}
        c, t = _COMPANY.search(user), _TIERS.search(user)
        for j in snap.get("judges", []):
            if c and t and j["company_name"] == c.group(1) and str(j["from_tier"]) == t.group(1) \
                    and str(j["proposed_tier"]) == t.group(2):
                return LLMResult(text=json.dumps(j["response"]), llm_calls=1)
        raise ResearchProviderError("No API key is configured and there is no recorded AI summary for this proposal.")


def provider_mode() -> str:
    if config.ANTHROPIC_API_KEY:
        return "live"
    if config.DEMO_REPLAY and snapshot_available():
        return "replay"
    return "off"
