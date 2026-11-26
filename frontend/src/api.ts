const API_BASE = (import.meta.env.VITE_API_BASE_URL || '/api/v1').replace(/\/$/, '')

let accessToken: string | null = null
let refreshToken: string | null = null
let refreshInFlight: Promise<boolean> | null = null

export class ApiError extends Error {
  readonly status: number

  constructor(message: string, status: number) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

export function getSessionToken() {
  return accessToken
}

export function clearSession() {
  accessToken = null
  refreshToken = null
}

async function renewSession() {
  if (!refreshToken) return false
  if (!refreshInFlight) {
    const currentRefreshToken = refreshToken
    refreshInFlight = fetch(`${API_BASE}/auth/refresh`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: currentRefreshToken }),
    })
      .then(async (response) => {
        if (!response.ok) return false
        const tokens = (await response.json()) as TokenResponse
        accessToken = tokens.access_token
        refreshToken = tokens.refresh_token
        return true
      })
      .catch((error: unknown) => {
        clearSession()
        throw error
      })
      .finally(() => {
        refreshInFlight = null
      })
  }
  const renewed = await refreshInFlight
  if (!renewed) clearSession()
  return renewed
}

async function request<T>(path: string, init: RequestInit = {}, canRenew = true): Promise<T> {
  const headers = new Headers(init.headers)
  if (accessToken) headers.set('Authorization', `Bearer ${accessToken}`)
  if (
    init.body !== undefined &&
    !(init.body instanceof FormData) &&
    !(init.body instanceof URLSearchParams) &&
    !headers.has('Content-Type')
  ) {
    headers.set('Content-Type', 'application/json')
  }

  const response = await fetch(`${API_BASE}${path}`, { ...init, headers })
  if (
    response.status === 401 &&
    canRenew &&
    refreshToken &&
    path !== '/auth/login' &&
    path !== '/auth/refresh'
  ) {
    if (await renewSession()) return request<T>(path, init, false)
  }

  if (!response.ok) {
    let message = `Request failed (${response.status})`
    try {
      const payload = (await response.json()) as { detail?: unknown; message?: unknown }
      const detail = payload.detail ?? payload.message
      if (typeof detail === 'string') message = detail
      else if (detail !== undefined) message = JSON.stringify(detail)
    } catch {
      // Keep the HTTP status as the actionable fallback for non-JSON responses.
    }
    if (response.status === 401) clearSession()
    throw new ApiError(message, response.status)
  }
  if (response.status === 204) return undefined as T
  return (await response.json()) as T
}

export async function login(username: string, password: string) {
  const body = new URLSearchParams({ username, password })
  const tokens = await request<TokenResponse>('/auth/login', { method: 'POST', body })
  accessToken = tokens.access_token
  refreshToken = tokens.refresh_token
}

export function getUser() {
  return request<User>('/auth/me')
}

export function getDashboard() {
  return request<Dashboard>('/dashboard/overview')
}

export function getFacultyList(search = '') {
  const params = new URLSearchParams({ page: '1', page_size: '50' })
  if (search) params.set('search', search)
  return request<Paginated<Faculty>>(`/faculty?${params}`)
}

export function getFacultyProfile(id: string) {
  return request<Faculty>(`/faculty/${encodeURIComponent(id)}`)
}

export function getFacultyDashboard(id: string) {
  return request<FacultySummary>(`/dashboard/faculty/${encodeURIComponent(id)}`)
}

export function getFacultyPublications(id: string) {
  return request<Paginated<Publication>>(`/faculty/${encodeURIComponent(id)}/publications?page=1&page_size=100`)
}

export function createFaculty(input: FacultyInput) {
  return request<FacultyCreated>('/faculty', { method: 'POST', body: JSON.stringify(input) })
}

export function previewFacultyImport(file: File) {
  const form = new FormData()
  form.append('file', file)
  return request<ImportPreview>('/faculty/import/preview', { method: 'POST', body: form })
}

export function importFaculty(file: File) {
  const form = new FormData()
  form.append('file', file)
  return request<ImportResult>('/faculty/import/commit', { method: 'POST', body: form })
}

export function startDiscovery(id: string) {
  return request<Job>(`/faculty/${encodeURIComponent(id)}/discover`, { method: 'POST' })
}

export function getJobs(page = 1) {
  return request<Paginated<Job>>(`/discovery-jobs?page=${page}&page_size=20`)
}

export function getReviews(page = 1, status = 'pending') {
  const params = new URLSearchParams({ page: String(page), page_size: '20', status })
  return request<Paginated<Review>>(`/reviews?${params}`)
}

export function decideReview(id: string, decision: 'accept' | 'reject' | 'defer', rationale?: string) {
  return request<Review>(`/reviews/${encodeURIComponent(id)}/decision`, {
    method: 'POST',
    body: JSON.stringify({ decision, rationale }),
  })
}

