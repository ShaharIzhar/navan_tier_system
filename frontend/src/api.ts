// Typed client for the FastAPI backend. All AI calls happen server-side.

export type Attention = 'review_now' | 'review_suggested' | 'monitor' | null

export interface Flag {
  type: string
  label: string
  severity: 'material' | 'moderate' | 'low'
  reasons: string[]
  evidence_ids: number[]
  uncertainty: string[]
  stage: 'day0' | 'day30'
}

export interface ProspectRow {
  id: string
  company_name: string
  domain: string
  entered_gbv_usd: number | null
  zi_employees: number | null
  original_tier: number | null
  applied_tier: number | null
  baseline_tier: number | null
  baseline_provisional: boolean | null
  attention: Attention
  attention_label: string
  priority_score: number
  priority: 'High' | 'Medium' | 'Low'
  primary_flag: string | null
  primary_flag_label: string | null
  flags: string[]
  review_status: string | null
  suggestion: { proposal_id: number; from_tier: number | null; to_tier: number; title: string; type: string; status: string } | null
  research_status: string
  stage: 'day0' | 'day30'
  day30_available: boolean
  data_quality_notes: string[]
}

export interface CoverageEntry {
  status: string
  summary: string | null
  run_id: number | null
  evidence_count: number
  manual: boolean
  synthetic: boolean
}

export interface EmployeeSource {
  value: number
  label: string
  origin: string
  reliability: string
  as_of: string | null
  evidence_id: number | null
  stale: boolean
  company_site?: boolean
  url?: string | null
}

export interface Assessment {
  id: number
  stage: 'day0' | 'day30'
  trigger: string
  created_at: string
  applied_tier: number | null
  baseline: {
    tier: number | null
    provisional: boolean
    basis: string
    unresolved: string[]
    data_quality_issues: string[]
  }
  accepted_values: {
    gbv_usd: number | null
    employees: number | null
    employee_source: string | null
    research_employees: number | null
    employee_sources: EmployeeSource[]
    headcount_history: { date: string; value: number; label: string }[]
    near_threshold: string | null
    research_ran: boolean
    research_failed_last: boolean
    deep_research: { suggested: boolean; reason: string }
    suppressed_proposals: { title: string; reason: string }[]
  }
  flags: Flag[]
  attention: Attention
  attention_label: string
  priority: string
  priority_reasons: string[]
  primary_flag: string | null
  primary_flag_label: string | null
  recommended_action: string
  coverage: Record<string, CoverageEntry>
  day30: null | {
    travelers: number | null
    bookings: number | null
    trend_pct: number | null
    comparison: string
    notes: string[]
    material: boolean
    compared_with_assessment_id: number | null
  }
  proposal_ids: number[]
}

export interface Evidence {
  id: number
  run_id: number | null
  field: string
  claim: string
  value_number: number | null
  signal_type: string
  observation: string
  travel_scope: string | null
  source_title: string | null
  source_url: string | null
  publisher: string | null
  published_date: string | null
  retrieved_at: string | null
  reliability: string
  origin: string
  is_stale: boolean
  accepted_for_reassessment: boolean
  entered_by: string | null
  note: string | null
  superseded_by: string | null
  created_at: string
}

export interface ResearchRun {
  id: number
  kind: 'standard' | 'deep'
  status: string
  stage?: string
  replayed: boolean
  prompt_version: string
  model: string
  focus_fields: string[] | null
  started_at: string
  finished_at: string | null
  research_cutoff: string
  input_tokens: number
  output_tokens: number
  web_search_requests: number
  llm_calls: number
  approx_cost_usd: number
  error: string | null
  summary: string | null
  limitations: string[]
  dropped_findings: { field: string; claim: string; source_url: string; reason: string }[]
  conflicts: { field: string; description: string }[]
  search_result_count: number
}

export interface Proposal {
  id: number
  prospect_id: string
  company_name?: string
  assessment_id: number
  stage: string
  proposal_type: 'standard_rule_correction' | 'evidence_override'
  from_tier: number | null
  proposed_tier: number
  title: string
  basis: Record<string, unknown> | null
  rationale: string[]
  evidence_ids: number[]
  uncertainties: string[]
  linked_assessment_ids: number[]
  status: string
  status_label: string
  created_at: string
  updated_at: string
}

export interface AuditRow {
  id: number
  entity_type: string
  entity_id: string | null
  action: string
  actor: string
  details: Record<string, unknown>
  created_at: string
}

