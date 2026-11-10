# Navan Growth Intelligence

An internal tool that researches company travel potential, flags cases needing attention, and lets a salesperson review proposed support-tier changes.

**AI gathers evidence. Code applies rules. Humans approve tier changes.**

Company names and domains are real. GBV, signup employee estimates, tiers and Day 30 activity are **fictional exercise data**.

## Run locally

Requires Python 3.11+ and Node 20+. Run these from the repository root in two separate terminals:

```bash
# Terminal 1: backend
cd backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/uvicorn app.main:app --port 8000
```

```bash
# Terminal 2: frontend
cd frontend
npm install
npm run dev
```

Open **http://localhost:5173**.

**No API key needed for the demo.** A fresh database loads recorded real research for 16 companies, including the cases in the accompanying paper, plus example reviews and Day 30 activity. Recordings are labelled **Recorded** and pass through the same validation and rules as live research. Some recordings use earlier prompt versions; the paper's evaluation describes the assessments reviewed at that time.

**For live research:** copy `backend/.env.example` to `backend/.env`, set `ANTHROPIC_API_KEY`, then restart the backend. Live research uses Anthropic API credit. Existing demo data remains. Other settings are documented in `.env.example`.

## Try the demo

- **IMU Biosciences (P-007):** inspect conflicting headcounts and approve, reject or comment on the proposed downgrade.
- **Retail Merchant Services (P-026):** inspect a seeded approval and its decision history.
- **Quantum Motion (P-011):** edit employee count to 180; rules reassess immediately without an AI call. Tier changes still require approval.
- **Day 30:** use **Receive all Day 30 activity** to reassess remaining cases. Signup assessments stay in history; booking counts do not establish annual GBV.

Set your reviewer name in the top-right user menu. Decisions and evidence persist in SQLite.

## Tests

Run each command from the repository root in a separate terminal:

```bash
cd backend && .venv/bin/python -m pytest -q
```

```bash
cd frontend && npm test
```

## Submission and documentation

The accompanying **research and AI integration paper** covers the hypothesis, manual cases, prompt/output examples and initial evaluation.

- [Business rules and flowchart](docs/business_logic.md)
- [AI prompts](backend/prompts/) · [Experiments and refinement](docs/llm_experiments/README.md)
- [Evaluation framework](docs/evaluation.md) · [Research cases](docs/cases.md)
- [Developer guide](docs/developer_guide.md)

**Stack:** FastAPI, SQLModel/SQLite, React, TypeScript and Anthropic web search.
