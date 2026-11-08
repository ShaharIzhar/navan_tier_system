// One place for every explanation shown on hover, so screens can stay short.

export const GLOSSARY: Record<string, string> = {
  // Tiers
  applied_tier: 'The tier the company has right now in this prototype. Only changes when a person approves a proposal.',
  baseline_tier: "What Navan's standard rules give: GBV ≥ $500K → Tier 1; GBV ≥ $100K or 150+ employees → Tier 2; otherwise Tier 3.",
  original_tier: 'The tier in the original dataset. Never changes, kept for comparison.',
  provisional: 'Provisional: GBV is under $100K and the employee count is unknown, so Tier 2 by headcount cannot be ruled out.',
  tier1: 'Tier 1 (Sales-led): dedicated AE and account manager.',
  tier2: 'Tier 2 (PLG Core): an AE helps with launch and adoption.',
  tier3: 'Tier 3 (Growth): mostly self-serve.',

  // Attention
  review_now: 'Review Now: a tier proposal is waiting, or a conflict decides which tier applies.',
  review_suggested: 'Review Suggested: worth a look (e.g. travel evidence, growth near a threshold), not urgent.',
  monitor: 'Monitor: weak signals only. No sales time needed yet.',
  no_action: 'No action: nothing found that needs attention.',
  priority: 'Order inside a tab: business impact first, then evidence strength, then how actionable it is. A prototype rule, not a prediction.',

  // Flags
  tier_mismatch: 'Tier Mismatch: the evidence suggests a different tier. This is the only flag that can create a tier proposal.',
  data_conflict: 'Data Conflict: sources disagree. "Material" when the disagreement decides the tier (e.g. employees on both sides of 150 while GBV < $100K).',
  travel_potential: 'Travel Potential: a source says employees travel for work (job ads, client-site work). Local driving or home visits do not count.',
  growth_opportunity: 'Growth Opportunity: funding, expansion or hiring. Growth is not proof of higher travel spend.',
  insufficient_evidence: 'Insufficient Evidence: an important fact could not be found. Missing info is not proof of "no travel".',

  // Severity
  material: 'Material: strong enough to affect routing.',
  moderate: 'Moderate: worth checking, does not change the tier on its own.',
  low: 'Low: informational.',

  // Research coverage
  found: 'Found: at least one source-backed finding.',
  not_found: 'Not found: searched, nothing usable.',
  not_searched: 'Not searched: research has not covered this yet.',
  conflicting: 'Conflicting: sources disagree.',
  stale: 'Stale: the evidence is older than 18 months.',
  not_applicable: 'Not applicable to this company.',

  // Reliability
  primary: "From the company's own site or an official registry.",
  secondary: 'From an independent source (news, job board).',
  aggregator: 'From a data aggregator (LinkedIn, PitchBook, ZoomInfo…). Usually an estimate.',
  manual_verified: 'Entered by a person and checked against a source.',
  manual_unverified: 'Entered by a person without a checked source.',
  synthetic: 'SYNTHETIC: fake observation added for a test. Never real research.',

  // Proposal types
  standard_rule_correction: "Standard-rule correction: applying Navan's rules to the accepted values gives a different tier.",
  evidence_override: 'Evidence-based override: the standard rules do not give this tier, but evidence suggests it. Approving overrides policy.',

  // Misc
  deep_research: 'A second, targeted research pass on missing or disputed fields. Costs extra and always asks first.',
  day30: 'Navan activity in the first 30 days after signup. Never used for the signup decision. Bookings are not dollars.',
  reported_vs_found: 'Reported = what the company or enrichment said at signup. Found = what public research shows. Used = the value the tier rules use.',
  scenario_checks: 'Automatic checks that the rules behave as specified. They do not measure real-world accuracy.',
  cost: 'Estimated from tokens and web searches at list prices. Rerunning the rules after a manual change costs nothing.',
  citation_validation: 'Findings citing a URL that the search did not actually return are removed automatically.',
  false_positives: 'Proposals a reviewer rejected. A reviewer can be wrong, so these are candidates to analyse, not proof.',
  false_negatives: 'Companies with strong Day 30 activity but no signup flag. A rough after-the-fact check only.',
  unsupported: 'Proposals with no cited evidence, or based only on aggregator, synthetic or guessed evidence.',
}

export const g = (key: string | null | undefined) => (key ? GLOSSARY[key] ?? '' : '')