export interface HistoryRow {
  id: number
  stage: string
  trigger: string
  created_at: string
  applied_tier: number | null
  baseline_tier: number | null
  attention: Attention
  flags: string[]
  accepted_employees?: number | null
}

export interface ProspectDetail {
  prospect: ProspectRow
  assessment: Assessment | null
  history: HistoryRow[]
  evidence: Evidence[]
  research_runs: ResearchRun[]
  proposals: Proposal[]
  day30: { received: boolean; exists?: boolean; released_at?: string | null; raw_text?: string; travelers?: number; bookings?: number; trend_pct?: number }
  day30_pending: boolean
  audit: AuditRow[]
}

export interface ProposalDetail {
  proposal: Proposal
  prospect: ProspectRow
  evidence: Evidence[]
  assessment_at_creation: Assessment | null
  current_assessment: Assessment | null
  history: HistoryRow[]
  decisions: { id: number; action: string; reviewer: string; comment: string | null; tier_before: number | null; tier_after: number | null; created_at: string }[]
  audit: AuditRow[]
}

export interface Meta {
  provider: { configured: boolean; mode: 'live' | 'replay' | 'off'; recorded_companies: string[]; model: string; web_search_tool: string; standard_max_searches: number; deep_max_searches: number; prompt_version: string }
  research_fields: Record<string, string>
  flag_labels: Record<string, string>
  attention_labels: Record<string, string>
  thresholds: Record<string, number>
}

export interface Judgement {
  status: 'ok' | 'failed'
  summary?: string
  support?: 'strong' | 'partial' | 'weak'
  main_doubt?: string
  grounded?: boolean
  ungrounded_numbers?: string[]
  error?: string
  model: string
  created_at: string
  approx_cost_usd?: number
  replayed?: boolean
  from_cache: boolean
}


async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`/api${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...init,
  })
  if (!res.ok) {
    let detail = `${res.status} ${res.statusText}`
    try {
      const body = await res.json()
      if (body?.detail) detail = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail)
    } catch {
      /* keep status text */
    }
    throw new Error(detail)
  }
  return res.json() as Promise<T>
}

const post = <T>(path: string, body: unknown = {}) => request<T>(path, { method: 'POST', body: JSON.stringify(body) })

export const api = {
  meta: () => request<Meta>('/meta'),
  prospects: () => request<ProspectRow[]>('/prospects'),
  prospect: (id: string) => request<ProspectDetail>(`/prospects/${id}`),
  research: (id: string, force = false, actor = 'user') => post<ResearchRun>(`/prospects/${id}/research`, { force, actor }),
  deepResearch: (id: string, actor: string, focus_fields?: string[]) =>
    post<ResearchRun>(`/prospects/${id}/deep-research`, { confirm: true, actor, focus_fields }),
  enrich: (id: string, body: { param: string; value: string; entered_by: string; source_url?: string; note?: string; verified: boolean; accepted: boolean }) =>
    post<{ before: Assessment | null; after: Assessment; llm_calls: number }>(`/prospects/${id}/enrichment`, body),
  withdraw: (evidenceId: number, actor: string, reason: string) => post<Evidence>(`/evidence/${evidenceId}/withdraw`, { actor, reason }),
  releaseDay30: (id: string) => post<Assessment>(`/prospects/${id}/day30/release`),
  updateDay30: (id: string, body: { travelers: number; bookings: number; trend_pct: number | null; actor: string }) =>
    request<Assessment>(`/prospects/${id}/day30`, { method: 'PUT', body: JSON.stringify(body) }),
  removeDay30: (id: string, actor: string) => request<Assessment>(`/prospects/${id}/day30?actor=${encodeURIComponent(actor)}`, { method: 'DELETE' }),
  activeResearch: (id: string) =>
    request<{ running: boolean; run?: ResearchRun; expected_seconds?: number; last?: ResearchRun | null }>(`/prospects/${id}/active-research`),
  releaseAllDay30: () => post<{ released: string[] }>('/day30/release-all'),
  proposals: (status?: string) => request<Proposal[]>(`/proposals${status ? `?status=${status}` : ''}`),
  proposal: (id: number) => request<ProposalDetail>(`/proposals/${id}`),
  decide: (id: number, action: string, reviewer: string, comment?: string) =>
    post<Proposal>(`/proposals/${id}/decision`, { action, reviewer, comment }),
  judge: (id: number, force = false) => post<Judgement>(`/proposals/${id}/judge${force ? '?force=true' : ''}`),
}
