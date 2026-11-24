# FRIS — Master Implementation Brief for Cursor Agent

**Project:** Faculty Research Intelligence System (FRIS)  
**Problem statement:** PB-1 — Design and implement a secure, automated CI/CD pipeline for developing, testing and deploying a university research publication tracking system.  
**Specification basis:** `FRIS_Revised_Scalable_Data_Pipeline_and_CICD_Blueprint_v3_0.docx` (the controlling project specification).  
**Build target:** a runnable, tested, locally deployable MVP that is architected for multiple institutions and larger faculty populations.  
**Primary coding agent:** Cursor Agent mode. This brief can also be used with Google Antigravity Agent.

---

## 0. Instructions to the coding agent — read before editing

You are the senior full-stack and data-platform engineer responsible for implementing FRIS. Do not respond with only an architecture proposal, pseudocode, screenshots or isolated Python scripts. Inspect the repository, implement the application, run it, execute tests, fix failures, and document exactly what works.

### Non-negotiable execution rules

1. **Inspect first.** Examine the existing workspace, source files, Git state, installed runtimes and available container tooling before making changes. Preserve existing user work. Do not overwrite a working project blindly. If the workspace is empty, scaffold the monorepo described below.
2. **Create an implementation plan, then execute it.** Do not stop after producing a plan. Work phase by phase and keep the application runnable after each major phase.
3. **Do not fake integrations.** No hard-coded publication lists, fabricated API responses in production paths, simulated success statuses, or mock records presented as live provider results. Mocks are allowed only in automated tests and must be labelled as mocks.
4. **Do not invent provider API behaviour.** Verify endpoint paths, query parameters, pagination, field names, authentication and current provider terms against official documentation before implementing each connector. Record the documentation URL and the date checked in `docs/provider-integrations.md`.
5. **Do not claim a test passed unless it was actually run.** Show command, result and any skipped tests. If an external API cannot be reached or credentials are missing, mark that connector `not_configured`, `unavailable` or `failed`; do not report a successful live integration.
6. **No paid dependency in the MVP.** Use free/open-source application components and local or university-hosted infrastructure. Public APIs can have quotas, rate limits, registration requirements and policy restrictions. Free software does not mean unlimited provider usage or zero infrastructure cost.
7. **Respect source terms.** Use official APIs, permitted feeds and repositories. Do not scrape Google Scholar, bypass publisher access controls, download restricted full text, or store provider payloads when terms prohibit it. This product is primarily a metadata discovery and tracking system, not a universal PDF downloader.
8. **Protect secrets and personal data.** No secrets in source control. Never send faculty institutional email to scholarly providers by default. Store only the identity and institutional attributes needed for the project. Hash passwords; enforce authenticated and role-authorized admin/reviewer actions.
9. **Keep raw evidence and normalized data separate.** Never silently overwrite provider fields or discard provenance. Preserve source-specific values, retrieval timestamps, provider identifiers and source URLs.
10. **Make processing idempotent.** Re-running discovery must not create duplicate faculty, source records, publications, authorships or jobs for the same logical event.
11. **Do not overengineer the MVP.** Start with a modular monolith, PostgreSQL, Docker Compose and bounded concurrency. Do not add Kafka, Kubernetes, Redis, Elasticsearch, a vector database or an LLM unless a measured requirement justifies it.
12. **Keep the two pipelines distinct and connected:**
    - Research Data Pipeline = discovers, validates, cleans, resolves, deduplicates, stores and displays publication metadata.
    - Software CI/CD Pipeline = tests, scans, builds, versions, deploys and verifies the application **and the Prefect worker/flow code**.

At the end of each phase, provide: files changed, commands run, actual test results, known gaps, and the next phase. If a failure occurs, diagnose and fix it before moving on. Make reasonable engineering choices without asking the user to decide routine implementation details.

---

## 1. Product goal and pilot scope

Build a university-oriented system that accepts **faculty identity data only** and autonomously discovers scholarly works from configured sources. The university must not need to supply a ready-made publication list.

The working pipeline is:

`Faculty intake → query planning → provider discovery → raw/source landing → schema validation → normalization/cleaning → author identity resolution → confidence scoring → publication deduplication → metadata reconciliation → PostgreSQL → dashboard/review queue → scheduled incremental refresh`

### First pilot researcher (demo-only)

Use this one publicly identifiable researcher as the first test subject:

| Field | Pilot value |
|---|---|
| Full name | Fei-Fei Li |
| Publicly reported affiliation | Stanford University |
| Department | Computer Science |
| ORCID iD | `0000-0002-7481-0810` |
| Public faculty profile | `https://profiles.stanford.edu/fei-fei-li` |
| OpenAlex public profile reference for runtime cross-check | `https://openalex.org/authors/A5100450462` |
| OpenAlex ID | `A5100450462` — expected discovery cross-check only; do not silently trust or pre-link it as a verified faculty identifier |
| Record label | `DEMO — external researcher; not a member of the customer's university` |

