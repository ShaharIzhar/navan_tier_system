# Business logic (detailed)

The README gives the short version. This page keeps the detailed rules the application implements.
Only the baseline tier thresholds come from the assignment. Everything else here (flag conditions,
attention levels, staleness, Day 30 thresholds) is a **prototype policy**: configurable in
`backend/app/config.py`, not calibrated against real outcomes.

The submitted flowchart is [`business-logic.excalidraw`](business-logic.excalidraw). The diagram below is a text version that renders on GitHub.

## Flow at a glance

Blue = deterministic code, purple = AI (LLM + web search), green = human decision. Nothing on the AI path can change a tier.

```mermaid
flowchart TD
    A[Company signs up<br/>name, domain, reported GBV, enrichment headcount] --> B[Import & normalise<br/>parse $ values, keep Day 30 data locked away]
    B --> C[Baseline tier rules<br/>GBV ≥ $500K → T1<br/>GBV ≥ $100K or 150+ employees → T2<br/>else T3 · provisional if headcount unknown]
    C --> D{Standard research<br/>enabled for this company?}
    D -- no --> F
    D -- yes --> E[AI research<br/>Claude Haiku + web search<br/>5 routing fields (Deep Research: 8)<br/>name + domain only]
    E --> E2[Validate output<br/>JSON schema · 1 repair retry<br/>drop citations not returned by search<br/>mark stale / future-dated evidence<br/>classify source reliability]
    E2 -- failed --> E3[Run recorded as failed<br/>error shown, no findings invented]
    E3 --> F
    E2 -- ok --> F[Structured signals<br/>accepted headcount, research headcount,<br/>direct travel evidence, growth evidence, coverage]
    F --> G[Reason flags<br/>Data Conflict · Travel Potential · Growth Opportunity<br/>Insufficient Evidence · Tier Mismatch]
    G --> H{Tier Mismatch?}
    H -- no --> I[Attention only<br/>Review Suggested / Monitor / No action]
    H -- yes --> J[Tier proposal<br/>standard-rule correction or evidence-based override<br/>deduplicated · rejected ones not re-raised]
    J --> K[Review Now queue]
    I --> L[Company page]
    K --> M{Human review}
    M -- Approve --> N[Applied tier changes inside prototype<br/>original + previous tier kept, audit event]
    M -- Reject --> O[Tier unchanged, reason recorded]
    M -- Comment --> P[Proposal stays open]
    P --> Q[Manual enrichment<br/>or Deep Research on request]
    L --> Q
    Q -- rules only, 0 AI calls --> F
    Q -- Deep Research, confirmed --> E

    R[Day 30 activity received<br/>travelers, bookings, trend] --> S[Lightweight reassessment<br/>compare with Day 0 assessment<br/>bookings ≠ GBV<br/>can suggest only Tier 3 → Tier 2]
    S --> G
    S -.-> T[(Day 0 assessment<br/>kept unchanged)]

    classDef det fill:#eef0fd,stroke:#3c4fe0,color:#1b1f27;
    classDef ai fill:#f2edfc,stroke:#6b3fc8,color:#1b1f27;
    classDef human fill:#e8f6ee,stroke:#18794e,color:#1b1f27;
    class B,C,E2,E3,F,G,H,I,J,K,S,T det;
    class E ai;
    class M,N,O,P,Q human;
```

## 1. Baseline tier (assignment rules)

- Tier 1: GBV ≥ $500K.
- Tier 2: GBV ≥ $100K, or 150+ employees.
- Tier 3: everyone else.

Edge cases:
- **Missing headcount with GBV < $100K** gives a *provisional* Tier 3, because headcount eligibility can't be ruled out.
- **Missing, negative or unparseable GBV** gives no tier and a data-quality issue. It is never treated as $0.
- The dataset tier (`original_tier`), the calculated baseline, and the tier currently applied in the prototype are stored separately.

**Dataset finding:** all 43 `current_tier` values already match the rules. Mismatches therefore come only from research, manual corrections, or Day 30 activity.

## 2. Research (AI)

- **Model:** Claude Haiku 5.5 with Anthropic's server-side web search, at most 5 searches per standard run.
- **Standard research (live prompt, labelled v4)** covers the routing basics: industry, locations, employees, funding, hiring. **Deep Research** covers all 8 fields, adding travel requirements, recent expansion and support complexity. Fields a run didn't cover show **Not searched**.
- **Fields:** industry and business model, geographic footprint, employee count, hiring trends, **direct travel indicators**, funding, expansion, support complexity.
- **Output:** structured findings, each with source URL, title, publisher, date, `observed`/`inferred`, and signal type (`direct_travel`, `indirect_growth`, `descriptive`).
- **Inputs:** the prompt contains only the company name and domain. It never contains reported GBV or Day 30 data.

The AI's output is not trusted as-is:

| Check | What happens |
|---|---|
| JSON schema (Pydantic) | One repair retry without web search, then the run is marked failed with the raw text kept. The closing summary line is optional, because long Deep Research answers sometimes leave it out |
| Citation check | Findings whose URL wasn't among the search results returned in that run are dropped and logged |
| Headcount bands | "51-200" or "fewer than 25" can't be used as an exact number (cleared deterministically) |
| Dates | Evidence older than 18 months is marked **Stale**. Evidence dated after the research run is dropped |
| Source reliability | Company site or registry / independent source / data aggregator, decided by domain |
| Timeouts, API errors, missing key | Recorded on the run and shown in the UI; the rules keep working |

