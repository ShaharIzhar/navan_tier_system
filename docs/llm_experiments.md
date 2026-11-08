# LLM prompt testing and refinement

**Author:** Shahar Izhar · **Model:** Claude Haiku 5.5 (`claude-haiku-5-5`) with Anthropic's server-side web search tool (`web_search_20250305`) · **Run on:** 8 November 2026

Everything below comes from real API runs. The raw, unedited outputs are saved in [`docs/experiments/v1/`](experiments/v1), [`v2/`](experiments/v2) and [`v3/`](experiments/v3). Sections 1–8 cover v1 → v2; section 9 covers the second iteration (v3), driven by errors found in live app runs. Each file holds:
- the exact system and user prompt
- the model's raw text
- every search result URL the tool returned
- token and search usage
- an automatic analysis

To reproduce a run (from `backend/`):

```
python -m scripts.prompt_experiment --version v2 --cases P-007 P-033 P-009 --conflict-test P-007
python -m scripts.prompt_experiment --version v3 --cases P-025 P-018 P-009
```

## What the LLM is (and is not) used for

The LLM reads public web pages and extracts **structured findings with source URLs** for 8 fields. Every decision after that is made by deterministic Python:
- validating the output
- dropping fake citations
- deciding stale vs fresh
- judging whether a conflict matters for the tier
- flags, attention, proposals and tiers

The prompt contains only the company **name and domain**. It never contains the reported GBV, the enrichment headcount or Day 30 activity, and a test enforces this.

## 1. Original prompt (v1)

Full text: `SYSTEM_V1` / `USER_V1` in [`backend/app/research/prompts.py`](../backend/app/research/prompts.py). The core of it:

```text
You are a company research assistant for a B2B sales team at a business-travel platform. ...
- Use only information from your web search results. Do not use prior knowledge.
- Every finding must cite the URL of the search result it came from.
- If you cannot find information for a field, mark it not_found. Do not guess.
- If sources disagree, mark the field conflicting and describe the conflict.
- Separate facts stated by a source (observed) from your own inferences (inferred).
- Do not estimate travel spend or GBV.
- Do not give confidence percentages.
- Respond with a single JSON object and nothing else.

Research this company: Company name: {name}  Website domain: {domain}
Cover these fields: industry_business_model, geographic_footprint, employee_count, hiring_trends,
travel_indicators, funding_financial, recent_expansion, support_complexity
signal_type: direct_travel | indirect_growth | descriptive ...
For employee_count findings, put the number in value_number.
Return JSON in exactly this shape: {...}
```

## 2. Test cases

| Case | Why it was chosen |
|---|---|
| **P-007 IMU Biosciences** (Tier 2 only because of 155 employees, $48K GBV) | The tier depends on a headcount just above the 150 threshold |
| **P-009 NexGen Cloud** ($460K GBV, 280 employees) | Well documented. Close to the Tier 1 GBV threshold, many aggregator figures |
| **P-033 Moorside Manufacturing Ltd** (11 employees, $7.5K GBV) | Small private UK firm, little public information. Its **name doesn't match its domain** (`moorsideengineering.com`) |
| **P-007 conflict test** | Deep Research prompt given two existing employee values: the dataset's **155** and a clearly labelled **SYNTHETIC 90**. These straddle the 150 threshold. The point is to see whether the model treats a synthetic or unsourced value as fact |

## 3. Representative v1 response (P-009 NexGen Cloud, excerpt)

The `employee_count` field, quoted as returned:

```json
{
 "status": "conflicting",
 "summary": "Reported headcounts range from fewer than 25 to about 117, with the most recent workforce-data sources clustering around 108 to 117 in March 2026.",
 "findings": [
  {"claim": "PitchBook lists 117 total employees.", "value_number": 117, "source_url": "https://pitchbook.com/profiles/company/459299-44"},
  {"claim": "Tracxn reports 108 employees as of 31 March 2026.", "value_number": 108, "source_url": "https://tracxn.com/d/companies/nexgen-cloud/..."},
  {"claim": "Crunchbase shows a headcount band of 101-250.", "value_number": 101, "source_url": "https://www.crunchbase.com/organization/nexgen-cloud-bf96"}
 ]
}
```