Create a separate demo tenant such as `FRIS Demo Tenant`. Keep the tenant/customer institution distinct from the researcher's reported affiliation. **Do not represent Fei-Fei Li as a faculty member of the user's university.** Do not preload a publication list. The system must discover works from providers.

The initial form/CSV should contain the name, reported affiliation, department, ORCID and public profile URL. Do not preload OpenAlex author ID as a verified identifier; discover it through the API and compare the returned ORCID/name/affiliation evidence. The OpenAlex ID above is only a test assertion/reference to check against live provider output.

### Why one researcher first

The pilot is a vertical-slice test: intake, source connectivity, identity resolution, normalization, deduplication, persistence, dashboard display and reruns must all work before expanding the faculty count. Passing one pilot proves the workflow works for that case; it does **not** prove universal publication coverage, high recall, or correct handling of common names. The system must support more faculty through form/CSV import and configuration, not code changes.

---

## 2. Recommended stack

Use stable, compatible releases and lock exact dependency versions in lockfiles. Do not guess versions; check current compatibility before pinning.

| Layer | Required implementation |
|---|---|
| Frontend | React + TypeScript + Vite |
| UI | Accessible component system and responsive CSS; avoid unnecessary paid UI kits |
| Charts | Recharts (or another maintained free chart library) |
| Backend/API | Python + FastAPI + Pydantic v2 |
| ORM/migrations | SQLAlchemy 2.x + Alembic |
| Database | PostgreSQL |
| HTTP client | `httpx` with explicit timeouts and connection limits |
| Workflow orchestration | Prefect OSS, self-hosted; Prefect flows/tasks are the actual scheduled/retryable research data workflow |
| Data transformation | Python; use standard library and small focused libraries; pandas/Polars only where they materially help |
| Similarity | RapidFuzz or a similarly maintained library for title/name similarity, with deterministic rules |
| Testing | pytest, HTTPX/FastAPI test client, testcontainers or Docker Compose test database, frontend unit tests, optional Playwright end-to-end tests |
| Quality | Ruff, mypy/pyright, frontend ESLint + TypeScript checks |
| Containerization | Docker Engine + Docker Compose |
| CI/CD | GitHub Actions; deploy backend, frontend, database migrations and Prefect worker/flow deployment |
| Security/supply chain | Gitleaks, Bandit, pip-audit, Trivy; run only supported tools and report tool failures accurately |
| Local observability | Prefect UI, structured application logs, job/connector run tables and dashboard status |

Avoid paid SaaS requirements. The local application should run on Windows 11 with Docker Desktop or on a Linux university VM. Include Windows PowerShell instructions and a Linux/macOS equivalent where practical.

---

## 3. Repository structure

Use a maintainable monorepo. Adjust names if a useful repository already exists, but preserve the separation of concerns.

```text
fris/
  README.md
  CONTRIBUTING.md
  .env.example
  .gitignore
  docker-compose.yml
  Makefile                         # optional convenience commands
  docs/
    architecture.md
    data-dictionary.md
    provider-integrations.md
    identity-resolution.md
    operations-runbook.md
    evaluation-plan.md
    threat-model.md
  backend/
    pyproject.toml
    lockfile
    Dockerfile
    alembic.ini
    migrations/
    app/
      main.py
      core/                        # settings, auth, logging, errors
      api/v1/                      # REST routes and schemas
      db/                          # session, base, models, repositories
      domain/                      # domain types, policies, enums
      services/                    # faculty, import, matching, normalization, dedup
      connectors/
        base.py
        registry.py
        openalex.py
        crossref.py
        orcid.py
        semantic_scholar.py
      workflows/                   # Prefect flows/tasks/deployments
      observability/
      seed/                         # demo tenant/faculty/admin seed (safe, idempotent)
    tests/
      unit/
      integration/
      contract/
      fixtures/
  frontend/
    package.json
    lockfile
    Dockerfile
    src/
      app/
      api/
      components/
      features/
        faculty/
        publications/
        review-queue/
        jobs/
        dashboard/
        settings/
      routes/
      styles/
    tests/
  infra/
    scripts/
      wait-for-db / migration / prefect deployment bootstrap as needed
  .github/
    workflows/
      ci.yml
      deploy.yml
```

Create `.cursor/rules/` project rules or a root `AGENTS.md` if supported by the chosen agent. Put the project invariants from Section 0 there so later agent sessions do not forget them.

---

## 4. Faculty intake and multi-institution data model

### Required and optional intake fields

Required:
- `full_name`
- `tenant_id` (the institution/customer account in FRIS; use the demo tenant for the pilot)

Optional/recommended:
- reported current institution / affiliation text
- department/school
- institutional email (private internal attribute; never send to external providers by default)
- ORCID iD (validate checksum/format and retain verification status/source)
- public faculty profile URL
- explicitly supplied name variants
- previous affiliations with start/end dates, if known
- research interests (weak supporting matching evidence only)
- externally verified provider author IDs (OpenAlex, Semantic Scholar, Scopus, Web of Science, DBLP), each with provider, value, verification source, verified-by and timestamp

