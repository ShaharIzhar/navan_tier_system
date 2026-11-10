# Developer guide

Notes for changing or extending the prototype. For running it, see the [README](../README.md).

## Changing a prompt

The app sends one live prompt per task. They are plain text files in `backend/prompts/` (`research.*`, `deep.*`, `judge.*`, `repair.user.txt`), described in `backend/prompts/manifest.json`.
1. Before editing, copy the current research prompt into `docs/llm_experiments/prompts/` as the next archived version (today's live prompt is archived there as `research_v4.*`).
2. Edit `backend/prompts/research.*.txt` and bump `research.version` in the manifest (e.g. `v5`). The version is stored on every run, and the cache is tied to it, so a new version triggers fresh research.
3. Run `cd backend && .venv/bin/python -m scripts.prompt_experiment --cases P-007 P-025` and compare `docs/llm_experiments/runs/v5/` with earlier versions.
4. Regenerate the prompt snapshot on purpose: `.venv/bin/python -m tests.golden_prompts > tests/fixtures/prompt_golden.json`. Until you do, `tests/test_prompt_refactor.py` fails on any prompt change, so nothing changes by accident.

Placeholders in `{braces}` are filled by code. Earlier versions (v1–v3) and why each changed: [`docs/llm_experiments/prompts/`](llm_experiments/prompts/README.md). `tests/test_prompts.py` checks they still reproduce the prompts sent in the saved experiments.

## Refreshing the demo recordings

Demo mode (no API key) replays `data/demo_snapshot.json`, then `backend/app/demo_seed.py` adds a little history once
(Day 30 activity for 5 companies and one approved proposal, labelled *Demo reviewer (seeded)*).

The exporter takes the latest successful run per company and kind for the demo set (`AUTO_RESEARCH_IDS` in
`config.py`), plus current-version AI summaries for open proposals:

```bash
cd backend && .venv/bin/python -m scripts.export_demo_snapshot
```

Some entries are pinned (`PINNED_RUNS`, `PINNED_JUDGES` in the script), and the exporter keeps them from the
existing snapshot. IMU Biosciences (P-007) and Moorside (P-033) keep their original 8 November standard recordings,
and IMU keeps its original AI summary, because the README walkthrough and `docs/cases.md` describe those runs. IMU's
Deep Research was recorded on top of that standard recording, so its context matches what the demo shows. After any refresh, run `pytest tests/test_replay.py`. It replays the whole snapshot on a fresh
database, checks the seed, and checks that every recorded AI summary passes the number check against the demo's own facts.

## Re-checking stored runs without a new AI call

`reprocess_run` in `backend/app/research/service.py` (and `backend/scripts/reprocess_runs.py`) re-validates saved
raw AI responses with the current rules, for example after a validation fix. It makes no AI call.
