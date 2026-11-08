# System flowchart

Blue = deterministic code, purple = AI (LLM + web search), green = human decision. Nothing on the AI path can change a tier.

```mermaid
flowchart TD
    A[Company signs up<br/>name, domain, reported GBV, enrichment headcount] --> B[Import & normalise<br/>parse $ values, keep Day 30 data locked away]
    B --> C[Baseline tier rules<br/>GBV ≥ $500K → T1<br/>GBV ≥ $100K or 150+ employees → T2<br/>else T3 · provisional if headcount unknown]
    C --> D{Standard research<br/>enabled for this company?}
    D -- no --> F
    D -- yes --> E[AI research<br/>Claude Haiku + web search<br/>8 fields, name + domain only]
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
    M -- Request info --> P[Proposal stays open]
    P --> Q[Manual enrichment<br/>or Deep Research on request]
    L --> Q
    Q -- rules only, 0 AI calls --> F
    Q -- Deep Research, confirmed --> E

    R[Day 30 activity received<br/>travelers, bookings, trend] --> S[Lightweight reassessment<br/>compare with Day 0 assessment<br/>bookings ≠ GBV]
    S --> G
    S -.-> T[(Day 0 assessment<br/>kept unchanged)]

    classDef det fill:#eef0fd,stroke:#3c4fe0,color:#1b1f27;
    classDef ai fill:#f2edfc,stroke:#6b3fc8,color:#1b1f27;
    classDef human fill:#e8f6ee,stroke:#18794e,color:#1b1f27;
    class B,C,E2,E3,F,G,H,I,J,K,S,T det;
    class E ai;
    class M,N,O,P,Q human;
```

## Key decisions shown in the chart

| Decision point | Rule | Why |
|---|---|---|
| Which inputs the AI sees | Company name + domain only | Research stays independent of the reported GBV, and Day 30 data cannot leak into it |
| What the AI may output | Findings with source URLs, field statuses, conflicts | The AI interprets evidence; it never assigns tiers or flags |
| Citation check | URL must be among the search results actually returned in that run | Prevents fabricated sources reaching the UI |
| Research headcount vs enrichment | Research never silently replaces the enrichment value; disagreement becomes a Data Conflict | Keeps a human in charge of the value that drives the tier |
| Conflict severity | "Material" only when the sources straddle 150 **and** GBV is below $100K | That is the only case where headcount decides the tier |
| Travel Potential | Needs direct evidence (job ads requiring travel, field or client-site work). Aggregator-only or inferred evidence does not count | Growth is not travel |
| Tier 3 → Tier 2 override | Direct travel evidence from 2+ independent sources | One source is enough to suggest a look, not a re-route |
| Day 30 proposal | At most one tier up, always typed as an override | Bookings are not dollars |
| After a rejection | The same proposal is not raised again unless new evidence appears | Avoids nagging reviewers |