Do not require ORCID or institutional email to create a faculty record. Missing identifiers must not block onboarding. Do not invent surname variants. Keep each variant linked to the original faculty profile and its source.

### CSV import

Implement upload with preview, row-level validation, duplicate detection within the tenant, row-specific errors, import batch ID and a downloadable error report. Accept a small pilot file and scale to chunked/streamed imports later. Validate header aliases explicitly. Never fail the entire CSV because one row is invalid; import valid rows and report invalid rows in a transactionally safe manner.

Use this schema as the first sample:

```csv
faculty_name,institution,department,institutional_email,orcid,profile_url,name_variants,previous_affiliations,research_interests
Fei-Fei Li,Stanford University,Computer Science,,0000-0002-7481-0810,https://profiles.stanford.edu/fei-fei-li,"L. Fei-Fei;Feifei Li",,"computer vision; deep learning; robotics"
```

The tenant is `FRIS Demo Tenant`; the row's `institution` is the researcher's reported affiliation, not the tenant identity. Mark the record as demo data in UI and API.

### Database entities

At minimum create the following entities with UUID primary keys, UTC timestamps, foreign keys, tenant ownership where applicable, and indexes appropriate to actual query patterns:

- `tenant` / `institution`
- `user`, `role` or role field, refresh/access-token revocation support as appropriate
- `faculty`
- `faculty_identifier` (identifier type, provider, value, verified flag, evidence, verified date; uniqueness scoped correctly)
- `faculty_name_variant`
- `faculty_affiliation` (organization, department, start/end date, source, confidence)
- `research_interest`
- `connector_registry` / source configuration (enabled, health, provider capabilities, terms link, config; never store secrets in plain config JSON)
- `discovery_job`
- `connector_run`
- `sync_checkpoint`
- `source_record` (provider, provider record ID, retrieved time, source URL, payload hash, allowed raw JSON or safe normalized snapshot, schema version, parse status)
- `author_candidate`
- `match_decision` (score, score version, status, positive/negative evidence, explanation, reviewer decision)
- `publication` (canonical work)
- `publication_source` (source-specific metadata values and provenance)
- `faculty_publication_match` (accepted/probable/review/rejected attribution relationship)
- `authorship` (author order, source spelling, identifiers when provided)
- `publication_relation` (preprint/final, version, correction, translation, extension, related work; do not silently merge)
- `review_item`
- `audit_event`

All tenant-owned entities must include/resolve `tenant_id`. Enforce tenant isolation in API queries and tests. Provider identifiers must be unique within the appropriate provider namespace; DOI uniqueness must be enforced after normalization where non-null. Add indexes for tenant, faculty, publication year, normalized DOI, normalized title, provider ID, job status and timestamps.

Use transactional writes for canonical publication creation and source-link creation. Preserve merge/review audit history and allow authorized reversal of a mistaken merge.

---

## 5. Provider integration strategy

Build a common connector interface, but do not pretend every source supports identical capabilities. Each adapter must declare its supported operations, authentication requirements, limits, terms URL, provenance behaviour and optional capabilities.

### MVP source order

1. **OpenAlex** — primary broad author/work discovery source. Resolve by verified ORCID where supported; use author entity and its works, rather than title search alone. Handle API key configuration if the current API requires/recommends it for the selected quota/pagination path. Implement documented pagination/cursor behaviour and rate limits.
2. **Crossref** — DOI metadata registry and supplementary work discovery/enrichment. Use `query.author` cautiously as a secondary source, not as a guaranteed author identity service. Enrich/verify DOI metadata and preserve Crossref record provenance. Include `mailto` for the polite pool if configured. Respect rate and concurrency limits.
3. **ORCID Public API** — read a supplied ORCID record and public works where the application has registered/obtained public API client credentials and a read-public token. ORCID API discovery/search requires credentials and access tokens; do not assume anonymous direct calls work. Prefer an authenticated ORCID iD collected from the researcher, if the real deployment can support the OAuth flow. The demo seed ORCID is supplied for the test but should still be checked against provider output.
4. **Semantic Scholar** — secondary author/work discovery source. Support optional API key configuration, documented fields, pagination and rate-limit handling. If no API key is configured, use only the access mode currently permitted by official docs and report rate limiting transparently.
5. **IEEE Xplore** — do not scrape. Build a disabled connector/config placeholder only if useful; activate only after an official API key and entitlement are confirmed. If access is not available, explicitly show `not_configured` and explain that IEEE papers may still appear through other indexes if independently indexed there.
6. Later connectors: OpenAIRE, CORE, DBLP, arXiv, PubMed/Europe PMC and institutional repositories via OAI-PMH/DSpace/EPrints. Add through the adapter interface without altering matching/dedup core.

### Connector interface

Implement a typed base contract with methods appropriate to each provider, for example:
- `health_check()`
- `search_author_candidates(faculty_profile, query_plan)`
- `fetch_author_works(provider_author_id, cursor/checkpoint)`
- `lookup_work_by_doi(doi)` where supported
- `normalize_author_candidate(payload)`
- `normalize_work(payload)`