**Deep Research runs in the background.** The company page shows a progress bar with the current step (starting, searching the web, checking sources, saving). It keeps running if you leave the page and refreshes the findings when done. Only one Deep Research runs per company at a time; a run cut off by a server restart is marked as interrupted.

**Cost controls:**
- Results are cached per company and prompt version label.
- Standard research runs only for a configured demo set of 16 companies, or when someone clicks it.
- **Deep Research** runs only after a confirmation dialog explaining what it will do. It reuses existing evidence as context and adds new evidence without deleting old evidence. Once it has run, the button is turned off and it's no longer suggested.
- Each run records tokens, searches and an approximate cost for the team running the tool (not shown to salespeople).
- A failed run whose search results were saved can be re-checked later without a new AI call (`reprocess_run`), e.g. after a validation fix.

## 3. Reason flags (prototype policy, may be several)

| Flag | Fires when | Never fires on |
|---|---|---|
| **Data Conflict** | Employee figures fall on both sides of 150 (**material** if GBV < $100K, because then headcount decides the tier), or differ by more than 50%. A verified manual value downgrades it to "resolved" | Differences in non-routing fields such as funding totals |
| **Travel Potential** | A source *states* employees travel for work (job ad, field or client-site work). **Material** with 2+ independent sources. Informational only on Tier 1 | Aggregator-only, inferred, or **local field travel** (home visits, mileage), which doesn't create bookable travel |
| **Growth Opportunity** | 2+ independent growth signals (funding, expansion, hiring, international footprint). Multiple articles on one announcement count once | — never drives a tier change; its tooltip says "growth isn't proof of travel spend" |
| **Insufficient Evidence** | Headcount unknown and nothing found, invalid GBV, or research found nothing in 5+ of 8 fields | — its tooltip says "missing isn't the same as 'doesn't travel'" |
| **Tier Mismatch** | The standard rules (with accepted values) give a different tier, research headcount would change the tier, strong direct travel evidence on a Tier 3, or material Day 30 activity | Informational flags alone |

## 4. Attention, proposals and reviews (prototype policy)

These four things are kept separate:
- **Tier**: the support level.
- **Flag**: why the company was flagged.
- **Attention**: when someone should look.
- **Review status**: where a proposal stands.

How attention is assigned:
- **Review Now**: an open tier proposal, or a conflict that decides tier eligibility.
- **Review Suggested**: moderate signals, such as one source of travel evidence, a conflict that doesn't change the tier, or growth near a tier threshold.
- **Monitor**: weak signals only.

How proposals are made:
- Only Tier Mismatch creates a proposal. Proposals are typed as **standard-rule correction** or **evidence-based override**.
- They are deduplicated per target tier. A proposal a reviewer rejected is not raised again unless new evidence appears. A proposal the latest evidence no longer supports is marked **No longer needed**.
- **Approve** changes the applied tier and keeps the original and previous tier. Approving a research-headcount correction also records that headcount as reviewer-accepted, so the rules stay consistent. Approving an override is logged as a policy override.
- **Reject** requires a reason.
- **Add comment** records a note and keeps the proposal open.

## 5. Manual enrichment

A Growth employee can set employee count, a direct travel requirement, funding, expansion, geographic footprint, or a free-text note:
- Each entry is a new evidence row. Original research is never edited.
- It is **Verified** only with a source URL and an explicit check; otherwise it shows as *unverified*.
- Saving reruns the rules immediately with **0 AI calls** (tested) and shows a before/after diff.
- A free-text note is explanatory only.
- An entry can be withdrawn, and it stays in history.

## 6. Day 30 reassessment (prototype policy)

Day 30 numbers can be **updated** or **removed**. Both ask for confirmation and are logged:
- **Update:** travelers, bookings in 30 days, and optional free-text remarks. The booking trend is calculated by the server from the previous bookings to the new ones (318 → 400 = ↑26%), so it always matches the numbers; the dialog previews it. The first arrival from the dataset keeps the file's own trend (days 16–30 vs days 1–15). The trend's tooltip says which comparison is shown.
- **Remove:** the company goes back to its signup assessment, and any tier change suggested from the activity is withdrawn.

Day 30 activity is imported into a separate table and stays *unreceived* until released, so it can't influence signup routing. When it arrives:
1. A new rules-only assessment compares it with the latest Day 0 assessment, and says whether the activity *strengthens*, *weakens* or is *consistent with* it.
2. Activity is material at 15+ travelers, or 40+ bookings growing 25%+. Day 30 never proposes Tier 1: Tier 1 depends on reported GBV ($500K+), and booking counts can't show dollars. Strong activity on a Tier 2 company becomes a Travel Potential flag (Review Suggested).
3. The only proposal Day 30 can make is Tier 3 → Tier 2, as an evidence-based override, because **booking counts are not dollars**.

Day 30 results on the 10 dataset rows are in [`cases.md`](cases.md#day-30-results-on-the-10-activity-rows).

## 7. Assumptions

| Assumption | Why |
|---|---|
| Signup cutoff = the research run time | The dataset has no signup dates. Each run stores its cutoff; later-dated evidence is dropped |
| Stale = older than 18 months | A reasonable default for company facts, configurable |
| Day 30 data is "received" by clicking a button | Simulates arrival; the CSV contains it from the start |
| Research headcount never silently replaces enrichment | A disagreement becomes a conflict and a proposal for a human |
| Priority = impact → evidence strength → actionability | Shown as High/Medium/Low, never as a probability or dollar figure |
| Auto-research covers 16 demo companies | Keeps API cost bounded. `AUTO_RESEARCH_ON_IMPORT=true` researches the demo set on start, and any company can be researched with one click |
