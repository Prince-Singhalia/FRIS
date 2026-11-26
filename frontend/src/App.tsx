import { useCallback, useEffect, useState } from 'react'
import type { FormEvent, ReactNode } from 'react'
import {
  clearSession,
  createFaculty,
  decideReview,
  getConnectors,
  getDashboard,
  getFacultyDashboard,
  getFacultyList,
  getFacultyProfile,
  getFacultyPublications,
  getJobs,
  getReviews,
  getSessionToken,
  getUser,
  importFaculty,
  login,
  previewFacultyImport,
  startDiscovery,
  type Connector,
  type Dashboard,
  type Faculty,
  type FacultyInput,
  type Job,
  type Paginated,
  type Publication,
  type Review,
  type User,
} from './api'
import './App.css'

type Page = 'dashboard' | 'faculty' | 'jobs' | 'reviews' | 'connectors'

function messageFrom(error: unknown): string {
  return error instanceof Error ? error.message : 'Something went wrong. Please try again.'
}

function useRemote<T>(load: () => Promise<T>, dependencies: unknown[] = []) {
  const [revision, setRevision] = useState(0)
  const [result, setResult] = useState<{ key: string; data: T | null; error: string }>({
    key: '',
    data: null,
    error: '',
  })
  const resourceKey = `${JSON.stringify(dependencies)}:${revision}`
  const refresh = useCallback(() => setRevision((value) => value + 1), [])

  useEffect(() => {
    let active = true
    load()
      .then((result) => {
        if (active) setResult({ key: resourceKey, data: result, error: '' })
      })
      .catch((reason: unknown) => {
        if (active) setResult({ key: resourceKey, data: null, error: messageFrom(reason) })
      })
    return () => {
      active = false
    }
  }, [load, resourceKey])

  const current = result.key === resourceKey
  return {
    data: current ? result.data : null,
    error: current ? result.error : '',
    loading: !current,
    refresh,
  }
}

function Loading({ label = 'Loading data' }: { label?: string }) {
  return <div className="feedback" role="status"><span className="spinner" />{label}…</div>
}

function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="feedback error-state" role="alert">
      <span>{message}</span>
      {onRetry && <button className="button button-subtle" onClick={onRetry}>Try again</button>}
    </div>
  )
}

function EmptyState({ title, detail }: { title: string; detail: string }) {
  return <div className="empty-state"><span className="empty-mark">—</span><h3>{title}</h3><p>{detail}</p></div>
}

function LoginScreen({ onLogin }: { onLogin: (user: User) => void }) {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setBusy(true)
    setError('')
    try {
      await login(username.trim(), password)
      onLogin(await getUser())
    } catch (reason) {
      setError(messageFrom(reason))
      clearSession()
    } finally {
      setBusy(false)
    }
  }

  return (
    <main className="login-page">
      <div className="login-aside">
        <div className="brand brand-light"><span className="brand-mark">F</span><span>FRIS</span></div>
        <div className="login-message">
          <p className="eyebrow">Research intelligence, in context</p>
          <h1>Make research activity visible.</h1>
          <p>One place to review faculty profiles, publication evidence, and discovery activity.</p>
        </div>
        <p className="login-foot">Faculty Research Intelligence System</p>
      </div>
      <section className="login-panel">
        <div className="login-card">
          <p className="eyebrow">Welcome back</p>
          <h2>Sign in to FRIS</h2>
          <p className="muted">Use your tenant-qualified username and password.</p>
          <form onSubmit={submit} className="form-stack">
            <label>Username<input autoComplete="username" required value={username} onChange={(e) => setUsername(e.target.value)} placeholder="tenant-slug/admin" /></label>
            <label>Password<input autoComplete="current-password" required type="password" value={password} onChange={(e) => setPassword(e.target.value)} /></label>
            {error && <div className="inline-error" role="alert">{error}</div>}
            <button className="button button-primary button-wide" disabled={busy}>{busy ? 'Signing in…' : 'Sign in'}<span aria-hidden="true">→</span></button>
          </form>
          <p className="login-note">Your account is scoped to its institution. Use <code>tenant-slug/username</code> when needed.</p>
        </div>
      </section>
    </main>
  )
}