Use Pydantic domain schemas for returned normalized data. Return structured connector results containing `status`, records, pagination/checkpoint, request count, rate-limit metadata, warnings and errors. One provider failing must not erase successful results from other providers.

### Required HTTP behaviour

- Explicit connect/read/overall timeouts.
- Bounded connection pools and per-provider concurrency limits.
- Exponential backoff with jitter for retryable timeouts, 429 and 5xx; respect `Retry-After` when supplied.
- Do not retry normal 400/401/403 responses indefinitely. Authentication/authorization failures should be surfaced and alertable.
- Validate response status, content type, JSON schema and pagination tokens.
- Quarantine malformed responses with safe diagnostics; never crash the entire multi-source flow because one provider returned a malformed record.
- Persist per-provider checkpoints only when the provider's API documents a reliable cursor/updated-since mechanism. Do not invent incremental support.
- Never assume publication counts or API quotas are fixed; capture runtime counts and relevant response headers.
- Cache safe idempotent GET responses where lawful and useful; configure TTL per source and invalidate on refresh as needed.

### Provider documentation record

In `docs/provider-integrations.md`, record for each enabled connector:
- official docs URL and date checked
- endpoint paths and query parameters actually used
- auth/token setup and `.env` variable names
- pagination method
- documented or observed rate/concurrency policy
- source metadata fields mapped to FRIS schema
- known coverage limitations
- sample successful response shape (redacted, no credentials)
- real/manual smoke-test command and result

---

## 6. Research Data Pipeline — required Prefect workflow

This is the functional automation the university needs. Do not implement it as a script that a developer must manually run. It must be orchestrated by Prefect with observable flow/task states, retries, logs and schedules.

### Trigger types

- Faculty created or materially updated.
- Authorized admin presses “Run discovery now”.
- Nightly/weekly incremental schedule (configurable; start conservatively, e.g. weekly).
- Retry/recovery for a failed or partial connector run.
- Explicit backfill after enabling a new source.

### Flow stages

1. Create `discovery_job` and correlation ID; capture initiating user/trigger and selected sources.
2. Load faculty identity, aliases, verified identifiers and affiliation timeline.
3. Build provider-specific query plan. Start with verified ORCID when present; otherwise search full name and supplied variants with institution/affiliation context where the provider supports it. Do not use the institutional email as a default public search query.
4. Invoke enabled providers using bounded parallel tasks, respecting provider rate and concurrency limits.
5. Persist source responses/metadata with provider ID, retrieval time, URL, payload hash and allowed raw record; preserve raw/source values separately from normalized values.
6. Validate payloads and map provider schema to a common typed schema. Quarantine invalid records with reason.
7. Resolve candidate author profiles against the faculty record using the scoring policy in Section 7.
8. Fetch works only from candidates that meet the configured policy; low-confidence candidates may be retained for the review queue, but their works must not be automatically attributed to the faculty.
9. Normalize titles, DOI, authors, author order, year/date, venue, publication type, URL, abstract/licence/open-access fields where legitimately provided.
10. Deduplicate using DOI-first and conservative metadata corroboration. Create review items for ambiguous records.
11. Reconcile canonical fields by explicit per-field source preference while retaining every source variant and provenance.
12. Persist canonical publications, faculty-publication match decisions, authorship and source links transactionally/idempotently.
13. Update dashboard summary/materialized views if needed; record per-source counts, latency, errors, last success and partial coverage.
14. Finalize the job as `succeeded`, `partial`, `failed` or `cancelled` with human-readable summary.

### Failure policy

- A provider timeout/5xx/429 should not stop other sources; retry within bounded policy.
- 429: honor `Retry-After`; otherwise use bounded exponential backoff with jitter.
- 401/403: mark that connector as auth/permission failed, do not spin retries.
- Bad payload: quarantine and continue processing valid records.
- If one or more sources succeed and another fails, final job is `partial`, not fully `succeeded`.
- If all configured sources fail, final job is `failed`.
- Never delete previously accepted canonical records because a source is temporarily unavailable.
- Use idempotency keys for trigger/run creation; support cancellation and recovery.

### Scheduling and worker lifecycle

Register a Prefect deployment for the research discovery flow. Start a self-hosted Prefect server and worker in Docker Compose. The application must be able to submit discovery runs through the configured Prefect deployment, and the worker must execute the deployed code. Provide a startup/bootstrap command that creates or verifies the work pool and deployment using the syntax for the pinned Prefect version. Confirm schedule registration and worker heartbeat in the UI. Do not use a custom infinite sleep loop instead of Prefect.

---

## 7. Author identity resolution and confidence scoring

Implement an explainable, deterministic, rules-based MVP. Do not use an LLM or train a classifier on unlabelled/generated matches. Scores are initial engineering hypotheses and must be calibrated using manually labelled records.

### Evidence hierarchy

