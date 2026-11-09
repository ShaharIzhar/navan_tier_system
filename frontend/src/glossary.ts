// Short, plain-language hover texts for salespeople. One line each.

export const GLOSSARY: Record<string, string> = {
  // Tiers
  applied_tier: 'Current tier. Changes only when someone approves.',
  baseline_tier: 'Standard rules: $500K+ GBV = T1 · $100K+ or 150+ staff = T2 · else T3.',
  original_tier: 'Tier from the original signup data.',
  provisional: 'Headcount unknown, so Tier 2 is still possible.',
  tier1: 'Tier 1: dedicated AE + account manager.',
  tier2: 'Tier 2: AE helps with launch.',
  tier3: 'Tier 3: self-serve.',

  // Attention
  review_now: 'Needs a decision now.',
  review_suggested: 'Worth a look, not urgent.',
  monitor: 'Keep an eye on it.',
  no_action: 'Nothing to do.',
  priority: 'Ranked by impact, evidence and how easy it is to act on.',

  // Flags
  tier_mismatch: 'Evidence points to a different tier.',
  data_conflict: 'Sources disagree.',
  travel_potential: 'Job ads or pages say staff travel for work.',
  growth_opportunity: 'Funding, hiring or expansion. Not proof of more travel.',
  insufficient_evidence: 'Key facts are missing.',

  // Severity
  material: 'Strong: can change the tier.',
  moderate: 'Worth checking.',
  low: 'FYI only.',

  // Research coverage
  found: 'Found, with a source.',
  not_found: 'Searched, nothing found.',
  not_searched: 'Not checked yet.',
  conflicting: 'Sources disagree.',
  stale: 'Older than 18 months.',
  not_applicable: 'Doesn’t apply.',

  // Source types
  primary: 'Company site or official registry.',
  secondary: 'Independent source (news, job board).',
  aggregator: 'Data-provider estimate (LinkedIn, PitchBook…).',
  manual_verified: 'Added by a person, source checked.',
  manual_unverified: 'Added by a person, no source.',
  synthetic: 'Test data, not real.',

  // Proposal types
  standard_rule_correction: 'The standard rules give a different tier.',
  evidence_override: 'Goes against the standard rules, based on evidence.',

  // Misc
  deep_research: 'A more thorough search, including travel requirements.',
  day30: 'First 30 days on Navan. Bookings aren’t dollars.',
}

export const g = (key: string | null | undefined) => (key ? GLOSSARY[key] ?? '' : '')