function App() {
  const [user, setUser] = useState<User | null>(null)
  const [checkingSession, setCheckingSession] = useState(() => Boolean(getSessionToken()))
  const [sessionError, setSessionError] = useState('')
  const [page, setPage] = useState<Page>('dashboard')
  const [selectedFaculty, setSelectedFaculty] = useState<string | null>(null)

  useEffect(() => {
    if (!getSessionToken()) return
    getUser()
      .then(setUser)
      .catch((error: unknown) => {
        clearSession()
        setSessionError(messageFrom(error))
      })
      .finally(() => setCheckingSession(false))
  }, [])

  if (checkingSession) return <div className="screen-loading"><Loading label="Checking your session" /></div>
  if (!user) {
    return <><LoginScreen onLogin={setUser} />{sessionError && <p className="session-notice" role="status">Your previous session could not be restored ({sessionError}). Please sign in again.</p>}</>
  }

  function navigate(next: Page) {
    setSelectedFaculty(null)
    setPage(next)
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <button className="brand brand-button" onClick={() => navigate('dashboard')} aria-label="FRIS dashboard">
          <span className="brand-mark">F</span><span>FRIS</span>
        </button>
        <p className="nav-caption">Workspace</p>
        <nav className="main-nav" aria-label="Main navigation">
          <NavButton active={page === 'dashboard' && !selectedFaculty} onClick={() => navigate('dashboard')} label="Overview" icon="◫" />
          <NavButton active={page === 'faculty' && !selectedFaculty} onClick={() => navigate('faculty')} label="Faculty" icon="◉" />
          <NavButton active={page === 'jobs'} onClick={() => navigate('jobs')} label="Discovery jobs" icon="↗" />
          <NavButton active={page === 'reviews'} onClick={() => navigate('reviews')} label="Review queue" icon="☷" />
          <NavButton active={page === 'connectors'} onClick={() => navigate('connectors')} label="Data sources" icon="⌘" />
        </nav>
        <div className="sidebar-bottom">
          <div className="sidebar-note"><span className="status-dot" />Tenant-scoped workspace</div>
          <div className="user-chip"><span className="avatar">{initials(user.full_name)}</span><span className="user-label"><strong>{user.full_name}</strong><small>{user.role.replaceAll('_', ' ')}</small></span><button aria-label="Sign out" className="icon-button" onClick={() => { clearSession(); setUser(null) }}>↪</button></div>
        </div>
      </aside>
      <div className="main-column">
        <header className="topbar">
          <div className="mobile-brand"><span className="brand-mark">F</span><strong>FRIS</strong></div>
          <div className="breadcrumb">Research operations <span>/</span> <strong>{selectedFaculty ? 'Faculty profile' : pageTitle(page)}</strong></div>
          <div className="topbar-meta"><span className="secure-label"><span className="status-dot" />Secure workspace</span><span className="avatar avatar-small">{initials(user.full_name)}</span></div>
        </header>
        <main className="page-content">
          {selectedFaculty ? (
            <FacultyProfilePage id={selectedFaculty} onBack={() => setSelectedFaculty(null)} canDiscover={['admin', 'research_officer'].includes(user.role)} />
          ) : page === 'dashboard' ? <DashboardPage onNavigate={navigate} onSelectFaculty={setSelectedFaculty} canManageFaculty={['admin', 'research_officer'].includes(user.role)} /> :
            page === 'faculty' ? <FacultyPage onSelect={setSelectedFaculty} canManage={['admin', 'research_officer'].includes(user.role)} /> :
              page === 'jobs' ? <JobsPage /> :
                page === 'reviews' ? <ReviewsPage canDecide={['admin', 'research_officer', 'reviewer'].includes(user.role)} /> : <ConnectorsPage />}
        </main>
        <footer className="app-footer"><span>FRIS · Research intelligence</span><span>Evidence-led discovery · Tenant scoped</span></footer>
      </div>
    </div>
  )
}

function NavButton({ active, onClick, label, icon }: { active: boolean; onClick: () => void; label: string; icon: string }) {
  return <button className={`nav-item${active ? ' active' : ''}`} onClick={onClick} aria-current={active ? 'page' : undefined}><span className="nav-icon" aria-hidden="true">{icon}</span>{label}{label === 'Review queue' && <span className="nav-arrow">›</span>}</button>
}

function initials(name: string) {
  return name.split(/\s+/).filter(Boolean).slice(0, 2).map((part) => part[0]?.toUpperCase()).join('')
}

function pageTitle(page: Page) {
  return ({ dashboard: 'Overview', faculty: 'Faculty', jobs: 'Discovery jobs', reviews: 'Review queue', connectors: 'Data sources' })[page]
}

function PageHeading({ eyebrow, title, detail, action }: { eyebrow: string; title: string; detail: string; action?: ReactNode }) {
  return <div className="page-heading"><div><p className="eyebrow">{eyebrow}</p><h1>{title}</h1><p className="page-description">{detail}</p></div>{action && <div className="heading-action">{action}</div>}</div>
}