Strongest to weakest:
1. Exact ORCID match to an ORCID associated with the faculty profile, with provenance and no contradictory identifier.
2. Verified external author ID already linked to the faculty profile, with who/when/how verification evidence.
3. Full/variant name plus current or historical institutional affiliation match.
4. Name plus co-author continuity.
5. Research-topic continuity.
6. Publication chronology consistent with dated affiliation history.
7. Name-only similarity is candidate-generation evidence only; never auto-verify an ambiguous identity.

Institutional email is restricted internal context. Do not transmit it to providers by default and do not treat it as a universal scholarly author-search identifier.

### Initial 0–100 score (use this version consistently)

| Signal | Maximum points |
|---|---:|
| Verified ORCID or verified linked provider author identifier | 40 |
| Institution / affiliation match | 20 |
| Full name or supplied variant similarity | 15 |
| Co-author continuity | 10 |
| Research-topic continuity | 5 |
| Chronology / affiliation timeline consistency | 10 |
| **Maximum** | **100** |

For each signal, store the raw evidence, normalized evidence, calculation and points awarded. Missing evidence is neutral/zero; do not invent evidence. Avoid double-counting the same fact across multiple signals.

### Decision bands

- **85–100: Verified candidate** only if a strong identifier condition is satisfied (verified ORCID or verified linked author ID) AND there is no material contradictory evidence.
- **70–84: Probable** — review recommended; do not silently treat as verified.
- **50–69: Review required** — do not automatically attribute.
- **Below 50: Rejected/unassigned** for automatic attribution; keep audit/candidate information only as policy permits.

A hard contradiction (e.g. a conflicting ORCID, incompatible verified author ID, or strong affiliation/time contradiction) must force `review_required` or `rejected` regardless of numeric score. A high score must never override a contradiction.

### Explainability and reviewer workflow

Every match decision must persist:
- score and score-model version
- decision status
- positive and negative evidence arrays
- provider and candidate author IDs
- source URL and retrieval time
- human-readable explanation
- reviewer ID, timestamp and decision rationale when manually reviewed
- previous decision / change history

Authorized reviewer actions: accept, reject, defer, link a verified provider author ID, correct affiliation dates, request rediscovery. Every action creates an audit event. A manual accept must not erase the original computed score or evidence.

The UI must display the reason, not only a number. Example: “ORCID matched; name matched; institution matched; affiliation dates unavailable; no contradiction detected.”

---

## 8. Publication cleaning, normalization and deduplication

### Keep source and canonical values separate

- Keep original provider title, DOI text, author strings/order, date/year, venue and type in `publication_source` / `source_record`.
- Store normalized comparison values separately.
- Store field-level provenance for canonical display values (provider, provider record ID, source URL, retrieval time, selection rule).
- Do not silently overwrite conflicting values; log reconciliation decisions.

### Normalization rules

- DOI: trim whitespace, remove `doi:` and DOI URL prefixes, lowercase for comparison, validate conservatively; retain original DOI string from each provider.
- Title: Unicode normalize; create a lowercase punctuation-normalized/collapsed whitespace comparison value; retain display title unchanged.
- Author names: preserve source spelling and author order; create normalized tokens for matching only.
- Publication date/year: preserve source date and date type; do not silently replace online-first year with print year.
- Venue: preserve source venue title and ISSN/ISBN where available.
- Publication type: map to controlled local vocabulary and preserve original provider type.
- URL: validate and store canonical/landing URLs separately from source links. Do not assume a URL implies open-access rights.
- Abstract and licence fields: include only when returned and permitted; do not scrape them from restricted publisher pages.

### Deduplication policy

1. Exact same valid normalized DOI → consolidate as one canonical publication, retaining every provider source record and variant.
2. DOI conflicts (same DOI but materially conflicting title/authors/year) → review item; do not blindly merge.
3. No DOI → compare normalized title; require strong similarity (initial threshold may be 0.96 but must be treated as provisional), compatible publication year, author overlap and compatible venue before proposing a merge.
4. Ambiguous no-DOI pair → manual review; do not auto-merge.
5. Preprint/final article, conference/journal extension, correction, translation, chapter and other related variants may be related works, not duplicates. Store relation type; do not silently collapse.
6. Keep a merge log and support an authorized reversal.

Deduplication must be idempotent and tested against both duplicate and non-duplicate cases. Do not deduplicate solely by title.

---

## 9. API and frontend requirements

### Backend REST API (versioned)

Implement, validate and document at least:

- `GET /health/live`
- `GET /health/ready`
- `POST /api/v1/auth/login` (and refresh/logout if implemented)
- `GET /api/v1/me`
- `POST /api/v1/faculty`
- `GET /api/v1/faculty`
- `GET /api/v1/faculty/{faculty_id}`
- `PATCH /api/v1/faculty/{faculty_id}`
- `POST /api/v1/faculty/import/preview`
- `POST /api/v1/faculty/import/commit`
- `POST /api/v1/faculty/{faculty_id}/discover`
- `GET /api/v1/faculty/{faculty_id}/publications`
- `GET /api/v1/faculty/{faculty_id}/candidates`
- `GET /api/v1/discovery-jobs`
- `GET /api/v1/discovery-jobs/{job_id}`
- `GET /api/v1/connectors/status`
- `GET /api/v1/reviews`
- `POST /api/v1/reviews/{review_id}/decision`
- `GET /api/v1/dashboard/overview`
- `GET /api/v1/dashboard/faculty/{faculty_id}`

