# Evaluation framework

> **Note:** there is no Reports page in the UI yet. Everything referenced below as "`/api/reports` → …" is already computed by the backend and returned by `GET /api/reports`; the section names are the keys in that response.

This page explains how to tell whether Navan Growth Intelligence is reliable and useful. It separates what the prototype can show today from what needs real outcomes. The dataset is fictional and has no verified tier outcomes, so **no accuracy number is reported anywhere in this project**.

## 1. What "right" means

There are three different questions, and each one needs its own measurement:

| Question | Example of an error | Measured by |
|---|---|---|
| Did the rules do what the policy says? | GBV $500,000 was put in Tier 2 | Scenario checks (automated, available now) |
| Was each flag or proposal backed by evidence? | A Tier 1 proposal that cites only a LinkedIn estimate | Unsupported-recommendation checks (available now) |
| Was the routing decision good for the business? | An account was moved to Tier 1 and never grew | Verified outcomes (needs production data) |

## 2. Metrics

### False positives (unnecessary flags)
A flag or proposal is a false positive when a documented review finds it unnecessary, or when verified outcomes later show it was not needed.

- **Precision among reviewed cases** = proposals judged correct ÷ proposals reviewed. Each rejection needs a reason, so rejection reasons can be grouped.
- **False-positive rate by flag type** (Travel Potential, Data Conflict, …), to see which rule is noisy.
- **Unnecessary review time**: minutes spent on proposals that were rejected.
- **In the prototype:** `/api/reports` → `review_outcomes` lists rejected proposals. A rejection is a candidate false positive for error analysis, *not* ground truth. A reviewer can be wrong.

### False negatives (missed flags)
A false negative is a meaningful opportunity or tier mismatch that the system did not flag.

- **Recall** = real opportunities flagged ÷ all real opportunities. This **cannot** be measured from reviewed cases alone, because those are all flagged by definition. It needs a labelled sample that includes companies the system did not flag. Plan: each month, a Growth reviewer labels a random sample of unflagged companies, stratified by tier and by how much public information exists.
- **Missed high-value opportunities**: unflagged companies that later reached Tier 1 GBV.
- **Misses broken down by** industry, company size, and source availability (for example, small UK private firms have little public data).
- **In the prototype:** `/api/reports` → `retrospective_day30` compares each Day 0 assessment with the company's Day 30 activity *after the fact*. Example: strong activity with no Day 0 flag is labelled "possible miss". Day 30 data is never used for the signup decision. The comparison is a weak proxy, because booking counts are not GBV.

### Unsupported actions
These are proposals or flags that:
- have no cited evidence (`/api/reports` → `unsupported_recommendations`).
- rely only on aggregator, synthetic, or inferred evidence (same report).
- cite a URL that the search tool did not actually return. These citations are removed automatically before storage, and `/api/reports` → `citation_validation` counts them.
- treat an inference as a fact. The LLM must label each finding `observed` or `inferred`, and inferred travel evidence never triggers Travel Potential.
- go against the baseline rules without a documented reason. Every override is typed `evidence_override`, carries its rationale, and is logged as a policy override when approved.

### Operational metrics (available now)
- Research completeness: the status of each field across researched companies (`/api/reports` → `missing_data`).
- Research cost per company, plus web searches and LLM calls (`/api/reports` → `research_cost`).
- Review turnaround time: from proposal creation to decision (timestamps stored).
- Approval and rejection patterns, broken down by proposal type.

## 3. Scenario checks (what is actually tested)

The scenario checks show that the rules behave as specified. They say nothing about predictive accuracy.

- **17 scenario checks** run on every call to `GET /api/reports` (`scenario_checks` in the response). They cover tier boundaries, missing and invalid inputs, conflicts across the 150-employee threshold, verified manual values resolving a conflict, and Day 30 thresholds and the "weakens" comparison.
- **65 backend pytest tests and 3 frontend smoke tests** cover the following (see `backend/tests/`):
  - malformed LLM output, which is repaired once and otherwise fails visibly
  - timeouts and a missing API key
  - fabricated citations, which are dropped
  - duplicate sources, which count once
  - stale and future-dated evidence
  - manual correction with zero LLM calls
  - approve, reject and request-info flows
  - duplicate-proposal suppression
  - Day 0 versus Day 30 separation (Day 0 rows are never modified, and no Day 30 text appears in prompts)
  - persistence across a restart

## 4. Error analysis loop

For each error found in review or in outcomes:

1. **Identify the wrong decision**: which flag, attention class or proposal.
2. **Inspect the evidence available at decision time**. Every assessment row is immutable and stores its inputs, flags, evidence ids and the research run it came from, so the exact state can be rebuilt.
3. **Classify the cause:**
   - *Retrieval*: search did not find the source.
   - *Extraction*: the LLM misread or mis-typed a finding.
   - *Stale data*.
   - *Unsupported inference*.
   - *Decision policy*: a threshold or rule was wrong.
4. **Fix the right component:**
   - Retrieval → search scope or Deep Research targeting.
   - Extraction → prompt version (prompts are versioned and kept; see `docs/llm_experiments/`) or post-processing.
   - Policy → the thresholds in `backend/app/config.py`.
5. **Rerun the original case and add a regression test** (a pytest case, or a scenario check for policy errors).

This loop has already been run on live data. Section 9 of [`llm_experiments.md`](llm_experiments/README.md) lists six errors found in end-to-end runs on 10 real companies. Each entry gives its cause class, fix and regression test. Example: home-visit nursing ads were counted as business travel. The cause was extraction granularity, fixed with prompt v3's `travel_scope` and a rule change.

Reviewer approval alone is never used as a measure of accuracy.

## 5. What needs production data

| Metric | Why it cannot be shown with this dataset |
|---|---|
| Flag precision and recall | No verified labels; the values are fictional |
| Business impact (revenue from re-tiered accounts) | No real GBV outcomes |
| Calibration of Day 30 thresholds | 10 fictional activity rows; 30 days is not a year |
| Value of each signal type | Needs outcomes to compare against |

The policy thresholds (Day 30 travelers ≥ 15, "near threshold" = within 15% of a GBV cut-off, and so on) are **prototype hypotheses**. They are not validated values. They live in `backend/app/config.py`, and the goal is to calibrate them once outcome data exists.
