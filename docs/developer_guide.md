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

Demo mode (no API key) replays `data/demo_snapshot.json`. After new live runs, export them with:

```bash
cd backend && .venv/bin/python -m scripts.export_demo_snapshot
```

## Re-checking stored runs without a new AI call

`reprocess_run` in `backend/app/research/service.py` (and `backend/scripts/reprocess_runs.py`) re-validates saved
raw AI responses with the current rules, for example after a validation fix. It makes no AI call.