Use Pydantic request/response schemas, consistent pagination/filter/sort parameters, validation errors, safe error messages and OpenAPI docs. Do not expose raw secrets or private fields in API responses. Apply tenant filters on every query and test cross-tenant access denial.

### Frontend pages

1. Login.
2. Dashboard: total faculty, canonical publications, publication years, sources connected, pending reviews, latest syncs, connector health and partial coverage warnings.
3. Faculty directory: search/filter, demo badge, import button, add faculty form.
4. Faculty profile: identity details, identifiers, affiliation history, discovery status and publication list.
5. Publication detail: canonical fields, source provenance, DOI/source links, author list and attribution evidence.
6. Review queue: probable/review-required matches and ambiguous dedup pairs with evidence and accept/reject/defer controls.
7. Jobs/monitoring: flow history, per-source success/failure, records fetched, retries, duration and error summary.
8. Connector settings: enabled/disabled state and credential status; never reveal stored secret values.

Use accessible labels, loading/error/empty states, responsive layouts and pagination. Show confidence status with text and colour, but never imply a probability unless it has been calibrated as one. Call it a score, not “85% probability”.

---

## 10. Security and governance

- JWT-based authentication or a comparably secure session approach; secure password hashing (Argon2id preferred).
- Roles: `admin`, `research_officer`, `reviewer`, `viewer` (enforce backend authorization; hiding frontend buttons is not security).
- Tenant-level data isolation and role-based access tests.
- Environment variables for secrets; `.env` excluded from Git; `.env.example` contains placeholders only.
- CORS allow-list, request size limits, upload limits, file extension/content checks and CSV formula-injection-safe error export.
- Parameterized queries/ORM, Pydantic validation, output escaping, no arbitrary URL fetching from user-supplied profile URLs without SSRF-safe controls.
- Audit admin login, faculty changes, imports, discovery triggers, review decisions, identifier changes and merge/unmerge actions.
- Limit log content; do not log tokens, client secrets, institutional emails or full raw provider payloads by default.
- Define a data retention and deletion policy. Support deletion/anonymization of a faculty record while preserving required non-personal operational audit evidence according to policy.
- Add a short threat model in `docs/threat-model.md` covering unauthorized access, tenant leakage, secret leakage, malicious CSV, SSRF, provider payload injection and supply-chain risk.

---

## 11. Software CI/CD pipeline — actual build/deploy automation

Implement GitHub Actions workflows that execute on pull requests and pushes. Failing quality, tests or security gates must block release.

### CI stages

1. Checkout and dependency setup using lockfiles/caching.
2. Backend formatting/lint/type checks (Ruff and selected type checker).
3. Frontend lint/typecheck/build.
4. Backend unit tests.
5. Connector contract tests with mocked success, pagination, duplicates, malformed payload, timeout, 429, 401/403 and 5xx responses.
6. Integration tests against PostgreSQL (migrations, repository writes, tenant isolation, API routes, Prefect flow using mocked providers).
7. Deduplication and matching regression tests.
8. Security/supply-chain checks: Gitleaks, Bandit, pip-audit and Trivy image/filesystem scan (pin and configure tools appropriately).
9. Build versioned backend/API, Prefect worker and frontend container images.

### CD stages

1. Deploy to staging only when required secrets/runner/host have been explicitly configured. Do not claim a deployment happened if no target exists.
2. Apply database migrations safely.
3. Deploy/update API and frontend.
4. Deploy/update the Prefect worker and register/update flow deployment and schedule. **Updating only the API/frontend is incomplete.**
5. Run smoke tests: API live/ready, DB connectivity, Prefect server/worker heartbeat, deployment/schedule exists, mocked end-to-end discovery executes, dashboard loads.
6. Promote to production through a protected environment/manual approval where applicable.
7. Keep previous immutable image tags and document rollback. Verify the previous flow/worker image and API are restored; never use `latest` as the only rollback reference.

Use GitHub-hosted runners for CI where possible. A university-hosted server may run Docker Compose for staging/demo. Do not expose a Docker socket or privileged runner unnecessarily. Document required GitHub Secrets and environment configuration without hard-coding them.

### Distinguish these two automations in docs and UI

- Prefect Research Data Pipeline: runs when faculty is added/updated, on manual refresh, and on schedule.
- GitHub Actions Software CI/CD: runs when source code changes; tests, builds, deploys and verifies the app and Prefect workflow code.

Security scans are only a stage in CI. They are not the research-data automation and are not the complete CI/CD pipeline.

---

## 12. Docker Compose and local run experience

Provide services for:
- PostgreSQL with persistent volume and health check.
- FastAPI backend.
- React frontend.
- Prefect server.
- Prefect worker.

