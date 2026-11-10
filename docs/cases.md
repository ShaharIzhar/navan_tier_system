# Representative cases (live research, 8 November 2026)

**Author:** Shahar Izhar

**How these were produced.** All 10 demo companies were researched live with prompt v3 (Claude Haiku 5.5 + web search).

> **Version note:** these cases come from the v3 runs (all 8 fields in standard research). Standard research is now v4 (5 fields: industry, locations, employees, funding, hiring), and travel requirements, expansion and support complexity come from Deep Research. The rules are unchanged; a company's travel findings now appear after Deep Research instead of standard research. See [`llm_experiments.md` §11](llm_experiments/README.md). Every source below is a URL that the search tool actually returned in that run; the app drops any other URL automatically.

**Data caveats.**
- Reported GBV, employee estimates, tiers and Day 30 activity are **fictional scenario values**.
- Research findings are public-web claims, mostly from data aggregators. Treat them as hypotheses, not verified facts.

**Totals for the demo set:**
- About **$0.04 per standard research run**, including web search fees.
- About **$0.88 overall**, including the experiments' reruns (from `GET /api/reports` → research cost).

The "Outcome" column is the Day 0 assessment, i.e. before any Day 30 data arrives.

| Company | Scenario values | Outcome (Day 0) |
|---|---|---|
| P-007 IMU Biosciences | $48K GBV · 155 employees · Tier 2 | **Review Now**: material Data Conflict, Tier 2 → Tier 3 standard-rule proposal |
| P-025 Bionical Solutions | $82K · 85 · Tier 3 | **Review Now**: material Data Conflict, no proposal (sources disagree), Deep Research suggested |
| P-009 NexGen Cloud | $460K · 280 · Tier 2 | **Review Suggested**: Travel Potential (1 source), growth near the Tier 1 threshold |
| P-018 Greyparrot | $395K · 42 · Tier 2 | **Review Suggested**: material Travel Potential (several sources), no proposal (already Tier 2) |
| P-030 Focusrite | $85K · 580 · Tier 2 | **Review Suggested**: growth signals and GBV near the Tier 2 threshold. Headcount confirmed above 150 |
| P-019 CloudNC | $44K · 125 · Tier 3 | **Review Suggested**: growth signals, headcount near 150 |
| P-002 Attio | $47K · 24 · Tier 3 | **Monitor**: growth only; no travel requirement found |
| P-021 Balfour Beatty | $620K · 26,000 · Tier 1 | **Monitor**: travel evidence is informational for a Tier 1 account |
| P-041 Anthropic | $850K · 1,200 · Tier 1 | **Monitor**: same |
| P-033 Moorside Manufacturing | $7.5K · 11 · Tier 3 | **No action**: research is consistent with a micro business |

---

## P-007 IMU Biosciences: the tier hangs on a disputed headcount

