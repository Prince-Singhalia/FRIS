# FRIS build status

**Updated:** 26 November 2026
**Repository:** `Prince-Singhalia/FRIS`  
**Working branch:** `main`  
**Starting code revision:** `291fbc5` (after removing the two handoff-document commits from the local branch)

## Implemented in this work

- Added an Alembic initial revision that creates the registered SQLAlchemy schema, including PostgreSQL enum types. The migration is for a clean database; subsequent schema changes must use new revisions and must not edit this baseline after release.
- Added fail-fast API bootstrap: migrations must succeed before Uvicorn starts. Demo seeding is opt-in, rejects production mode and placeholder/weak seed passwords, and is idempotent for the demo tenant, admin, and pilot record.
- Moved the pilot CSV to `backend/fixtures/pilot_faculty_seed.csv` and made the demo seed read that CSV.
- Fixed faculty CSV intake so real tenants are not tagged as demo, semicolon-separated previous affiliations are persisted as historical affiliations, and duplicate names, ORCID, email, and profile URL values receive row-level handling.
- Restricted demo records to demo tenants and added tenant-specific login as `tenant-slug/username`; refresh and `/me` lookups are scoped to the token tenant.
- Wired the manual discovery API route to the named Prefect deployment. Jobs are committed before submission, Prefect run IDs are stored, and submission failures produce a failed job plus HTTP 503 instead of a pending job with no work behind it.
- Made flow-level failures persist a terminal failed job state. Partial provider outcomes are retained in discovery processing and connector-run status. Crossref work-search results are handled as supplementary works rather than author identities.
- Persisted tenant-scoped source-record hashes, normalized provider snapshots, retrieval times, source URLs, and connector-run links. Raw provider payload retention remains disabled pending a terms review. Canonical field provenance is recorded.
- Made repeated DOI and provider-ID-only publication persistence reuse existing canonical rows; repeated matching scores update the latest decision rather than multiplying identical rows.
- Reworked Compose to remove the nonexistent frontend service and hidden `|| true` startup fallbacks. Database credentials and signing key must be configured; the Prefect work pool and manual deployment are registered before the API starts.
- Organized reference files under `docs/specifications/` and `docs/archive/`; removed the two redundant Antigravity prompt files. The team handoff remains outside this repository in the parent `CICD PROJECT` directory.
- Restored the backend Ruff gate by applying safe import/style fixes, formatting the backend, replacing string enums with `StrEnum`, narrowing broad validation assertions, and explicitly allowing FastAPI's dependency-injection defaults.
- Made the published PostgreSQL host port configurable with `POSTGRES_HOST_PORT`, allowing local startup without changing the container-internal connection port.
- Fixed Prefect task-result collection in the async discovery flow. Added a unit regression test and confirmed that worker execution updates the job to a terminal state instead of failing with an invalid `await`.
- Replaced `python-jose` with PyJWT, retained the explicit JWT algorithm allowlist, and added token round-trip and invalid-token tests. Raised pytest and setuptools constraints to versions that address the dependency advisories.
- Hardened the runtime image to install only application dependencies, remove pip/setuptools, and run without Uvicorn reload. Added a backend `.dockerignore` so local virtualenvs, tests, build output, and caches are not copied into runtime images.
- Extended backend CI with Bandit, `pip-audit`, a runtime-image build and Trivy scan, and Gitleaks.
- Resolved the backend mypy findings, added the `types-passlib` development stub dependency, and made mypy a CI gate.
- Added PostgreSQL-backed auth integration coverage for ambiguous usernames, tenant-specific login, and cross-tenant `/auth/me` denial. CI runs it against a fresh PostgreSQL service after applying migrations.
- Built the React/TypeScript frontend against the existing API contracts: tenant login, dashboard, faculty directory and profiles, CSV preview/commit, publication provenance, discovery jobs, review decisions, and connector readiness.
- Added responsive layouts, loading/error/empty states, role-aware action visibility, and no fabricated provider/publication records. The demo researcher is explicitly labelled external; confidence is displayed as a score.
- Added an in-memory access/refresh token client, tenant-qualified OAuth form login, authenticated API requests, token refresh, and multipart CSV upload.
- Added frontend unit tests, TypeScript/lint/build checks, a non-root Nginx runtime image, Compose frontend service, and a frontend CI job that builds/scans the image and smoke-tests its served app.
- Patched current Alpine runtime packages in the frontend image at build time after Trivy identified upstream-fixable base-image advisories; the rebuilt image has no HIGH or CRITICAL findings in the local Trivy scan.

## Validation and environment

Verified in the current continuation:

