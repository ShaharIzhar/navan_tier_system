# Navan Growth Intelligence

**Author:** Shahar Izhar
**Submission for:** Navan, Full-Stack Software Engineer, Growth AI Solutions (home assignment)

An internal Growth tool that checks whether a newly signed-up company's support tier fits its business-travel potential, explains why, and lets a person decide what to do.

**AI gathers evidence. Code applies the rules. Humans approve tier changes.**

Company names and domains are real. All customer values (reported GBV, employee estimates, tiers and Day 30 activity) are **fictional scenario data** from the exercise, not real Navan customer information.

## Submission deliverables

This repository is one of three complementary deliverables:

1. **This repository and the working application.**
2. **A separate document** (submitted alongside this repository) covering external research, the hypothesis, manual company cases, AI prompts and output, missing and duplicate information, human review, and the evaluation framework.
3. **An Excalidraw flowchart** of the business logic. The repository copy is [`docs/business-logic.excalidraw`](docs/business-logic.excalidraw) (open it at [excalidraw.com](https://excalidraw.com), menu → Open). A text (Mermaid) version is at the top of [`docs/business_logic.md`](docs/business_logic.md).

## What a salesperson sees

- **Review queue:** companies grouped into Review Now, Review Suggested and Monitor, most important first.
- **Company page:** the values the tier rules use next to what research found, the flags and their reasons, sources, Day 30 activity, and any suggested tier change.
- **Tier review:** a pull-request-style page with an AI summary (advisory only), the evidence and caveats, and Approve / Reject / Comment. Every decision is logged with the reviewer's name.

## Quick start

Requirements: Python 3.11+ and Node 20+.

```bash
# 1. Backend
cd backend
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
cp .env.example .env          # optional: add ANTHROPIC_API_KEY for live research
.venv/bin/uvicorn app.main:app --port 8000

# 2. Frontend (new terminal)
cd frontend
npm install
npm run dev                    # http://localhost:5173
```

On first start the backend imports `data/prospects.csv` and gives every company a rules-only assessment. Set your name in the user menu (top right); it is recorded in the audit trail.

### Demo mode (no API key)

Without `ANTHROPIC_API_KEY`, the backend replays **recorded real Claude runs** from `data/demo_snapshot.json` for 10 companies (P-002, P-007, P-009, P-018, P-019, P-021, P-025, P-030, P-033, P-041) and one recorded AI summary.
- The recordings were made with the earlier v3 research prompt (all 8 fields in standard research), so replayed standard research can show travel findings that live v4 research leaves to Deep Research.
- Replays go through the same validation, evidence storage and rules as live research.
- Replayed items are labelled **Recorded** and a banner shows that demo mode is on.
- Other companies show an error if you click research; add a key to research them live.

### Configuration

Set in `backend/.env` (see `backend/.env.example`):

| Variable | Default | Effect |
|---|---|---|
| `ANTHROPIC_API_KEY` | empty | Enables live research (Claude Haiku 5.5 with web search) |
| `DEMO_REPLAY` | `true` | Replays recordings when there is no key |
| `AUTO_RESEARCH_ON_IMPORT` | `false` | With a key, researches the 10 demo companies on start |
| `RESEARCH_MODEL` | `claude-haiku-5-5` | Research model |

Policy thresholds live in `backend/app/config.py`.

### Tests

```bash
cd backend && .venv/bin/python -m pytest -q
cd frontend && npm test
```

## A short walkthrough

These steps work in demo mode on a fresh database.

1. **Conflicting headcount (IMU Biosciences, P-007).** It is Tier 2 only because the enrichment says 155 employees (GBV $48K). Research finds 25 (PitchBook) and 53 (Built In), plus an 11–50 LinkedIn band. The figures straddle 150, so the system raises a material Data Conflict and proposes Tier 2 → Tier 3. Open the review and approve or reject it.
2. **Manual value, no AI (Quantum Motion, P-011).** Headcount is missing, so it is a provisional Tier 3. Edit Employees to 180: the rules rerun with 0 AI calls and propose Tier 3 → Tier 2. The applied tier changes only if someone approves.
3. **Day 30 activity.** On *All companies*, click **Receive all Day 30 activity**. Strong activity on Tier 2 companies (for example NexGen Cloud, Puttshack) shows as Travel Potential (Review Suggested). It never proposes Tier 1. The Day 0 assessment stays unchanged in each company's history.
4. **Restart the backend.** Decisions, evidence and audit events persist (SQLite).

## How it works (overview)

1. **Baseline tier (assignment rules):** Tier 1 at GBV ≥ $500K; Tier 2 at GBV ≥ $100K or 150+ employees; otherwise Tier 3. Missing headcount with GBV under $100K gives a *provisional* Tier 3; invalid GBV gives no tier.
2. **Research (AI):** Claude Haiku 5.5 with web search, given only the company name and domain. Standard research covers 5 routing basics; Deep Research (on request) covers all 8 fields, including travel requirements. Code validates the output: schema, citations must come from that run's search results, headcount bands are not treated as exact numbers, and stale or future-dated evidence is marked or dropped.
3. **Flags and attention (prototype policy):** code turns validated evidence into flags (Tier Mismatch, Data Conflict, Growth Opportunity, Travel Potential, Insufficient Evidence) and an attention level.
4. **Human review:** only a Tier Mismatch creates a tier proposal. Nothing changes until a person approves it.
5. **Day 30 (prototype policy):** received activity triggers a rules-only reassessment. It can suggest at most Tier 3 → Tier 2, and never Tier 1, because booking counts are not dollars.

Detailed rules: [`docs/business_logic.md`](docs/business_logic.md).

## AI prompts

All prompts are plain text files in [`backend/prompts/`](backend/prompts/). There is one live prompt per task, and none of them is shown in the UI. Code fills the `{placeholders}`; the AI never sees reported GBV or Day 30 data during research.

| Task | Files | When it runs | What it gets | What it returns |
|---|---|---|---|---|
| Standard research (v4) | `research.system.txt`, `research.user.txt` | When someone clicks it (or for the 10 demo companies on start, if `AUTO_RESEARCH_ON_IMPORT` is on) | Company name and domain | Findings with sources for 5 routing fields: industry, locations, employees, funding, hiring |
| Deep Research | `deep.system.txt`, `deep.user.txt` | Only on request, after a confirmation | Name, domain, signup inputs, what is already known | Findings for all 8 fields, including travel requirements, with gaps and conflicts explained |
| JSON repair | `repair.user.txt` | Once, if the AI's answer fails validation | The validation error | The same answer as valid JSON |
| AI summary (judge-v4) | `judge.system.txt`, `judge.user.txt` | When a tier review page opens (cached) | The proposal's facts | One-sentence reason, support level, main doubt (advisory only) |

`research_shape.json` is the JSON shape both research prompts must return, and `manifest.json` records each prompt's version label and placeholders. Editing a `.txt` file takes effect on the next AI call; see [`docs/developer_guide.md`](docs/developer_guide.md).

### How the research prompt was refined

The research prompt was refined on real runs, and each fix also got a code-level check:
- **v1 → v2:** headcount ranges were stored as exact numbers, travel requirements were never found (0 of 3 runs), and normal database differences were reported as conflicts. v2 added a search plan and conflict rules, plus two deterministic guards.
- **v3:** running the full app on 10 companies exposed more errors, the main one being community-nurse home visits counted as business travel. v3 labels travel as business, local field or unclear, and local travel can't drive a tier change.
- **v4 (live):** standard research narrowed to 5 fields to control cost; travel moved to Deep Research.

Full history with raw outputs and the earlier prompt versions: [`docs/llm_experiments/`](docs/llm_experiments/README.md).

## Assumptions and limitations

- **Prototype policies are not calibrated.** Only the tier thresholds come from the assignment. Flag conditions, attention levels, staleness (18 months) and Day 30 thresholds are hypotheses with no outcome data behind them.
- **Annual GBV cannot be inferred from booking counts.** 30 days of activity may not represent a year.
- **Public sources are uncertain.** Headcounts often come from aggregator estimates, small private companies may have almost no public data, and "not found" never means "doesn't travel". Company identity is not independently verified.
- **Signup cutoff = research run time**, because the dataset has no signup dates. Day 30 data is "received" by a button to simulate its arrival.
- **Standard research doesn't search for travel.** Travel requirements are only found by Deep Research.
- **No authentication.** The name in the user menu is used only for the audit trail.
- **Prototype only.** Tier changes apply inside this app, not to Navan's routing.
- **No Reports page yet.** The data is available from `GET /api/reports`.

Testing done so far is automated (unit, API and scenario tests) plus the recorded live runs above. No accuracy figure is claimed: the dataset is fictional and unlabelled. How false positives, false negatives and unsupported actions would be measured is in [`docs/evaluation.md`](docs/evaluation.md).

## Project structure

```
backend/
  app/            FastAPI app: rules/, research/ (AI client, validation), assessment/ (flags,
                  attention, proposals, Day 30), reviews/, enrichment.py, api/routes.py
  prompts/        the live AI prompts as plain text files
  tests/          pytest
  scripts/        prompt experiments, demo snapshot export, reprocessing stored runs
frontend/src/     React + TypeScript (Vite) pages and components, Vitest smoke tests
data/             prospects.csv (fictional scenario data), demo_snapshot.json (recorded runs)
docs/             rules and flowchart, cases, evaluation, LLM experiments (see docs/README.md)
```

Stack: FastAPI, SQLModel/SQLite, Pydantic, the Anthropic Python SDK, React + TypeScript (Vite), pytest, Vitest + Testing Library.

## Documentation

- [`docs/business_logic.md`](docs/business_logic.md): flowchart (text version) and detailed rules, validation checks, flags, proposals, Day 30, assumptions
- [`docs/business-logic.excalidraw`](docs/business-logic.excalidraw): the submitted flowchart
- [`docs/cases.md`](docs/cases.md): live-research results on the demo companies, with sources, and Day 30 results
- [`docs/llm_experiments/`](docs/llm_experiments/README.md): prompt testing and refinement, raw AI outputs, earlier prompt versions
- [`docs/evaluation.md`](docs/evaluation.md): evaluation framework
- [`docs/developer_guide.md`](docs/developer_guide.md): changing a prompt, refreshing demo recordings

## AI tools used

- **NotebookLM and ChatGPT:** product research, understanding the problem, and PRD work.
- **Claude Code:** implementation and tests. It also drafted the repository documentation and ran the recorded LLM experiments.
- **Claude Haiku 5.5 with web search:** company research inside the application (raw outputs in `docs/llm_experiments/runs/`).
- **Codex:** flowchart creation, document writing and review, and evaluation discussions.

I set the product decisions and reviewed the output. Checks described in this repository were run by the code, tests or AI tools named above, not repeated manually unless stated.