function DashboardPage({ onNavigate, onSelectFaculty, canManageFaculty }: { onNavigate: (page: Page) => void; onSelectFaculty: (id: string) => void; canManageFaculty: boolean }) {
  const load = useCallback(() => getDashboard(), [])
  const { data, error, loading, refresh } = useRemote<Dashboard>(load)
  if (loading) return <Loading />
  if (error || !data) return <ErrorState message={error || 'Dashboard data is unavailable.'} onRetry={refresh} />

  const configured = data.connector_statuses.filter((connector) => connector.is_enabled && connector.is_configured).length
  const years = Object.entries(data.publication_years).sort(([a], [b]) => Number(a) - Number(b)).slice(-8)
  const maxYearCount = Math.max(1, ...years.map(([, count]) => count))

  return <>
    <PageHeading eyebrow="Workspace overview" title="Good research starts with good evidence." detail="A live view of faculty profiles, publication discovery, and the work that needs review." action={canManageFaculty && <button className="button button-primary" onClick={() => onNavigate('faculty')}><span aria-hidden="true">＋</span> Manage faculty</button>} />
    <div className="metric-grid">
      <MetricCard label="Faculty profiles" value={data.total_faculty} note="In this institution" icon="◉" />
      <MetricCard label="Publications" value={data.total_publications} note="Matched to faculty" icon="▤" />
      <MetricCard label="Awaiting review" value={data.pending_reviews} note="Requires a decision" icon="☷" accent={data.pending_reviews > 0} onClick={() => onNavigate('reviews')} />
      <MetricCard label="Sources ready" value={`${configured} / ${data.connector_statuses.length}`} note="Enabled and configured" icon="⌘" />
    </div>
    <div className="dashboard-grid">
      <section className="panel chart-panel">
        <div className="panel-heading"><div><p className="eyebrow">Research output</p><h2>Publications by year</h2></div><span className="subtle-tag">Matched records</span></div>
        {years.length ? <div className="year-chart" aria-label="Publication counts by year">{years.map(([year, count]) => <div className="year-column" key={year}><span className="bar-count">{count}</span><div className="bar-track"><span className="bar" style={{ height: `${Math.max(5, (count / maxYearCount) * 100)}%` }} /></div><span className="year-label">{year}</span></div>)}</div> : <EmptyState title="No publication activity yet" detail="Publication activity will appear here as evidence is discovered and matched." />}
      </section>
      <section className="panel source-panel">
        <div className="panel-heading"><div><p className="eyebrow">Connected services</p><h2>Data sources</h2></div><button className="text-button" onClick={() => onNavigate('connectors')}>View all <span aria-hidden="true">→</span></button></div>
        <div className="source-list">{data.connector_statuses.slice(0, 4).map((source) => <SourceRow key={source.provider} source={source} />)}</div>
        <p className="panel-footnote">Source readiness reflects configuration only, not a live health check.</p>
      </section>
    </div>
    <section className="panel recent-panel">
      <div className="panel-heading"><div><p className="eyebrow">Recent activity</p><h2>Discovery jobs</h2></div><button className="text-button" onClick={() => onNavigate('jobs')}>All jobs <span aria-hidden="true">→</span></button></div>
      <JobsTable jobs={data.recent_jobs} onSelectFaculty={onSelectFaculty} />
    </section>
  </>
}

function MetricCard({ label, value, note, icon, accent, onClick }: { label: string; value: string | number; note: string; icon: string; accent?: boolean; onClick?: () => void }) {
  return <button className={`metric-card${accent ? ' metric-accent' : ''}${onClick ? ' metric-clickable' : ''}`} onClick={onClick} disabled={!onClick}>
    <span className="metric-icon" aria-hidden="true">{icon}</span><span className="metric-label">{label}</span><strong className="metric-value">{value}</strong><span className="metric-note">{note}</span>
  </button>
}

function SourceRow({ source }: { source: Connector }) {
  const configuredState = source.is_enabled && source.is_configured
  const label = !source.is_enabled ? 'Disabled' : !source.is_configured ? 'Not configured' : source.health_status === 'healthy' ? 'Healthy' : 'Configured · not checked'
  return <div className="source-row"><span className={`source-symbol source-${source.provider.slice(0, 2)}`}>{source.display_name.slice(0, 1)}</span><span className="source-name"><strong>{source.display_name}</strong><small>{source.provider.replaceAll('_', ' ')}</small></span><span className={`status-pill ${configuredState ? 'status-ready' : 'status-muted'}`}><span className="status-dot" />{label}</span></div>
}

