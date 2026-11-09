import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import ReviewQueue from '../pages/ReviewQueue'
import CompanyDetail from '../pages/CompanyDetail'
import TierReview from '../pages/TierReview'
import { ConfirmProvider } from '../components/confirm'

const row = (over: Record<string, unknown>) => ({
  id: 'P-007', company_name: 'IMU Biosciences', domain: 'imubiosciences.com', entered_gbv_usd: 48000, zi_employees: 155,
  original_tier: 2, applied_tier: 2, baseline_tier: 2, baseline_provisional: false, attention: 'review_now',
  attention_label: 'Review Now', priority_score: 40, priority: 'High', primary_flag: 'data_conflict',
  primary_flag_label: 'Data Conflict', flags: ['data_conflict'], review_status: 'Awaiting review',
  research_status: 'ok', stage: 'day0', day30_available: false, data_quality_notes: [], ...over,
})

const assessment = {
  id: 5, stage: 'day0', trigger: 'research', created_at: '2026-11-08T10:00:00', applied_tier: 2,
  baseline: { tier: 2, provisional: false, basis: 'Reported GBV $48,000 is below $100,000, but 155 employees meets the 150+ employee rule.', unresolved: [], data_quality_issues: [] },
  accepted_values: {
    gbv_usd: 48000, employees: 155, employee_source: 'Enrichment estimate (dataset)', research_employees: 90,
    employee_sources: [
      { value: 155, label: 'Enrichment estimate (dataset)', origin: 'dataset', reliability: 'enrichment', as_of: null, evidence_id: null, stale: false },
      { value: 90, label: 'SYNTHETIC test observation', origin: 'synthetic_test', reliability: 'synthetic', as_of: null, evidence_id: 1, stale: false },
    ],
    headcount_history: [], near_threshold: 'Headcount 155 is close to the 150-employee Tier 2 threshold.', research_ran: true,
    research_failed_last: false, deep_research: { suggested: true, reason: 'A source conflict decides Tier 2 eligibility.' }, suppressed_proposals: [],
  },
  flags: [{ type: 'data_conflict', label: 'Data Conflict', severity: 'material', reasons: ['Employee sources fall on both sides of 150.'], evidence_ids: [1], uncertainty: ['Includes a SYNTHETIC test observation, not public research.'], stage: 'day0' }],
  attention: 'review_now', attention_label: 'Review Now', priority: 'High', priority_reasons: [], primary_flag: 'data_conflict',
  primary_flag_label: 'Data Conflict', recommended_action: 'Review the standard-rule correction proposal: Tier 2 → Tier 3.',
  coverage: {
    employee_count: { status: 'conflicting', summary: null, run_id: 1, evidence_count: 1, manual: false, synthetic: true },
    travel_indicators: { status: 'not_found', summary: null, run_id: 1, evidence_count: 0, manual: false, synthetic: false },
  },
  day30: null, proposal_ids: [9],
}

const proposal = {
  id: 9, prospect_id: 'P-007', assessment_id: 5, stage: 'day0', proposal_type: 'standard_rule_correction', from_tier: 2,
  proposed_tier: 3, title: 'Research headcount implies Tier 3 under standard rules (currently Tier 2)', basis: { employee_source: 'research' },
  rationale: ['Research headcount 90.'], evidence_ids: [1], uncertainties: ['Research headcount includes a SYNTHETIC test observation.'],
  linked_assessment_ids: [5], status: 'open', status_label: 'Awaiting review', created_at: '2026-11-08T10:00:00', updated_at: '2026-11-08T10:00:00',
}

function mockFetch(routes: Record<string, unknown>) {
  const calls: { url: string; init?: RequestInit }[] = []
  vi.stubGlobal('fetch', vi.fn(async (url: string, init?: RequestInit) => {
    calls.push({ url, init })
    const key = Object.keys(routes).find((k) => url.startsWith(k))
    return { ok: true, status: 200, statusText: 'OK', json: async () => (key ? routes[key] : {}) } as Response
  }))
  return calls
}

beforeEach(() => localStorage.setItem('ngi.reviewer', 'Sam'))
afterEach(() => {
  vi.unstubAllGlobals()
  localStorage.clear()
})

