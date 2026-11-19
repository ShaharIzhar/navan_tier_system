# Navan Growth Intelligence

Internal tool that checks whether a newly signed company is in the right support tier. AI researches the company; code checks the evidence and applies Navan's tier rules; a human approves any tier change.

## Run
- Backend: `cd backend && .venv/bin/uvicorn app.main:app --port 8000 --reload`
- Frontend: `cd frontend && npm run dev` (http://localhost:5173)
- With `ANTHROPIC_API_KEY` in `backend/.env` research is live and costs money. Without it, recorded runs replay (demo mode).

## Test
- Backend: `cd backend && .venv/bin/python -m pytest -q` (all must pass; ~6s)
- Frontend: `cd frontend && npm test` and `npm run build`

## Where things live
- `backend/app/rules/baseline.py`: official tier rules (deterministic)
- `backend/app/assessment/`: `engine.py` (`reassess()`), signals, flags, proposals, attention/priority, day30
- `backend/app/research/`: Claude client, research service, evidence checks, AI judge
- `backend/prompts/`: prompt text + `manifest.json` (bump the version when a prompt meaningfully changes)
- `backend/app/reviews/service.py`: approve / reject / request info / comment
- `backend/app/config.py`: all thresholds, including the tier cut-offs (`TIER1_GBV_MIN`, `TIER2_GBV_MIN`, `TIER2_EMPLOYEES_MIN`)
- `frontend/src/pages/`, `frontend/src/components/`, `frontend/src/api.ts`

## Rules
- The AI never sets or changes a tier. Tier cut-offs are defined only in `config.py`, and only `rules/baseline.py` turns them into a tier; never hardcode a cut-off anywhere else.
- Only human approval changes the applied tier.
- History is append-only: never delete or overwrite assessments, runs or evidence.
- Every AI citation must come from the search results of that run; keep the code checks.
- Any change to recalculation goes through `reassess()`.
- Every behaviour change gets a test. Never weaken a test to make it pass.

## Workflow
- Plan first; don't edit until the plan is agreed.
- Keep changes small and in scope; don't refactor unrelated code.
- Run the tests and show the result before saying it's done.