- **What the rules say:** Tier 2, only because enrichment reports 155 employees. Reported GBV of $48K is far below $100K.
- **What research found:**

  | Source | Headcount | Reliability |
  |---|---|---|
  | [PitchBook](https://pitchbook.com/profiles/company/432627-67) | 25 | aggregator |
  | [Built In London](https://builtinlondon.uk/company/imu-biosciences) | 53 | job board |
  | [LinkedIn](https://uk.linkedin.com/company/imubiosciences) | 11-50 band | aggregator; kept as text, not a number |

  No job posting mentions travel. The company recently closed a Series A extension of over $53M (June 2026, per the research summary).
- **Why it matters:** the sources fall on both sides of 150 and GBV is below $100K, so the conflict **decides Tier 2 eligibility**. That makes it a material Data Conflict.
- **What the system does:**
  1. Opens a **Tier 2 → Tier 3 standard-rule correction** for a human. The research figures all agree the company is below 150.
  2. Flags that the evidence is mostly aggregators.
  3. Recommends confirming the headcount.

  The applied tier does not change on its own.
- **Day 30, for comparison only:** 19 travelers and 57 bookings (+62%). This is real activity for a "small" company. It shows why the system asks a person rather than downgrading automatically.

## P-025 Bionical Solutions: two lessons from live data

- **Headcount:**
  - The company's own [modern slavery statement](https://www.bionical.com/modern-slavery-statement.pdf) (December 2023, marked *stale*) says "over 700 worldwide".
  - [PitchBook](https://pitchbook.com/profiles/company/125238-61) says 90 and [Craft.co](https://craft.co/bionical-solutions) says 219.
  - Enrichment says 85.

  The figures straddle 150 and GBV is under $100K, so this is a **material conflict**. Because the research sources disagree among themselves, there is **no proposal**. The system recommends confirming the figure and suggests Deep Research instead.
- **Travel:** the only travel evidence is community nurse adverts for home visits, for example [NHS Jobs E0393-24-0010](https://www.jobs.nhs.uk/candidate/jobadvert/E0393-24-0010). They mention a car allowance and mileage. Prompt v3 labels this `local_field_travel`, which doesn't count as bookable business travel.
- **Correction history:** an earlier run (before v3) turned these adverts into a Tier 3 → Tier 2 override proposal. Another earlier proposal relied on a median of conflicting aggregator figures. Both are kept in the audit trail as *No longer needed* (superseded). See [`llm_experiments.md` §9](llm_experiments/README.md).

## P-009 NexGen Cloud: travel evidence found by a targeted search

- **Travel:** a [Deployment Lead posting](https://jobgether.com/offer/6a87c65fa55bd7e3ae1046f8-deployment-lead) requires "extensive global travel to deployment sites" (`business_travel`, observed). It is one posting, so it counts as **one independent source**. That gives a moderate Travel Potential flag: Review Suggested, with no proposal.
- **Headcount:** research gives 79–117 ([Built In](https://builtin.com/company/nexgen-cloud), [PitchBook](https://pitchbook.com/profiles/company/459299-44)) against 280 from enrichment. GBV of $460K already sets Tier 2, so the conflict is *moderate*.
- **Growth:** USD.AI GPU financing of [$106M](https://usd.ai/blog/usdai-106m-nexgen-cloud-finland-gpu-financing) (October 2026). The near-threshold GBV makes the growth signal *moderate*, but the system states that growth is not evidence of GBV.
- **Day 30, for comparison only:** 83 travelers give a Travel Potential flag. Day 30 never proposes Tier 1, because Tier 1 depends on reported GBV and booking counts aren't dollars.

## P-018 Greyparrot: strong travel evidence, but the tier is already right

- **Travel:** several independent sources, including the company's own [Technical Operations Engineer job description](https://www.greyparrot.ai/hubfs/Careers/Technical%20Operations%20Engineer_final%20JD.docx.pdf?hsLang=en-gb) ("travel to clients to install or update hardware"), plus listings mentioning travel within the UK, the US and EMEA. The result is material Travel Potential.
- **Why there's no proposal:** reported GBV of $395K already puts it in Tier 2, and overrides from travel evidence are only raised for Tier 3. The recommended action is an extra AE touchpoint.

## P-030 Focusrite: employee-based Tier 2 confirmed

- **Headcount:** [Bloomberg](https://www.bloomberg.com/profile/company/FOCIF:US) gives 537 and [PitchBook](https://pitchbook.com/profiles/company/107184-16) gives 585. Enrichment says 580. All are well above 150, so the employee-based Tier 2 is well supported despite $85K GBV.
- **Travel:** no travel requirement found.
- **Attention:** Review Suggested only because GBV is within 15% of the $100K threshold, and growth signals exist (published [final results](https://www.tradingview.com/news/reuters.com,2026-06-29:newsml_RSc1346Ka:0-reg-focusrite-plc-final-results/)).

## P-033 Moorside Manufacturing Ltd: very little public information

- **Identity:** the name differs from the domain (`moorsideengineering.com`). It was confirmed through [Companies House 04936087](https://find-and-update.company-information.service.gov.uk/company/04936087) and the company's [own site](http://moorsideengineering.com/).
- **Headcount:** [Endole](https://open.endole.co.uk/insight/company/04936087-moorside-manufacturing-ltd) puts it under 10. This is consistent with enrichment (11).
- **Gaps:** no travel, hiring or funding evidence. Coverage shows these as *Not found* or *Stale*, never as "no travel". Outcome: no action.

## P-021 Balfour Beatty and P-041 Anthropic: Tier 1 controls

- Both have explicit travel requirements in job postings: [Balfour Beatty US](https://builtin.com/company/balfour-beatty-us/jobs) ("regional travel … is required"), and [Anthropic via Built In](https://builtin.com/company/anthropic/jobs) ("25–50% travel to customer sites").
- They already receive a dedicated AE and account manager, so the flag is **informational (Monitor)**. An earlier version sent them to Review Suggested; that was fixed after live testing (§9 of the experiments doc).

## P-002 Attio: growth is not travel

- **Growth:** a $52M Series B ([PR Newswire](https://www.prnewswire.com/news-releases/attio-raises-52m-series-b-to-scale-the-first-ai-native-crm-for-go-to-market-builders-302538357.html), August 2025), active hiring, US offices.
- **Travel:** no travel requirement found. The result is a low-severity Growth Opportunity: Monitor, with no tier change.
- **Day 30, for comparison only:** 6 travelers, 21 bookings, +80%. This is growing but below the review threshold, so it gets Review Suggested and still no proposal.

## Day 30 results on the 10 activity rows

What the rules do when the fictional Day 30 activity is received (checked in a fresh demo-mode run on
10 November 2026). Day 30 never proposes Tier 1, and the only proposal it can make is Tier 3 → Tier 2,
because booking counts are not dollars. The thresholds are prototype policies.


| Company | Activity | Day 30 effect |
|---|---|---|
| NexGen Cloud (T2) | 83 travelers, 318 bookings, +12% | Travel Potential (Day 30), no proposal |
| Greyparrot (T2) | 42 travelers, 151 bookings, +58% | Travel Potential (Day 30), no proposal |
| Puttshack (T2) | 44 travelers, 140 bookings, +42% | Travel Potential (Day 30), no proposal |
| IMU Biosciences (T2) | 19 travelers, 57 bookings, +62% | Travel Potential (Day 30), no new proposal; "strengthens" |
| Attio (T3) | 6 travelers, 21 bookings, +80% | Growth Opportunity, Review Suggested (below the review threshold) |
| Callosum, Metaview (T3) | 1–5 travelers, flat / −22% | Monitor |
| Bionical (T3) | 9 travelers, −35% | Recorded as **weakening** the Day 0 travel signal; stays Review Now for its headcount conflict |
| Valarian, Balfour Beatty (T1) | strong | Consistent with Tier 1, no action |