describe('Review queue', () => {
  it('renders the three attention tabs and filters rows', async () => {
    mockFetch({ '/api/prospects': [row({}), row({ id: 'P-002', company_name: 'Attio', attention: 'review_suggested', attention_label: 'Review Suggested' })] })
    render(<MemoryRouter><ReviewQueue /></MemoryRouter>)
    expect(await screen.findByText('IMU Biosciences')).toBeInTheDocument()
    const tabs = screen.getAllByRole('tab')
    expect(tabs.map((t) => t.textContent?.replace(/\d+$/, ''))).toEqual(['Review Now', 'Review Suggested', 'Monitor'])
    expect(screen.queryByText('Attio')).not.toBeInTheDocument()
    await userEvent.click(tabs[1])
    expect(screen.getByText('Attio')).toBeInTheDocument()
  })
})

describe('Company detail', () => {
  it('shows tiers, flags, coverage and the synthetic warning', async () => {
    mockFetch({
      '/api/prospects/P-007': {
        prospect: row({}), assessment, history: [], proposals: [proposal], research_runs: [],
        evidence: [{ id: 1, run_id: null, field: 'employee_count', claim: '[SYNTHETIC TEST] 90 employees', value_number: 90, signal_type: 'descriptive', observation: 'observed', travel_scope: null, source_title: null, source_url: null, publisher: 'Synthetic', published_date: null, retrieved_at: null, reliability: 'synthetic', origin: 'synthetic_test', is_stale: false, accepted_for_reassessment: false, entered_by: 't', note: null, superseded_by: null, created_at: '2026-11-08T10:00:00' }],
        day30: { received: false, exists: false }, day30_pending: false, audit: [],
      },
    })
    render(
      <MemoryRouter initialEntries={['/companies/P-007']}>
        <Routes><Route path="/companies/:id" element={<CompanyDetail />} /></Routes>
      </MemoryRouter>,
    )
    expect(await screen.findByRole('heading', { name: /IMU Biosciences/ })).toBeInTheDocument()
    expect(screen.getByText('test data', { selector: 'strong' })).toBeInTheDocument()
    expect(screen.getAllByText('Data Conflict').length).toBeGreaterThan(0)
    expect(screen.getByText('Conflicting')).toBeInTheDocument()
    expect(screen.getByText('Not found')).toBeInTheDocument()
    expect(screen.getByText(/Deep Research suggested/)).toBeInTheDocument()
  })
})

describe('Tier review', () => {
  it('requires a comment to reject and posts the decision', async () => {
    const calls = mockFetch({
      '/api/proposals/9/decision': { ...proposal, status: 'rejected' },
      '/api/proposals/9/judge': { status: 'ok', summary: 'Downgrade: Tier 2 rests only on 155 employees; sources say 90.', support: 'weak', main_doubt: 'The 90 figure is synthetic', grounded: true, model: 'claude-haiku-5-5', created_at: '2026-11-09T08:00:00', from_cache: false },
      '/api/proposals/9': {
        proposal, prospect: row({}), evidence: [], assessment_at_creation: assessment, current_assessment: assessment,
        linked_assessments: [], history: [], decisions: [], audit: [],
      },
    })
    render(
      <MemoryRouter initialEntries={['/reviews/9']}>
        <Routes><Route path="/reviews/:id" element={<TierReview />} /></Routes>
      </MemoryRouter>,
    )
    expect(await screen.findByText(/Tier 2 rests only on 155 employees/)).toBeInTheDocument()
    expect(screen.getByText('Weakly supported')).toBeInTheDocument()
    const reject = await screen.findByRole('button', { name: 'Reject' })
    expect(reject).toBeDisabled()
    expect(screen.getByRole('button', { name: /Approve Tier 3/ })).toBeEnabled()
    await userEvent.type(screen.getByLabelText('Review comment'), 'Synthetic source only')
    expect(reject).toBeEnabled()
    await userEvent.click(reject)
    await waitFor(() => expect(calls.some((c) => c.url === '/api/proposals/9/decision')).toBe(true))
    const body = JSON.parse(String(calls.find((c) => c.url === '/api/proposals/9/decision')!.init!.body))
    expect(body).toEqual({ action: 'reject', reviewer: 'Sam', comment: 'Synthetic source only' })
    expect(within(document.body).getByText('Standard-rule correction')).toBeInTheDocument()
  })
})