export function getConnectors() {
  return request<Connector[]>('/connectors/status')
}

export function searchOpenAlexAuthors(name: string) {
  const params = new URLSearchParams({ name })
  return request<OpenAlexAuthorSearch>(`/search/authors?${params}`)
}

export function searchOpenAlexOrcid(orcid: string) {
  return request<OpenAlexAuthorSearch>(`/search/orcid/${encodeURIComponent(orcid)}`)
}

export function getOpenAlexWorks(authorId: string, page: number, perPage = 25) {
  const params = new URLSearchParams({ page: String(page), per_page: String(perPage) })
  return request<OpenAlexWorksPage>(`/authors/${encodeURIComponent(authorId)}/works?${params}`)
}

export interface TokenResponse {
  access_token: string
  refresh_token: string
  token_type: string
}

export interface User {
  id: string
  tenant_id: string
  email: string
  username: string
  full_name: string
  role: string
  is_active: boolean
}

export interface Paginated<T> {
  items: T[]
  total: number
  page: number
  page_size: number
  pages: number
}

export interface FacultyInput {
  full_name: string
  reported_institution?: string | null
  department?: string | null
  institutional_email?: string | null
  profile_url?: string | null
  research_interests_text?: string | null
  orcid?: string | null
  name_variants?: string[]
}

export interface Faculty {
  id: string
  full_name: string
  reported_institution: string | null
  department: string | null
  profile_url: string | null
  research_interests_text: string | null
  is_demo: boolean
  demo_label: string | null
  identifiers: Array<{ id: string; identifier_type: string; value: string; is_verified: boolean }>
  name_variants: Array<{ id: string; variant_name: string; source?: string | null }>
  affiliations: Array<{ id: string; organization: string; department?: string | null; is_current: boolean; source?: string | null }>
}

export interface FacultyCreated extends Faculty {
  discovery_job: Job
}

export interface FacultySummary {
  faculty: Faculty
  publication_count: number
  latest_job: Job | null
}

export interface Job {
  id: string
  faculty_id: string
  status: string
  trigger_type: string
  summary: string | null
  error_detail: string | null
  created_at: string
  started_at: string | null
  completed_at: string | null
  connector_runs: Array<{
    id: string
    provider: string
    status: string
    records_fetched: number
    records_valid: number
    records_quarantined: number
    error_message: string | null
    warnings: unknown[] | null
  }>
}

export interface Connector {
  provider: string
  display_name: string
  is_enabled: boolean
  is_configured: boolean
  health_status: string | null
  last_health_check: string | null
  capabilities: Record<string, boolean> | null
  terms_url: string | null
}

export interface Dashboard {
  total_faculty: number
  total_publications: number
  pending_reviews: number
  recent_jobs: Job[]
  connector_statuses: Connector[]
  publication_years: Record<string, number>
}

export interface Review {
  id: string
  review_type: string
  entity_type: string
  entity_id: string
  status: string
  priority: number
  evidence: Record<string, unknown> | null
  explanation: string | null
  decision: string | null
  created_at: string
}

export interface Publication {
  id: string
  title: string
  doi: string | null
  publication_year: number | null
  venue: string | null
  publication_type: string | null
  landing_url: string | null
  match_status: string | null
  confidence_score: number | null
  authorships: Array<{ id: string; author_name: string; author_position: number | null }>
  sources: Array<{
    id: string
    provider: string
    source_title: string | null
    source_url: string | null
    retrieved_at: string | null
  }>
}

export interface OpenAlexAuthor {
  id: string
  name: string
  orcid: string | null
  affiliation: string | null
  works_count: number | null
  cited_by_count: number | null
  source_url: string
  identity_status: 'possible_name_match' | 'provider_identifier_matched'
}

export interface OpenAlexAuthorSearch {
  results: OpenAlexAuthor[]
  count: number
  source: string
  retrieved_at: string
  warnings: string[]
}

export interface OpenAlexWork {
  title: string
  doi: string | null
  publication_year: number | null
  venue: string | null
  publication_type: string | null
  landing_url: string | null
  source_url: string
  citation_count: number | null
  authors: Array<{ name: string; orcid: string | null }>
}

export interface OpenAlexWorksPage {
  results: OpenAlexWork[]
  count: number
  pagination: { page: number; next_page?: number; has_more: boolean; limit_reached?: boolean } | null
  page: number
  source: string
  retrieved_at: string
}

export interface ImportPreview {
  total_rows: number
  valid_rows: number
  invalid_rows: number
  duplicate_rows: number
  rows: Array<{
    row_number: number
    data: Record<string, unknown>
    is_valid: boolean
    errors: string[]
  }>
}

export interface ImportResult {
  imported_count: number
  skipped_count: number
  error_count: number
  discovery_jobs: Job[]
}