The `travel_indicators` field:

```json
{"status": "not_found", "summary": "None of the retrieved sources state that employees travel for work ... the job listings and careers page describe remote and office-based roles without travel requirements.", "findings": []}
```

v1 behaved well in several ways:
- All 4 runs produced valid JSON on the first try.
- Every finding carried a URL.
- The model never estimated GBV.
- Moorside's name/domain mismatch was resolved correctly: *"The website pages at moorsideengineering.com show the Moorside Manufacturing Ltd name, the Two Trees Lane Denton address, and company number 04936087. Third-party company profiles … list the same company number."*
- **Citation validation caught real cases.** In the v1 NexGen run, the model cited a Yahoo Finance URL for two claims, but the search tool never returned that URL. The validator dropped both findings (`unsupported_citation`).

## 4. The difficult case: conflicting employee counts (P-007)

Given the dataset's 155 and the SYNTHETIC 90 as "existing evidence", v1 answered:

> "Public sources disagree widely on IMU Biosciences' headcount, with the most common band being 11-50 and the highest exact figure being 77. **None of the retrieved sources supports 155 or 90**, so the Tier 2 threshold (150) should not be decided from current evidence."

And in its limitations: *"Neither the 155 nor the 90 figure from the existing evidence could be traced to any retrieved source, and the existing evidence has no URL to verify."*

**This passed the robustness test.** The model did not adopt the synthetic value, and it did not pick a side without evidence. It also surfaced something useful that the dataset alone wouldn't show: public sources put IMU's headcount far below the fictional 155 enrichment value, at 25–80 across aggregators. In the app, this becomes a **material Data Conflict** and a Tier 2 → Tier 3 standard-rule proposal for a human to review. It is never applied automatically.

## 5. Weaknesses observed in v1

Running v1 on the three standard cases showed three problems. None were invented for this write-up; each is visible in the saved JSON.

| # | Observed failure | Evidence | Why it matters |
|---|---|---|---|
| 1 | **Headcount bands became exact numbers.** | NexGen v1: `"101-250"` → `value_number: 101`, `"51-200"` → `51`, `"fewer than 25"` → `25`. Employee numbers extracted: `[117, 108, 109, 92, 101, 51, 79, 25]` | These numbers go straight into the deterministic conflict and tier logic. A band's lower bound reads as a precise figure, which creates false conflicts and could create false tier proposals |
| 2 | **Direct travel evidence was not actively looked for.** | `travel_indicators` was `not_found` in **3 of 3** standard runs. v1 didn't log search queries, but the returned URLs show what it reached: careers *landing pages* (`careers.nexgencloud.com`, `imubiosciences.com/careers`) and job-board company profiles, with no individual job postings | Direct travel evidence is the most important signal for a travel platform. A careers landing page rarely states travel requirements; individual postings do |
| 3 | **Ordinary differences between databases were reported as conflicts.** | 2–3 fields marked `conflicting` per company: funding totals in different currencies and cut-off dates, "Greater Manchester vs Lancashire" for Moorside, job-board counts from different days | Each one became a Data Conflict flag, adding noise that would teach salespeople to ignore the flag |

## 6. Refinement (v2 prompt + two deterministic processing steps)

**Prompt changes** (`SYSTEM_V2` / `USER_V2` in `prompts.py`):
- **A search plan in priority order.** Step 2 is: *"Travel requirements: search for the company's job postings or careers page together with words like 'travel', 'client site', 'on-site', 'field'. This is the most important field for this research."*
- **Employee rules:** *"Put a number in value_number ONLY when the source states one exact headcount … For a band or range … set value_number to null and keep the band in the claim."*
- **Conflict rules:** *"Report a conflict only when sources disagree about the same fact for the same period in a way that changes the conclusion … Different estimates from different databases, or figures from different dates, are normal."*
- **A tighter definition of `direct_travel`:** use it only when the source states it, and mark anything guessed as `inferred`.