Use a startup/migration/bootstrap sequence that waits for PostgreSQL readiness, runs Alembic migrations, creates/validates the Prefect work pool/deployment, and seeds only the explicitly requested demo tenant/user/researcher. Avoid race conditions and restart loops that hide a broken initialization.

Required developer experience (adapt actual commands to implementation and document them):

```powershell
Copy-Item .env.example .env
# Edit .env and set strong local-only secrets / optional provider keys

docker compose up --build -d
docker compose ps
docker compose logs -f api prefect-worker
```

Provide URLs for frontend, FastAPI docs, Prefect UI and health endpoints. Provide stop/reset commands with a warning before deleting database volumes. Include a command to seed the pilot idempotently and a command/API/UI action to trigger the first discovery job.

The app must start even when optional provider credentials are missing. It must show which sources are not configured. The core OpenAlex/Crossref workflow should be demonstrably runnable with available public access and local settings, subject to current provider limits.

---

## 13. Testing and acceptance criteria

Create actual automated tests, not just a checklist. The project is not complete until the relevant checks run successfully.

### Unit tests

- ORCID format/checksum validation and normalization.
- DOI prefix removal, lowercase comparison and invalid DOI handling.
- Unicode/title normalization and author-name tokenization.
- Confidence score weights, bands, hard contradictions and evidence explanation.
- Tenant scoping.
- Idempotency keys and upsert behaviour.
- DOI-based deduplication.
- No-DOI duplicate candidates with title/year/author/venue corroboration.
- Preprint/final and related versions are not auto-collapsed.
- CSV header/row validation and safe error output.

### Connector contract tests (mocks only)

For each adapter: valid response, empty result, pagination, duplicated record, malformed payload, 429 with Retry-After, 5xx, timeout, auth failure, unexpected schema change and partial page failure.

### Integration tests

- Apply migrations to a fresh PostgreSQL database.
- Create demo tenant and faculty.
- Submit an API-triggered Prefect discovery job.
- Execute the Prefect flow with mocked provider responses.
- Persist raw/source, normalized and canonical records.
- Refresh the same faculty a second time; assert no duplicate canonical works or source links.
- Fail one provider and verify successful providers' data remains and the job is `partial`.
- Confirm a reviewer can accept/reject a candidate and the audit event is written.
- Confirm a user from Tenant A cannot read Tenant B's faculty/publications/jobs.

### Live smoke test (separate from automated tests)

If outbound network and provider access are available, run one live discovery for the Fei-Fei Li demo profile. Show per-source statuses and actual returned counts. Confirm the returned candidate's ORCID/name/affiliation against current provider metadata. Fetch works only through candidates accepted by policy. Crossref may find overlapping work records; dedup should consolidate DOI matches while preserving source provenance. Clearly label source coverage and limitations.

If a live provider fails due to quota, key, outage or network, report that specifically and still run mocks for deterministic CI. Do not substitute mocked success for live validation.

### MVP acceptance checklist

- Faculty can be added manually and through CSV without a publication list.
- Pilot is clearly marked demo-only and not misrepresented as university faculty.
- Adding faculty automatically enqueues a Prefect discovery run.
- Admin can manually refresh; a scheduled refresh runs via Prefect.
- OpenAlex and Crossref connectors are implemented end-to-end; ORCID is implemented with explicit credential status; Semantic Scholar is implemented or clearly marked pending with reason (preferred: implement it).
- IEEE is disabled until official access is approved; no scraping.
- Per-source retries, rate limits, pagination and status are visible.
- Raw/source provenance and normalized data are both preserved.
- Identity status and score are explainable; name-only matches are never auto-verified.
- DOI duplicates consolidate; ambiguous no-DOI pairs go to review.
- Re-running discovery is idempotent and incremental where supported by the provider.
- Dashboard displays publication records, source provenance, last sync, connector status and review queue.
- CI runs lint, type, test, security and build checks; failures block release.
- CD builds/deploys versioned images and updates the Prefect worker/flow, not only the web UI.
- Staging smoke tests verify the complete deployed application and workflow.
- README/runbook explains setup, secrets, imports, discovery, schedules, deployment, rollback and known limitations.

---

## 14. Evaluation plan — do not fabricate results

After the pilot works, create an evaluation dataset of 10–20 faculty across departments (or the instructor-approved sample), including common names, initials, spelling variants and researchers with/without ORCID. The pilot researcher alone is a technical smoke test, not a sufficient research evaluation dataset.

Create a manually verified gold-standard publication list using official faculty pages, ORCID and publisher/DOI landing pages. Record verification evidence and retrieval date. Then compare:

- Baseline 1: one provider + name-only search.
- Baseline 2: union of provider results without deduplication.
- Baseline 3: identifier-only matching.
- Proposed system: context-aware score + review workflow + DOI-first dedup + source provenance.

Measure precision, recall, F1, false attribution/false merge rate, duplicate reduction, unique source contribution, metadata completeness, median/p95 runtime, API request counts, incremental refresh benefit and failure recovery. Do not claim accuracy until the gold-standard comparison is complete. Prefer precision for automatic attribution because false attribution is costly.