function FacultyPage({ onSelect, canManage }: { onSelect: (id: string) => void; canManage: boolean }) {
  const [term, setTerm] = useState('')
  const [search, setSearch] = useState('')
  const [dialog, setDialog] = useState<'add' | 'import' | null>(null)
  const [notice, setNotice] = useState('')
  const load = useCallback(() => getFacultyList(search), [search])
  const { data, error, loading, refresh } = useRemote<Paginated<Faculty>>(load, [search])

  async function saveFaculty(input: FacultyInput) {
    const created = await createFaculty(input)
    setDialog(null)
    setNotice(
      created.discovery_job.status === 'failed'
        ? `${input.full_name} was added, but discovery could not be submitted. See Discovery jobs for details.`
        : `${input.full_name} was added. Discovery job ${created.discovery_job.id.slice(0, 8)} is ${created.discovery_job.status}.`,
    )
    refresh()
  }

  return <>
    <PageHeading eyebrow="People & profiles" title="Faculty directory" detail="Manage institutional profiles and review the evidence connected to each researcher." action={canManage && <div className="button-row"><button className="button button-secondary" onClick={() => setDialog('import')}>↑ Import CSV</button><button className="button button-primary" onClick={() => setDialog('add')}><span aria-hidden="true">＋</span> Add faculty</button></div>} />
    {notice && <div className="success-banner" role="status">{notice}<button onClick={() => setNotice('')} aria-label="Dismiss">×</button></div>}
    <section className="panel directory-panel">
      <div className="directory-toolbar"><div><h2>All faculty</h2><p>{data ? `${data.total} profile${data.total === 1 ? '' : 's'}` : 'Search profiles'}</p></div><form className="search-form" onSubmit={(event) => { event.preventDefault(); setSearch(term.trim()) }}><label className="sr-only" htmlFor="faculty-search">Search faculty</label><span aria-hidden="true">⌕</span><input id="faculty-search" value={term} onChange={(event) => setTerm(event.target.value)} placeholder="Search by name" /><button className="button button-subtle">Search</button></form></div>
      {loading ? <Loading label="Loading faculty" /> : error ? <ErrorState message={error} onRetry={refresh} /> : data?.items.length ? <div className="faculty-list">{data.items.map((faculty) => <button className="faculty-row" key={faculty.id} onClick={() => onSelect(faculty.id)}><span className="faculty-avatar">{initials(faculty.full_name)}</span><span className="faculty-info"><strong>{faculty.full_name}{faculty.is_demo && <span className="demo-badge">DEMO · external researcher</span>}</strong><small>{[faculty.department, faculty.reported_institution].filter(Boolean).join(' · ') || 'No institution details added'}</small></span><span className="faculty-meta">{faculty.identifiers.find((identifier) => identifier.identifier_type === 'orcid')?.value ?? 'Profile'}<span aria-hidden="true">→</span></span></button>)}</div> : <EmptyState title={search ? 'No matching faculty' : 'Your directory is ready'} detail={search ? 'Try another name or clear the search to view all profiles.' : 'Add a faculty profile or import a CSV to start connecting research evidence.'} />}
    </section>
    {dialog === 'add' && <AddFacultyDialog onClose={() => setDialog(null)} onSave={saveFaculty} />}
    {dialog === 'import' && <ImportDialog onClose={() => setDialog(null)} onComplete={(text) => { setDialog(null); setNotice(text); refresh() }} />}
  </>
}

function AddFacultyDialog({ onClose, onSave }: { onClose: () => void; onSave: (input: FacultyInput) => Promise<void> }) {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const form = new FormData(event.currentTarget)
    const input: FacultyInput = {
      full_name: String(form.get('full_name')).trim(),
      reported_institution: String(form.get('reported_institution') || '').trim() || null,
      department: String(form.get('department') || '').trim() || null,
      institutional_email: String(form.get('institutional_email') || '').trim() || null,
      profile_url: String(form.get('profile_url') || '').trim() || null,
      orcid: String(form.get('orcid') || '').trim() || null,
      research_interests_text: String(form.get('research_interests_text') || '').trim() || null,
      name_variants: String(form.get('name_variants') || '').split(';').map((value) => value.trim()).filter(Boolean),
    }
    setBusy(true)
    setError('')
    try { await onSave(input) } catch (reason) { setError(messageFrom(reason)) } finally { setBusy(false) }
  }
  return <Dialog title="Add faculty profile" onClose={onClose}>
    <p className="dialog-intro">Create an institutional profile. Researcher emails are stored only in FRIS and are not sent to data providers.</p>
    <form className="form-grid" onSubmit={submit}>
      <label className="field-span">Full name<input name="full_name" required autoFocus maxLength={500} /></label>
      <label>Institution<input name="reported_institution" maxLength={500} /></label><label>Department<input name="department" maxLength={500} /></label>
      <label>ORCID<input name="orcid" placeholder="0000-0000-0000-0000" /></label><label>Profile URL<input name="profile_url" type="url" placeholder="https://" /></label>
      <label className="field-span">Institutional email <span className="private-label">Private · not shared</span><input name="institutional_email" type="email" autoComplete="off" /></label>
      <label className="field-span">Research interests <small>Separate topics with semicolons</small><textarea name="research_interests_text" rows={2} /></label>
      <label className="field-span">Name variants <small>Separate names with semicolons</small><input name="name_variants" /></label>
      {error && <div className="inline-error field-span" role="alert">{error}</div>}
      <div className="dialog-actions field-span"><button type="button" className="button button-secondary" onClick={onClose}>Cancel</button><button className="button button-primary" disabled={busy}>{busy ? 'Saving…' : 'Save profile'}</button></div>
    </form>
  </Dialog>
}

