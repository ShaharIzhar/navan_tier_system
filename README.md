# Navan Growth Intelligence

An internal tool that researches company travel potential, flags cases needing attention, and lets a salesperson review proposed support-tier changes.

Requires Python 3.11+ and Node 20+. Both options use two terminals and open at **http://localhost:5173**.

## Option 1: Demo (no API key)

```bash
git clone https://github.com/ShaharIzhar/navan_tier_system.git
cd navan_tier_system/backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/uvicorn app.main:app --port 8000
```

```bash
# second terminal, from the navan_tier_system folder
cd frontend
npm install
npm run dev
```

A fresh database loads recorded real research for 16 companies, plus example reviews and Day 30 activity. Recordings are labelled **Recorded** and go through the same validation and rules as live research. Some recordings use earlier prompt versions. **Demo mode** shows at the bottom of the sidebar.

## Option 2: Live research (with an Anthropic API key)

```bash
git clone https://github.com/ShaharIzhar/navan_tier_system.git
cd navan_tier_system/backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env            # then set ANTHROPIC_API_KEY=... in backend/.env
.venv/bin/uvicorn app.main:app --port 8000
```

```bash
# second terminal, from the navan_tier_system folder
cd frontend
npm install
npm run dev
```

Research then calls Claude Haiku with web search, which uses Anthropic API credit. If you ran the demo first, delete `backend/navan_growth.db` before starting to begin with a clean database. Other settings are in `backend/.env.example`.

## Tests

Run each command from the repository root in a separate terminal:

```bash
cd backend && .venv/bin/python -m pytest -q
```

```bash
cd frontend && npm test
```