---

## 15. Future scale path

Design for scale now; add infrastructure only when measured volume requires it.

**Stage 1 — pilot:** one demo tenant, one researcher, PostgreSQL, single Prefect worker, bounded provider concurrency, Docker Compose.

**Stage 2 — department:** CSV bulk import, 10–100+ faculty, incremental scheduled refresh, indexes, pagination, review workflow, per-provider throttling and job observability.

**Stage 3 — university:** multiple departments, larger faculty sets, separate Prefect workers, controlled queue/work-pool concurrency, connection pooling, retention policies, backups, metrics/alerts and background bulk imports.

**Stage 4 — multi-university:** strict tenant isolation, tenant-configurable connectors/schedules, tenant-specific institution aliases, per-tenant role policies, optional separate schemas/databases if justified, operational monitoring and disaster recovery.

Do not jump directly to Kubernetes/Kafka. First measure bottlenecks: provider latency/rate limits, DB write load, flow duration, number of pending tasks, dashboard query latency and worker saturation. Add queueing/caching/orchestration infrastructure only when metrics justify it.

---

## 16. Build sequence — execute in order

### Phase 0 — repository and environment inspection
- Inspect workspace and runtimes.
- Create `AGENTS.md`/Cursor rules from Section 0.
- Scaffold repository if empty; document prerequisites and env variables.
- Commit or checkpoint work logically (do not make Git commits unless configured/authorized; at least preserve clear diffs).

### Phase 1 — backend foundation
- FastAPI app, settings, structured logging, PostgreSQL, SQLAlchemy models, Alembic migrations, auth/RBAC and tenant isolation.
- Implement health routes and initial faculty CRUD.
- Tests and Docker Compose must pass before continuing.

### Phase 2 — intake and pilot setup
- Manual faculty form API, CSV preview/commit, validation, demo tenant seed and pilot researcher.
- Frontend faculty add/import screens.
- Tests for bad rows, duplicates and demo flags.

### Phase 3 — connectors and normalization
- Implement OpenAlex and Crossref first, then ORCID and Semantic Scholar according to credentials/access.
- Base connector interface, provider status, retries, pagination and provenance.
- Unit/contract tests. Do not proceed with fake data masquerading as a live provider.

### Phase 4 — matching, dedup and Prefect automation
- Implement confidence score and review queue.
- DOI normalization, canonical publication and source mapping.
- Prefect flow/deployment, API trigger, scheduled refresh, retry and partial-failure semantics.
- Integration tests with mocked APIs and idempotent rerun test.

### Phase 5 — frontend completion and live pilot
- Dashboard, faculty profile, publication listing/detail, review queue and job/source monitor.
- Run actual live pilot discovery where provider/network credentials allow.
- Show source counts and limitations; do not invent output.

### Phase 6 — CI/CD, security and release readiness
- GitHub Actions quality/test/security/build workflows.
- Staging deployment configuration, migrations, flow/worker deployment, smoke tests and rollback plan.
- README, integration docs, runbook, threat model and evaluation plan.

**Do not mark a phase complete if its tests fail or critical acceptance items are missing.** If time or context limits prevent completion in one agent session, leave a precise `docs/BUILD_STATUS.md` containing completed work, failing commands, blockers and the exact next task. Do not claim the product is finished.

---

## 17. Final response required from the coding agent

When implementation work is complete, respond with:

1. What was actually implemented.
2. Exact local setup/run commands for Windows PowerShell.
3. Frontend/API/Prefect URLs.
4. Which providers passed a live test, which were tested only with mocks, and which need credentials/approval.
5. Actual test commands and pass/fail counts.
6. Actual pilot discovery results (only if run); include number of candidate author profiles, accepted/probable/review/rejected statuses, publications retrieved per source, canonical publications after dedup and source errors.
7. How to add the second faculty member via UI/CSV.
8. What is not yet done and why.

Do not say “fully working”, “100% accurate”, “all IEEE papers found”, “all publications found” or “production ready” unless the evidence actually supports that claim.

---

## Official references the agent must consult and keep current

- OpenAlex API documentation: https://docs.openalex.org/
- Crossref REST API: https://www.crossref.org/documentation/retrieve-metadata/rest-api/
- Crossref access/authentication and request limits: https://www.crossref.org/documentation/retrieve-metadata/rest-api/access-and-authentication/
- ORCID API tutorials: https://info.orcid.org/documentation/api-tutorials/
- ORCID Registry search and credentials: https://info.orcid.org/documentation/api-tutorials/api-tutorial-searching-the-orcid-registry/
- Semantic Scholar Academic Graph API: https://api.semanticscholar.org/api-docs/
- Prefect documentation: https://docs.prefect.io/
- Cursor Agent documentation: https://cursor.com/docs/agent/overview
- Google Antigravity documentation (alternative agent): https://antigravity.google/docs/getting-started

**Important:** API terms, endpoints, quotas, software versions and deployment features can change. Verify before coding; cite the official URL and date in the project docs.