function ImportDialog({ onClose, onComplete }: { onClose: () => void; onComplete: (message: string) => void }) {
  const [file, setFile] = useState<File | null>(null)
  const [preview, setPreview] = useState<Awaited<ReturnType<typeof previewFacultyImport>> | null>(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  async function createPreview(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!file) return
    setBusy(true); setError('')
    try { setPreview(await previewFacultyImport(file)) } catch (reason) { setError(messageFrom(reason)) } finally { setBusy(false) }
  }
  async function commit() {
    if (!file || !preview?.valid_rows) return
    setBusy(true); setError('')
    try {
      const result = await importFaculty(file)
      const failedJobs = result.discovery_jobs.filter((job) => job.status === 'failed').length
      const submittedJobs = result.discovery_jobs.length - failedJobs
      const discoveryNote = result.discovery_jobs.length
        ? ` ${submittedJobs} discovery job${submittedJobs === 1 ? '' : 's'} submitted; ${failedJobs} submission${failedJobs === 1 ? '' : 's'} failed.`
        : ''
      onComplete(`Import complete: ${result.imported_count} added, ${result.skipped_count} skipped, ${result.error_count} issue${result.error_count === 1 ? '' : 's'}.${discoveryNote}`)
    } catch (reason) { setError(messageFrom(reason)) } finally { setBusy(false) }
  }
  return <Dialog title="Import faculty from CSV" onClose={onClose} wide>
    <p className="dialog-intro">Preview and validate the file before importing. Required column: <code>faculty_name</code>, <code>full_name</code>, or <code>name</code>.</p>
    <form className="upload-form" onSubmit={createPreview}>
      <label className="upload-drop"><span className="upload-icon">↑</span><strong>{file?.name ?? 'Choose a CSV file'}</strong><small>UTF-8 CSV · max 10 MB</small><input type="file" accept=".csv,text/csv" onChange={(event) => { setFile(event.target.files?.[0] ?? null); setPreview(null); setError('') }} /></label>
      <button className="button button-secondary" disabled={!file || busy}>{busy ? 'Checking…' : 'Preview import'}</button>
    </form>
    {error && <div className="inline-error" role="alert">{error}</div>}
    {preview && <div className="import-preview">
      <div className="preview-summary"><span><strong>{preview.total_rows}</strong> rows</span><span className="valid-count"><strong>{preview.valid_rows}</strong> valid</span><span className={preview.invalid_rows ? 'invalid-count' : ''}><strong>{preview.invalid_rows}</strong> invalid</span><span><strong>{preview.duplicate_rows}</strong> duplicates</span></div>
      <div className="table-scroll"><table><thead><tr><th>Row</th><th>Name</th><th>Institution</th><th>Validation</th></tr></thead><tbody>{preview.rows.slice(0, 8).map((row) => <tr key={row.row_number}><td>{row.row_number}</td><td>{String(row.data.full_name ?? '—')}</td><td>{String(row.data.reported_institution ?? '—')}</td><td>{row.is_valid ? <span className="valid-count">Ready</span> : <span className="invalid-count">{row.errors.join('; ')}</span>}</td></tr>)}</tbody></table></div>
      {preview.rows.length > 8 && <small className="muted">Showing 8 of {preview.rows.length} rows.</small>}
    </div>}
    <div className="dialog-actions"><button className="button button-secondary" onClick={onClose}>Cancel</button>{preview && <button className="button button-primary" disabled={busy || preview.valid_rows === 0} onClick={commit}>{busy ? 'Importing…' : `Import ${preview.valid_rows} valid rows`}</button>}</div>
  </Dialog>
}

function Dialog({ title, onClose, children, wide = false }: { title: string; onClose: () => void; children: ReactNode; wide?: boolean }) {
  return <div className="modal-backdrop" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose() }}><section className={`dialog${wide ? ' dialog-wide' : ''}`} role="dialog" aria-modal="true" aria-labelledby="dialog-title"><div className="dialog-heading"><h2 id="dialog-title">{title}</h2><button className="icon-button close-button" onClick={onClose} aria-label="Close dialog">×</button></div>{children}</section></div>
}