describe('Inline value correction', () => {
  it('edits the employee count in place and saves through the enrichment API', async () => {
    const calls = mockFetch({
      '/api/prospects/P-007/enrichment': { before: assessment, after: assessment, llm_calls: 0 },
      '/api/prospects/P-007': {
        prospect: row({}), assessment, history: [], proposals: [], research_runs: [], evidence: [],
        day30: { received: false, exists: false }, day30_pending: false, audit: [],
      },
    })
    render(
      <MemoryRouter initialEntries={['/companies/P-007']}>
        <Routes><Route path="/companies/:id" element={<CompanyDetail />} /></Routes>
      </MemoryRouter>,
    )
    await userEvent.click(await screen.findByRole('button', { name: 'Edit employees' }))
    await userEvent.type(screen.getByLabelText('Correct employee count'), '85')
    await userEvent.click(screen.getByRole('button', { name: /Save/ }))
    await waitFor(() => expect(calls.some((c) => c.url === '/api/prospects/P-007/enrichment')).toBe(true))
    const body = JSON.parse(String(calls.find((c) => c.url.endsWith('/enrichment'))!.init!.body))
    expect(body).toMatchObject({ param: 'employee_count', value: '85', entered_by: 'Sam', accepted: true, verified: false })
    expect(await screen.findByText(/Rules rerun with no AI call/)).toBeInTheDocument()
  })
})

describe('Company website source', () => {
  it('shows a verified check only for figures from the company domain', async () => {
    const ev = (id: number, url: string) => ({
      id, run_id: 1, field: 'employee_count', claim: `claim ${id}`, value_number: id === 1 ? 160 : 25, signal_type: 'descriptive',
      observation: 'observed', travel_scope: null, source_title: null, source_url: url, publisher: null, published_date: null,
      retrieved_at: null, reliability: id === 1 ? 'primary' : 'aggregator', origin: 'ai_research', is_stale: false,
      accepted_for_reassessment: false, entered_by: null, note: null, superseded_by: null, created_at: '2026-11-08T10:00:00',
    })
    const a = {
      ...assessment,
      accepted_values: {
        ...assessment.accepted_values,
        employee_sources: [
          { value: 155, label: 'Enrichment estimate (dataset)', origin: 'dataset', reliability: 'enrichment', as_of: null, evidence_id: null, stale: false },
          { value: 160, label: 'Company website (imubiosciences.com)', origin: 'ai_research', reliability: 'primary', as_of: null, evidence_id: 1, stale: false, company_site: true, url: 'https://www.imubiosciences.com/about' },
          { value: 25, label: 'PitchBook', origin: 'ai_research', reliability: 'aggregator', as_of: null, evidence_id: 2, stale: false },
        ],
      },
    }
    mockFetch({
      '/api/prospects/P-007': {
        prospect: row({}), assessment: a, history: [], proposals: [], research_runs: [],
        evidence: [ev(1, 'https://www.imubiosciences.com/about'), ev(2, 'https://pitchbook.com/profiles/x')],
        day30: { received: false, exists: false }, day30_pending: false, audit: [],
      },
    })
    render(
      <MemoryRouter initialEntries={['/companies/P-007']}>
        <Routes><Route path="/companies/:id" element={<CompanyDetail />} /></Routes>
      </MemoryRouter>,
    )
    await screen.findByRole('heading', { name: /IMU Biosciences/ })
    const checks = screen.getAllByLabelText("From the company's own website")
    expect(checks).toHaveLength(1)
    expect(checks[0].closest('.badge')?.textContent).toContain('160')
  })
})