**Processing changes.** A prompt alone shouldn't be trusted, so two deterministic steps were added:
1. `clear_band_headcounts()` in `research/evidence.py` clears `value_number` whenever the claim text describes a band ("51-200", "fewer than 25", "500+"). The change is recorded on the run as a `normalized_finding`.
2. Only LLM-reported conflicts in **routing-relevant fields** (employee count, travel indicators) can create a Data Conflict flag. Other conflicts stay visible in the research section.

Both have regression tests: `test_headcount_band_is_not_used_as_exact_number` and `test_non_routing_llm_conflicts_do_not_raise_flags`.

## 7. Re-run with v2 (same cases, same day)

| Case | Metric | v1 | v2 |
|---|---|---|---|
| P-009 NexGen | Employee numbers used | `117, 108, 109, 92, 101, 51, 79, 25` | `79, 117, 92`. Bands kept as text only |
| P-009 NexGen | travel_indicators | not_found | **found**: a Senior Deployment Lead job ad requiring "extensive global travel to deployment sites" (direct_travel, observed). The model labelled its own guess about other roles `inferred` |
| P-009 NexGen | Fields marked conflicting | 3 | 0 |
| P-009 NexGen | Searches / cost | 5 / $0.064 | 3 / $0.042 |
| P-007 IMU | travel_indicators | not_found | still not_found, now after a targeted search for `"IMU Biosciences careers travel client site"`. Summary: *"No job ad, careers page or company page found states that roles require business travel…"* |
| P-007 IMU | Fields marked conflicting | 2 | 0. The headcount disagreement with the enrichment value is still caught deterministically |
| P-033 Moorside | Fields marked conflicting | 2 | 0 |
| P-033 Moorside | travel_indicators | not_found | not_found after a dedicated search. The travel search also returned pages for a *different* company ("Moorside Precision", `moorside-precision.co.uk`), and the model correctly didn't use them |
| P-007 conflict test | Behaviour | Did not adopt 155 or 90 | Same. The band filter also cleared 2 band-derived numbers the model still emitted (the Deep Research prompt wasn't changed), which shows why the code check exists |

v2 search queries, as captured from the API:
- `NexGen Cloud careers jobs travel client site`
- `IMU Biosciences careers travel client site`
- `Moorside Manufacturing careers jobs travel client site`

v1 did not log its queries, so a direct query comparison isn't possible. The improvement shows in the results: an individual job posting (`jobgether.com/offer/…-deployment-lead`) appeared only in v2.

**How the NexGen result flows through the app:**
1. The two travel findings come from one job posting, so they count as **one independent source**.
2. That gives a *moderate* Travel Potential flag: Review Suggested, with no tier proposal.
3. Two independent sources plus a Tier 3 account would be needed before the system proposes an override.

## 8. Remaining limitations (honest list)

- **The band filter is too cautious.** In the v2 conflict test it cleared LinkedIn's "View all 49 employees" because the same sentence also mentioned the "11-50" band. It loses some real figures rather than risk using a band as a number. That's acceptable for routing, but it is a real trade-off.
- **v2 reports fewer conflicts overall.** In v1, IMU's funding figures (an £11.5M Series A vs a later ~$53M round) were flagged as a conflict; in v2 they appear only in the summary. That's the intended trade for routing, but a non-routing discrepancy is now easier to miss.
- **Aggregators dominate headcount evidence**, and their figures often have no "as of" date. Companies House filings were found for Moorside (via Endole, 6 employees) but not for IMU. Deep Research targets this gap.
- **One posting can appear as two findings.** The deterministic layer counts sources by host, so this doesn't inflate evidence, but the model's own "independent source" judgement isn't fully reliable.
- **Similar company names.** The Moorside travel search returned a different company with a similar name. The model ignored it this time, but nothing enforces that; findings are trusted only because the model confirms identity, and that confirmation isn't independently checked.
- **Job ads are a snapshot.** A posting found today says nothing about last year, and finding no travel ad is not evidence of no travel.
- **Prompt length and cost.** Search results make up most of the input tokens (45–80K per run). At Haiku 5.5 prices, a standard run costs about $0.04–0.06, most of it web search fees.
- **Small sample.** These are 4 cases × 2 versions, enough to find and fix failure modes but not to measure accuracy. See [`evaluation.md`](evaluation.md).

## 9. Second iteration: error analysis on live application runs (v3)

After v2, I ran the full app on 10 companies. Live research, then the deterministic rules. The point was to find errors that only appear end to end. Each error was handled with the loop from [`evaluation.md`](evaluation.md): identify the error, inspect the evidence, classify the cause, fix the right component, add a regression test, and rerun.

| # | Error observed in the live app | Cause | Fix | Regression test |
|---|---|---|---|---|
| 1 | **Bionical (P-025):** Tier 3 → Tier 2 proposal because research headcounts 219 / 90 / 152 had a median of 152 | **Decision policy.** A median of disagreeing estimates was treated as evidence | Propose from research headcount only when every research figure is on the same side of 150. Otherwise it stays a material conflict, and Deep Research is suggested | `test_disagreeing_research_headcounts_do_not_create_proposal` |
| 2 | **Bionical, after Deep Research:** community-nurse ads ("enjoy travel… care to patients in their own homes", car allowance and mileage) produced a **Tier 3 → Tier 2 travel override** | **Extraction granularity.** "Travel" in a job ad was not split into bookable vs local. The model itself wrote: *"they indicate travel for care delivery rather than business travel by corporate staff"* | **Prompt v3:** every `direct_travel` finding gets `travel_scope` = `business_travel` / `local_field_travel` / `unclear`. **Rule:** local field travel can't make Travel Potential strong or trigger an override | `test_local_field_travel_does_not_create_override` |
| 3 | **Balfour Beatty and Anthropic (Tier 1)** were sent to Review Suggested with "consider an extra AE touchpoint" | **Decision policy.** Travel Potential ignored the current tier | On Tier 1, Travel Potential is informational (low → Monitor) | `test_travel_on_tier1_is_informational` |
| 4 | Bionical showed **Review Now** but recommended "check the travel evidence" | **Bug.** With two Data Conflict flags, `recommend()` kept only the last one | Keep the most severe flag per type | `test_recommendation_uses_most_severe_flag_of_each_type` |
| 5 | After a reviewer **rejected** IMU's proposal, the company stayed in Review Now indefinitely | **Policy.** A reviewed conflict kept re-escalating | Once its proposal is rejected, a material conflict drops to Review Suggested until new evidence arrives | Extended `test_reject_keeps_tier_and_suppresses_duplicate` |
| 6 | An Indeed *search-results* page was used as evidence for one employer | **Source quality.** Search listings mix employers | Job-board search URLs are classified as aggregator | `test_job_board_search_page_is_aggregator` |

**v2 vs v3 on Bionical's job ads.** Same standard prompt structure, same day. Raw files: `experiments/v2/P-025-standard.json` and `experiments/v3/P-025-standard.json`.

| | v2 | v3 |
|---|---|---|
| Nurse home-visit ads | `direct_travel`, observed, no scope (counted as business travel) | `direct_travel`, observed, **`local_field_travel`** (5 of 5) |
| NexGen Deployment Lead ("extensive global travel") | `direct_travel`, no scope | `direct_travel`, **`business_travel`** |
| Greyparrot | — | Director of Sales (US/EMEA travel) labelled `business_travel`; site installs labelled `unclear` or `local_field_travel` |

**Result in the app after v3 and the policy fixes:**
- Both wrong Bionical proposals were automatically marked **superseded**, with audit events. They remain visible in history.
- Bionical stays in Review Now for the genuine reason: its headcount is disputed and decides the tier.
- Greyparrot and NexGen keep their Travel Potential flags.
- Reports → "Unsupported recommendations" lists the superseded aggregator-only proposal. The check catches a real historical error, not a planted one.

**A versioning mistake, caught and fixed.** When adding `travel_scope`, I first changed the JSON shape that every prompt version shared, so a "v2" rerun was quietly getting part of v3. I noticed because that run returned `travel_scope` values. Now each version has its own frozen shape, and I checked that rebuilding the v1, v2 and v3 prompts gives **byte-identical** text to the prompts stored in the saved experiment files. I then deleted the contaminated file and reran a clean v2.
