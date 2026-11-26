import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import App from './App'

const api = vi.hoisted(() => ({
  clearSession: vi.fn(),
  createFaculty: vi.fn(),
  decideReview: vi.fn(),
  getConnectors: vi.fn(),
  getDashboard: vi.fn(),
  getFacultyDashboard: vi.fn(),
  getFacultyList: vi.fn(),
  getFacultyProfile: vi.fn(),
  getFacultyPublications: vi.fn(),
  getJobs: vi.fn(),
  getReviews: vi.fn(),
  getSessionToken: vi.fn(),
  getUser: vi.fn(),
  importFaculty: vi.fn(),
  login: vi.fn(),
  previewFacultyImport: vi.fn(),
  startDiscovery: vi.fn(),
}))

vi.mock('./api', () => api)

describe('App authentication flow', () => {
  beforeEach(() => {
    api.getSessionToken.mockReturnValue(null)
    api.login.mockResolvedValue(undefined)
    api.getUser.mockResolvedValue({
      id: 'user-id',
      tenant_id: 'tenant-id',
      email: 'admin@example.edu',
      username: 'admin',
      full_name: 'Research Admin',
      role: 'admin',
      is_active: true,
    })
    api.getDashboard.mockResolvedValue({
      total_faculty: 0,
      total_publications: 0,
      pending_reviews: 0,
      recent_jobs: [],
      connector_statuses: [],
      publication_years: {},
    })
    api.getFacultyList.mockResolvedValue({
      items: [],
      total: 0,
      page: 1,
      page_size: 50,
      pages: 0,
    })
  })

  it('signs in using the tenant-qualified username and renders live dashboard values', async () => {
    render(<App />)
    fireEvent.change(screen.getByLabelText('Username'), { target: { value: 'north-campus/admin' } })
    fireEvent.change(screen.getByLabelText('Password'), { target: { value: 'example-password' } })
    fireEvent.click(screen.getByRole('button', { name: /sign in/i }))

    await waitFor(() => expect(screen.getByText('Good research starts with good evidence.')).toBeInTheDocument())
    expect(api.login).toHaveBeenCalledWith('north-campus/admin', 'example-password')
    expect(screen.getByText('Research Admin')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Faculty' }))
    expect(await screen.findByText('Your directory is ready')).toBeInTheDocument()
  })

  it('shows the API authentication error and stays on sign-in', async () => {
    api.login.mockRejectedValue(new Error('Incorrect username or password'))
    render(<App />)
    fireEvent.change(screen.getByLabelText('Username'), { target: { value: 'north-campus/admin' } })
    fireEvent.change(screen.getByLabelText('Password'), { target: { value: 'wrong-password' } })
    fireEvent.click(screen.getByRole('button', { name: /sign in/i }))

    expect(await screen.findByRole('alert')).toHaveTextContent('Incorrect username or password')
    expect(screen.getByRole('heading', { name: 'Sign in to FRIS' })).toBeInTheDocument()
  })

  it('previews CSV rows before enabling import and reports the API result', async () => {
    api.getSessionToken.mockReturnValue('existing-access-token')
    api.getFacultyList.mockResolvedValue({ items: [], total: 0, page: 1, page_size: 50, pages: 0 })
    api.previewFacultyImport.mockResolvedValue({
      total_rows: 2,
      valid_rows: 1,
      invalid_rows: 1,
      duplicate_rows: 0,
      rows: [
        { row_number: 2, data: { full_name: 'Ada Researcher' }, is_valid: true, errors: [] },
        { row_number: 3, data: { full_name: '' }, is_valid: false, errors: ['full_name is required'] },
      ],
    })
    api.importFaculty.mockResolvedValue({
      imported_count: 1,
      skipped_count: 0,
      error_count: 1,
      discovery_jobs: [{
        id: 'job-1',
        faculty_id: 'faculty-1',
        status: 'failed',
        trigger_type: 'faculty_imported',
        summary: null,
        error_detail: 'Prefect submission failed',
        created_at: '2026-01-01T00:00:00Z',
        started_at: null,
        completed_at: '2026-01-01T00:00:00Z',
        connector_runs: [],
      }],
    })
    render(<App />)
    await screen.findByText('Good research starts with good evidence.')
    fireEvent.click(screen.getByRole('button', { name: 'Faculty' }))
    fireEvent.click(screen.getByRole('button', { name: /Import CSV/ }))
    const file = new File(['full_name\nAda Researcher\n'], 'faculty.csv', { type: 'text/csv' })
    fireEvent.change(screen.getByLabelText(/Choose a CSV file/), { target: { files: [file] } })
    fireEvent.click(screen.getByRole('button', { name: 'Preview import' }))

    expect(await screen.findByRole('button', { name: 'Import 1 valid rows' })).toBeInTheDocument()
    expect(screen.getByText('full_name is required')).toBeInTheDocument()
    const importButton = screen.getByRole('button', { name: 'Import 1 valid rows' })
    expect(importButton).toBeEnabled()
    fireEvent.click(importButton)

    const status = await screen.findByRole('status')
    expect(status).toHaveTextContent('1 added, 0 skipped, 1 issue')
    expect(status).toHaveTextContent('0 discovery jobs submitted; 1 submission failed')
    expect(api.importFaculty).toHaveBeenCalledWith(file)
  })

  it('shows publication provenance and labels match confidence as a score', async () => {
    const faculty = {
      id: 'faculty-1',
      full_name: 'Ada Researcher',
      reported_institution: 'Example University',
      department: 'Computer Science',
      profile_url: null,
      research_interests_text: null,
      is_demo: false,
      demo_label: null,
      identifiers: [],
      name_variants: [],
      affiliations: [],
    }
    api.getFacultyList.mockResolvedValue({ items: [faculty], total: 1, page: 1, page_size: 50, pages: 1 })
    api.getFacultyProfile.mockResolvedValue(faculty)
    api.getFacultyDashboard.mockResolvedValue({ faculty, publication_count: 1, latest_job: null })
    api.getFacultyPublications.mockResolvedValue({
      items: [{
        id: 'publication-1',
        title: 'Evidence-led research',
        doi: '10.1000/example',
        publication_year: 2025,
        venue: 'Research Journal',
        publication_type: 'article',
        landing_url: null,
        match_status: 'accepted',
        confidence_score: 0.84,
        authorships: [],
        sources: [{
          id: 'source-1',
          provider: 'OpenAlex',
          source_title: 'Evidence-led research',
          source_url: 'https://openalex.org/W123',
          retrieved_at: '2025-01-01T00:00:00Z',
        }],
      }],
      total: 1,
      page: 1,
      page_size: 100,
      pages: 1,
    })
    api.getSessionToken.mockReturnValue('existing-access-token')
    render(<App />)
    await screen.findByText('Good research starts with good evidence.')
    fireEvent.click(screen.getByRole('button', { name: 'Faculty' }))
    fireEvent.click(await screen.findByRole('button', { name: /Ada Researcher/ }))

    expect(await screen.findByRole('heading', { name: 'Evidence-led research' })).toBeInTheDocument()
    fireEvent.click(screen.getByText('Evidence & source provenance'))
    expect(screen.getByText(/score, not probability/)).toBeInTheDocument()
    expect(screen.getByText(/OpenAlex/)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'view source' })).toHaveAttribute('href', 'https://openalex.org/W123')
  })

  it('records a review decision with the supplied rationale', async () => {
    api.getSessionToken.mockReturnValue('existing-access-token')
    api.getReviews.mockResolvedValue({
      items: [{
        id: 'review-1',
        review_type: 'publication_match',
        entity_type: 'publication',
        entity_id: 'publication-1',
        status: 'pending',
        priority: 2,
        evidence: { provider: 'OpenAlex' },
        explanation: 'Confirm the publication match.',
        decision: null,
        created_at: '2025-01-01T00:00:00Z',
      }],
      total: 1,
      page: 1,
      page_size: 20,
      pages: 1,
    })
    api.decideReview.mockResolvedValue({})
    vi.spyOn(window, 'prompt').mockReturnValue('Confirmed against the source record')
    render(<App />)
    await screen.findByText('Good research starts with good evidence.')
    fireEvent.click(screen.getByRole('button', { name: /Review queue/ }))
    fireEvent.click(await screen.findByRole('button', { name: 'Accept' }))

    await waitFor(() => expect(api.decideReview).toHaveBeenCalledWith(
      'review-1',
      'accept',
      'Confirmed against the source record',
    ))
    expect(await screen.findByRole('status')).toHaveTextContent('Review accepted.')
  })
})