describe('Figure to evidence', () => {
  it('clicking a research figure opens the field and highlights the finding', async () => {
    const a = {
      ...assessment,
      coverage: { ...assessment.coverage, employee_count: { status: 'found', summary: null, run_id: 1, evidence_count: 1, manual: false, synthetic: false } },
      accepted_values: {
        ...assessment.accepted_values,
        employee_sources: [
          { value: 155, label: 'Enrichment estimate (dataset)', origin: 'dataset', reliability: 'enrichment', as_of: null, evidence_id: null, stale: false },
          { value: 53, label: 'Built In London', origin: 'ai_research', reliability: 'secondary', as_of: null, evidence_id: 7, stale: false, url: 'https://builtinlondon.uk/x' },
        ],
      },
    }
    const ev = { id: 7, run_id: 1, field: 'employee_count', claim: 'Built In London lists 53 employees.', value_number: 53, signal_type: 'descriptive',
      observation: 'observed', travel_scope: null, source_title: 'Built In', source_url: 'https://builtinlondon.uk/x', publisher: null, published_date: null,
      retrieved_at: null, reliability: 'secondary', origin: 'ai_research', is_stale: false, accepted_for_reassessment: false, entered_by: null,
      note: null, superseded_by: null, created_at: '2026-11-08T10:00:00' }
    mockFetch({
      '/api/prospects/P-007': {
        prospect: row({}), assessment: a, history: [], proposals: [], research_runs: [], evidence: [ev],
        day30: { received: false, exists: false }, day30_pending: false, audit: [],
      },
    })
    Element.prototype.scrollIntoView = vi.fn()
    render(
      <MemoryRouter initialEntries={['/companies/P-007']}>
        <Routes><Route path="/companies/:id" element={<CompanyDetail />} /></Routes>
      </MemoryRouter>,
    )
    await userEvent.click(await screen.findByRole('button', { name: 'Show evidence for 53' }))
    const item = await screen.findByText('Built In London lists 53 employees.')
    expect(item.closest('.evidence-item')).toHaveClass('highlight')
  })
})

describe('Companies table', () => {
  it('sorts by a column and shows a suggested tier arrow', async () => {
    const { default: Companies } = await import('../pages/Companies')
    mockFetch({
      '/api/prospects': [
        row({ id: 'P-001', company_name: 'Beta', entered_gbv_usd: 10000, suggestion: null }),
        row({ id: 'P-002', company_name: 'Alpha', entered_gbv_usd: 90000, suggestion: { proposal_id: 4, from_tier: 2, to_tier: 1, title: 'Day 30 activity', type: 'evidence_override', status: 'open' } }),
      ],
    })
    render(<MemoryRouter><Companies /></MemoryRouter>)
    await screen.findByText('Alpha')
    expect(screen.getByLabelText('Suggested Tier 1')).toHaveTextContent('↑T1')
    expect(screen.queryByText('Review')).not.toBeInTheDocument()
    expect(screen.queryByText('Rules say')).not.toBeInTheDocument()
    const names = () => screen.getAllByRole('row').slice(1).map((r) => r.querySelector('strong')?.textContent)
    await userEvent.click(screen.getByRole('button', { name: /Company/ }))
    expect(names()).toEqual(['Alpha', 'Beta'])
    await userEvent.click(screen.getByRole('button', { name: /Reported GBV/ }))
    await userEvent.click(screen.getByRole('button', { name: /Reported GBV/ }))
    expect(names()).toEqual(['Alpha', 'Beta']) // GBV descending: 90K first
  })
})

describe('User menu', () => {
  it('defaults to Employee 23 and can be renamed', async () => {
    const { default: UserMenu } = await import('../components/UserMenu')
    localStorage.clear()
    render(<UserMenu />)
    await userEvent.click(screen.getByRole('button', { name: /Employee 23/ }))
    const input = screen.getByLabelText('Your name')
    await userEvent.clear(input)
    await userEvent.type(input, 'Dana Levi{Enter}')
    expect(screen.getByRole('button', { name: /Dana Levi/ })).toHaveTextContent('DL')
    expect(localStorage.getItem('ngi.reviewer')).toBe('Dana Levi')
  })
})