- `backend/.venv/bin/python -m pytest -q`: **62 passed, 1 skipped** (Python 3.11.17; the PostgreSQL integration test was run separately).
- `backend/.venv/bin/python -m ruff check app tests`: passed.
- `backend/.venv/bin/python -m compileall -q app tests`: passed.
- `backend/.venv/bin/python -m mypy app`: passed for 40 source files.
- `backend/.venv/bin/python -m bandit -q -r app`: passed. Bandit reports a warning for the scoped B104 suppression on the intentional container bind address.
- `backend/.venv/bin/python -m pip_audit --skip-editable`: no known vulnerabilities.
- PostgreSQL auth integration test: **1 passed** against the local PostgreSQL service; the test uses unique tenant/user rows and cleans them up.
- Alembic `upgrade head` and `downgrade base`: passed against a newly created, disposable PostgreSQL database.
- Built runtime image imports for PyJWT and the FastAPI application passed. Confirmed the image excludes `.venv`, tests, pip, and pytest; Trivy found no HIGH or CRITICAL vulnerabilities.
- `docker compose config -q` with disposable local credentials: passed.
- `docker compose up -d --build` with disposable local credentials and `POSTGRES_HOST_PORT=55432`: all services started; the database became healthy, migration revision `20261124_0001` was current, and API readiness returned `{"status":"ready","database":"connected"}`.
- Explicit demo startup seeded the demo tenant/admin and external researcher. Tenant login and `/auth/me` succeeded.
- Manual API discovery submitted to Prefect and completed with job status `succeeded`. OpenAlex (1 record), Crossref (11 records), and Semantic Scholar (10 records) reported `succeeded` in that run. This was a real local worker run and live provider request, not a mock.
- A first live run exposed the flow-result bug; the flow persisted a failed job as intended. After the fix, the rebuilt worker completed successfully.
- After the PyJWT and runtime-image changes, the rebuilt API passed readiness, tenant-specific login and `/auth/me`; a new Prefect discovery run completed with `succeeded` and three connector runs.
- `git diff --check`: passed.
- `frontend/npm run build`: passed (TypeScript project build and Vite production bundle).
- `frontend/npm test`: **7 passed** (authentication, CSV preview/commit, review decision, publication provenance, OAuth form encoding, bearer token attachment, and API error/session behavior).
- `frontend/npm run lint`: passed with no diagnostics.
- `frontend/npm run typecheck`: passed.
- `docker build --tag fris-frontend:local ./frontend`: passed.
- Frontend runtime smoke: the Nginx container served the FRIS document and proxied `/api/v1/auth/me` to the live API, which correctly returned HTTP 401 without credentials.
- `trivy image --scanners vuln --severity HIGH,CRITICAL --ignore-unfixed --exit-code 1 fris-frontend:local`: passed with **0 HIGH / CRITICAL** findings after the base-package update.
- `docker compose config --quiet` with disposable Compose interpolation values: passed.
- `git diff --check`: passed.

Not verified / blocked:

- Gitleaks is configured in CI but has not been run locally.
- The default host port 5432 is occupied by an unrelated local container; FRIS was verified on host port 55432. The unrelated container was left untouched.
- Broader PostgreSQL API integration, cross-tenant denial, failure injection, repeated-run persistence, and staging remain unverified.

## Remaining work

### Aksh — backend/database/integration follow-up

- Replace the metadata-driven initial revision with a frozen explicit baseline if the team wants immutable schema definitions before shipping.
- Expand PostgreSQL API integration coverage for faculty import behavior, persistence idempotency, and Prefect submission failure/success; cross-tenant denial across other resource routes and repeat-run persistence remain unverified.
- Decide and implement the approved auto-discovery behavior for newly created/imported faculty; the current API provides an explicit manual discovery trigger.

### Prince — provider ingestion

- Verify provider documentation and adapter behavior; add contract tests for paging, malformed responses, authentication/rate limits, timeout, and partial provider failures.
- Preserve provider provenance and ensure an unavailable provider is never counted as success. One live run exercised OpenAlex, Crossref, and Semantic Scholar; broader provider behavior remains unverified.

### Yash — matching and deduplication

- Complete explainable matching evidence and conservative no-DOI corroboration; add production-service tests for contradictions, boundaries, DOI validity, author/venue evidence, and idempotent reruns.

### Shivanya — frontend and software CI/CD

- The frontend and frontend quality/image-smoke job are implemented. Remaining: broader end-to-end UI/API checks, scheduled Prefect deployment verification, release/deployment workflow, rollback procedure, and staging configuration. No staging target is configured.

## Key limitations

The frontend is an API-backed MVP, not a fully validated production client. There is no end-to-end database/API UI test suite, no broad provider verification, and no configured staging deployment. The backend unit tests and frontend quality checks pass, and one local worker run succeeded; broader database/API behavior remains unverified. The team should not describe FRIS as a complete or production-ready pilot until the integration gates in the implementation brief pass.