function FacultyProfilePage({ id, onBack, canDiscover }: { id: string; onBack: () => void; canDiscover: boolean }) {
  const [notice, setNotice] = useState('')
  const loadProfile = useCallback(async () => {
    const [profile, summary, publications] = await Promise.all([getFacultyProfile(id), getFacultyDashboard(id), getFacultyPublications(id)])
    return { profile, summary, publications }
  }, [id])
  const { data, error, loading, refresh } = useRemote(loadProfile, [id])
  async function discover() {
    setNotice('')
    try {
      const job = await startDiscovery(id)
      setNotice(`Discovery job ${job.id.slice(0, 8)} was submitted with status “${job.status}”.`)
    } catch (reason) { setNotice(messageFrom(reason)) }
  }
  if (loading) return <Loading label="Loading faculty profile" />
  if (error || !data) return <><button className="back-link" onClick={onBack}>← Faculty directory</button><ErrorState message={error || 'Profile is unavailable.'} onRetry={refresh} /></>
  const { profile, summary, publications } = data
  return <>
    <button className="back-link" onClick={onBack}>← Faculty directory</button>
    <PageHeading eyebrow="Faculty profile" title={profile.full_name} detail={[profile.department, profile.reported_institution].filter(Boolean).join(' · ') || 'Institution details not provided'} action={canDiscover && <button className="button button-primary" onClick={discover}>↻ Discover publications</button>} />
    {profile.is_demo && <div className="demo-notice"><strong>DEMO — external researcher.</strong> This researcher is not a member of the customer's university.</div>}
    {notice && <div className="success-banner" role="status">{notice}<button onClick={() => setNotice('')} aria-label="Dismiss">×</button></div>}
    <div className="profile-grid">
      <section className="panel profile-card"><div className="profile-card-top"><span className="faculty-avatar faculty-avatar-large">{initials(profile.full_name)}</span><span className="profile-status">Institutional record</span></div><h2>Researcher details</h2><dl className="detail-list"><Detail label="Institution" value={profile.reported_institution} /><Detail label="Department" value={profile.department} /><Detail label="ORCID" value={profile.identifiers.find((item) => item.identifier_type === 'orcid')?.value} /><Detail label="Profile URL" value={profile.profile_url} href={profile.profile_url} /><Detail label="Research interests" value={profile.research_interests_text} /></dl>{profile.name_variants.length > 0 && <div className="detail-extra"><strong>Name variants</strong><p>{profile.name_variants.map((variant) => variant.variant_name).join(' · ')}</p></div>}</section>
      <section className="panel profile-activity"><p className="eyebrow">Discovery activity</p><div className="profile-stat"><strong>{summary.publication_count}</strong><span>matched publications</span></div>{summary.latest_job ? <div className="latest-job"><span className={`job-status status-${summary.latest_job.status}`}>{summary.latest_job.status.replaceAll('_', ' ')}</span><p>Last job · {formatDate(summary.latest_job.created_at)}</p><small>{summary.latest_job.summary ?? 'No run summary provided.'}</small></div> : <EmptyState title="No discovery jobs" detail="Start discovery to gather publication evidence from configured sources." />}</section>
    </div>
    <section className="panel publications-panel"><div className="panel-heading"><div><p className="eyebrow">Evidence library</p><h2>Publications <span className="count-chip">{publications.total}</span></h2></div><span className="subtle-tag">Provider provenance shown</span></div>
      {publications.items.length ? <div className="publication-list">{publications.items.map((publication) => <PublicationCard key={publication.id} publication={publication} />)}</div> : <EmptyState title="No matched publications" detail="No publication records are currently matched to this profile. Run discovery to look for evidence." />}
    </section>
  </>
}

function Detail({ label, value, href }: { label: string; value?: string | null; href?: string | null }) {
  if (!value) return null
  return <div><dt>{label}</dt><dd>{href ? <a href={href} target="_blank" rel="noreferrer">{value}<span aria-hidden="true"> ↗</span></a> : value}</dd></div>
}

function PublicationCard({ publication }: { publication: Publication }) {
  return <article className="publication-card"><div className="publication-main"><div className="publication-title-row"><h3>{publication.title}</h3>{publication.publication_year && <span className="year-chip">{publication.publication_year}</span>}</div><p className="publication-meta">{[publication.venue, publication.publication_type?.replaceAll('_', ' ')].filter(Boolean).join(' · ') || 'Publication metadata'}</p>{publication.authorships.length > 0 && <p className="author-line">{publication.authorships.map((author) => author.author_name).join(', ')}</p>}<details className="evidence-details"><summary>Evidence &amp; source provenance</summary><div className="evidence-content">{publication.doi && <p><strong>DOI</strong> <a href={`https://doi.org/${publication.doi}`} target="_blank" rel="noreferrer">{publication.doi}</a></p>}{publication.match_status && <p><strong>Match status</strong> {publication.match_status}</p>}{publication.confidence_score !== null && publication.confidence_score !== undefined && <p><strong>Confidence score</strong> {publication.confidence_score.toFixed(2)} <small>· score, not probability</small></p>}{publication.sources.length ? publication.sources.map((source) => <p key={source.id}><strong>{source.provider}</strong> · {source.source_title ?? 'Source record'}{source.retrieved_at && <span> · retrieved {formatDate(source.retrieved_at)}</span>}{source.source_url && <> · <a href={source.source_url} target="_blank" rel="noreferrer">view source</a></>}</p>) : <p>No provider provenance was returned for this record.</p>}</div></details></div><div className="publication-actions">{publication.landing_url && <a className="text-button" href={publication.landing_url} target="_blank" rel="noreferrer">Open record ↗</a>}</div></article>
}

function JobsPage() {
  const [pageNumber, setPageNumber] = useState(1)
  const load = useCallback(() => getJobs(pageNumber), [pageNumber])
  const { data, error, loading, refresh } = useRemote<Paginated<Job>>(load, [pageNumber])
  return <>
    <PageHeading eyebrow="Research data pipeline" title="Discovery jobs" detail="Track provider retrieval runs and their outcomes. A submitted job is not the same as a completed provider check." />
    <section className="panel table-panel"><div className="table-panel-heading"><div><h2>Job history</h2><p>{data ? `${data.total} total jobs` : 'Most recent first'}</p></div>{data && <span className="subtle-tag">{data.total} records</span>}</div>
      {loading ? <Loading /> : error ? <ErrorState message={error} onRetry={refresh} /> : data?.items.length ? <><JobsTable jobs={data.items} /><Pagination current={pageNumber} pages={data.pages} onChange={setPageNumber} /></> : <EmptyState title="No discovery jobs yet" detail="Start a discovery run from a faculty profile to see its status and provider-level results here." />}
    </section>
  </>
}

function JobsTable({ jobs, onSelectFaculty }: { jobs: Job[]; onSelectFaculty?: (id: string) => void }) {
  if (!jobs.length) return <EmptyState title="No recent activity" detail="Discovery runs will appear here as they are submitted." />
  return <div className="table-scroll"><table><thead><tr><th>Faculty</th><th>Status</th><th>Started</th><th>Sources</th><th>Records fetched</th></tr></thead><tbody>{jobs.map((job) => <tr key={job.id}><td>{onSelectFaculty ? <button className="table-link" onClick={() => onSelectFaculty(job.faculty_id)}>{job.faculty_id.slice(0, 8)}…</button> : <span className="mono">{job.faculty_id.slice(0, 8)}…</span>}</td><td><span className={`job-status status-${job.status}`}>{job.status.replaceAll('_', ' ')}</span></td><td>{formatDate(job.created_at)}</td><td>{job.connector_runs?.length ?? 0}</td><td>{job.connector_runs?.reduce((sum, run) => sum + run.records_fetched, 0) ?? '—'}</td></tr>)}</tbody></table></div>
}

function ReviewsPage({ canDecide }: { canDecide: boolean }) {
  const [pageNumber, setPageNumber] = useState(1)
  const [status, setStatus] = useState('pending')
  const load = useCallback(() => getReviews(pageNumber, status), [pageNumber, status])
  const { data, error, loading, refresh } = useRemote<Paginated<Review>>(load, [pageNumber, status])
  const [busyId, setBusyId] = useState('')
  const [notice, setNotice] = useState('')
  async function decide(item: Review, decision: 'accept' | 'reject' | 'defer') {
    const rationale = window.prompt(`Optional rationale for ${decision}ing this item:`)
    if (rationale === null) return
    setBusyId(item.id); setNotice('')
    try {
      await decideReview(item.id, decision, rationale.trim() || undefined)
      setNotice(`Review ${decision}ed.`)
      refresh()
    } catch (reason) { setNotice(messageFrom(reason)) } finally { setBusyId('') }
  }
  return <>
    <PageHeading eyebrow="Human-in-the-loop" title="Review queue" detail="Review uncertain publication matches and record explicit decisions with an optional rationale." />
    {notice && <div className="success-banner" role="status">{notice}<button onClick={() => setNotice('')} aria-label="Dismiss">×</button></div>}
    <section className="panel table-panel"><div className="table-panel-heading"><div><h2>{status === 'pending' ? 'Needs your attention' : `${status[0].toUpperCase()}${status.slice(1)} reviews`}</h2><p>Decisions are recorded in the audit trail.</p></div><label className="filter-label">Show<select value={status} onChange={(event) => { setStatus(event.target.value); setPageNumber(1) }}><option value="pending">Pending</option><option value="decided">Decided</option><option value="deferred">Deferred</option></select></label></div>
      {loading ? <Loading /> : error ? <ErrorState message={error} onRetry={refresh} /> : data?.items.length ? <><div className="review-list">{data.items.map((item) => <article className="review-card" key={item.id}><div className="review-priority">{item.priority > 0 ? `P${item.priority}` : '—'}</div><div className="review-content"><div className="review-title-row"><div><span className="eyebrow">{item.review_type.replaceAll('_', ' ')} · {item.entity_type.replaceAll('_', ' ')}</span><h3>{item.explanation || `Review ${item.entity_type} evidence`}</h3></div><span className={`job-status status-${item.status}`}>{item.status}</span></div><p className="review-entity">Record ID <span className="mono">{item.entity_id}</span></p>{item.evidence && <details className="evidence-details"><summary>View evidence</summary><pre>{JSON.stringify(item.evidence, null, 2)}</pre></details>}{canDecide && item.status === 'pending' && <div className="review-actions"><button className="button button-secondary" disabled={busyId === item.id} onClick={() => decide(item, 'defer')}>Defer</button><button className="button button-secondary" disabled={busyId === item.id} onClick={() => decide(item, 'reject')}>Reject</button><button className="button button-primary" disabled={busyId === item.id} onClick={() => decide(item, 'accept')}>{busyId === item.id ? 'Saving…' : 'Accept'}</button></div>}</div></article>)}</div><Pagination current={pageNumber} pages={data.pages} onChange={setPageNumber} /></> : <EmptyState title={status === 'pending' ? 'All caught up' : `No ${status} reviews`} detail={status === 'pending' ? 'There are no review items waiting for a decision.' : 'Items will show here when their review status changes.'} />}
    </section>
  </>
}

function ConnectorsPage() {
  const load = useCallback(() => getConnectors(), [])
  const { data, error, loading, refresh } = useRemote<Connector[]>(load)
  return <>
    <PageHeading eyebrow="Provider integrations" title="Data sources" detail="Review enabled providers, configuration readiness, and the capabilities each connector reports." />
    <div className="info-banner"><strong>Readiness is not a health check.</strong> Credentials and enabled state are reported by FRIS configuration. Live provider health is not implied unless explicitly shown.</div>
    {loading ? <Loading /> : error ? <ErrorState message={error} onRetry={refresh} /> : data?.length ? <div className="connector-grid">{data.map((connector) => <ConnectorCard key={connector.provider} connector={connector} />)}</div> : <EmptyState title="No data sources returned" detail="The API did not return connector status information." />}
  </>
}

function ConnectorCard({ connector }: { connector: Connector }) {
  const ready = connector.is_enabled && connector.is_configured
  return <article className="panel connector-card"><div className="connector-top"><span className="source-symbol connector-symbol">{connector.display_name.slice(0, 1)}</span><span className={`status-pill ${ready ? 'status-ready' : 'status-muted'}`}><span className="status-dot" />{!connector.is_enabled ? 'Disabled' : connector.is_configured ? (connector.health_status === 'healthy' ? 'Healthy' : 'Configured · not checked') : 'Not configured'}</span></div><h2>{connector.display_name}</h2><p className="connector-key">{connector.provider}</p><div className="capability-list"><strong>Reported capabilities</strong>{Object.entries(connector.capabilities ?? {}).map(([capability, enabled]) => <span key={capability} className={enabled ? '' : 'capability-disabled'}><span aria-hidden="true">{enabled ? '✓' : '—'}</span>{capability.replaceAll('_', ' ')}</span>)}</div>{connector.terms_url && <a className="text-button connector-link" href={connector.terms_url} target="_blank" rel="noreferrer">Provider documentation ↗</a>}</article>
}

function Pagination({ current, pages, onChange }: { current: number; pages: number; onChange: (page: number) => void }) {
  if (pages <= 1) return null
  return <div className="pagination"><span>Page {current} of {pages}</span><div><button className="button button-subtle" disabled={current <= 1} onClick={() => onChange(current - 1)}>Previous</button><button className="button button-subtle" disabled={current >= pages} onClick={() => onChange(current + 1)}>Next</button></div></div>
}

function formatDate(value: string) {
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? '—' : new Intl.DateTimeFormat(undefined, { dateStyle: 'medium' }).format(date)
}

export default App