describe('Confirmations', () => {
  it('asks before approving a tier change and only posts after Confirm', async () => {
    const calls = mockFetch({
      '/api/proposals/9/decision': { ...proposal, status: 'approved' },
      '/api/proposals/9/judge': { status: 'failed', error: 'x', model: 'm', created_at: '2026-11-09T08:00:00', from_cache: false },
      '/api/proposals/9': {
        proposal, prospect: row({}), evidence: [], assessment_at_creation: assessment, current_assessment: assessment,
        linked_assessments: [], history: [], decisions: [], audit: [],
      },
    })
    render(
      <ConfirmProvider>
        <MemoryRouter initialEntries={['/reviews/9']}>
          <Routes><Route path="/reviews/:id" element={<TierReview />} /></Routes>
        </MemoryRouter>
      </ConfirmProvider>,
    )
    await userEvent.click(await screen.findByRole('button', { name: /Approve Tier 3/ }))
    const first = await screen.findByRole('dialog', { name: /Downgrade IMU Biosciences to Tier 3\?/ })
    expect(within(first).getByText(/mostly self-serve/)).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Cancel' }))
    expect(calls.some((c) => c.url.endsWith('/decision'))).toBe(false)

    await userEvent.click(screen.getByRole('button', { name: /Approve Tier 3/ }))
    const dialog = await screen.findByRole('dialog')
    await userEvent.click(within(dialog).getByRole('button', { name: 'Approve Tier 3' }))
    await waitFor(() => expect(calls.some((c) => c.url.endsWith('/decision'))).toBe(true))
  })

  it('asks before an employee edit that changes the rules tier', async () => {
    const calls = mockFetch({
      '/api/prospects/P-007/enrichment': { before: assessment, after: assessment, llm_calls: 0 },
      '/api/prospects/P-007': {
        prospect: row({}), assessment, history: [], proposals: [], research_runs: [], evidence: [],
        day30: { received: false, exists: false }, day30_pending: false, audit: [],
      },
    })
    render(
      <ConfirmProvider>
        <MemoryRouter initialEntries={['/companies/P-007']}>
          <Routes><Route path="/companies/:id" element={<CompanyDetail />} /></Routes>
        </MemoryRouter>
      </ConfirmProvider>,
    )
    await userEvent.click(await screen.findByRole('button', { name: 'Edit employees' }))
    await userEvent.type(screen.getByLabelText('Correct employee count'), '90')
    await userEvent.click(screen.getByRole('button', { name: /^Save$/ }))
    const dialog = await screen.findByRole('dialog', { name: /Change employees to 90\?/ })
    expect(within(dialog).getByText('Tier 3')).toBeInTheDocument()
    expect(calls.some((c) => c.url.endsWith('/enrichment'))).toBe(false)
    await userEvent.click(within(dialog).getByRole('button', { name: 'Save and rerun rules' }))
    await waitFor(() => expect(calls.some((c) => c.url.endsWith('/enrichment'))).toBe(true))
  })
})

describe('Day 30 editing', () => {
  it('opens the update dialog even when the section is collapsed, and expands it', async () => {
    localStorage.setItem('ngi.section.day30', '0') // collapsed
    const calls = mockFetch({
      '/api/prospects/P-007/day30': assessment,
      '/api/prospects/P-007': {
        prospect: row({}), assessment, history: [], proposals: [], research_runs: [], evidence: [],
        day30: { received: true, travelers: 19, bookings: 57, trend_pct: 62, remarks: null }, day30_pending: false, audit: [],
      },
    })
    render(
      <MemoryRouter initialEntries={['/companies/P-007']}>
        <Routes><Route path="/companies/:id" element={<CompanyDetail />} /></Routes>
      </MemoryRouter>,
    )
    await userEvent.click(await screen.findByRole('button', { name: /Update/ }))
    const dialog = await screen.findByRole('dialog', { name: 'Update Day 30 data' })
    expect(screen.getByText('travelers')).toBeInTheDocument() // section expanded
    await userEvent.type(within(dialog).getByLabelText('Remarks'), 'From finance export')
    await userEvent.click(within(dialog).getByRole('button', { name: 'Save' }))
    await waitFor(() => expect(calls.some((c) => c.url === '/api/prospects/P-007/day30')).toBe(true))
    const body = JSON.parse(String(calls.find((c) => c.url === '/api/prospects/P-007/day30')!.init!.body))
    expect(body).toMatchObject({ travelers: 19, bookings: 57, trend_pct: 62, remarks: 'From finance export' })
  })
})
