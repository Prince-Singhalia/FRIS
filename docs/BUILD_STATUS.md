# FRIS build status

**Updated:** 24 November 2026  
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

## Validation and environment

No tests, compile checks, container startup, or live provider calls were run during this implementation session. The available Python is 3.9.6, below this project’s Python 3.11 minimum; Docker is installed but its daemon is not running. A normal sandboxed push initially failed because DNS resolution was unavailable; an authorized push then force-updated remote main with the implementation commit. Do not treat the changes as runtime-verified.

## Remaining work

### Aksh — backend/database/integration follow-up

- Run the backend unit suite, Ruff, and type checks with Python 3.11+; fix failures in production code.
- Run `alembic upgrade head` and `alembic downgrade base` against a clean PostgreSQL database. Replace the metadata-driven initial revision with a frozen explicit baseline if the team wants immutable schema definitions before shipping.
- Start Compose with a configured `.env`; verify migration, explicit seed, login, tenant isolation, manual Prefect submission, worker execution, flow failure state, and repeat-run persistence.
- Add PostgreSQL API integration tests for cross-tenant denial, import behavior, idempotency, and Prefect submission failure/success.
- Decide and implement the approved auto-discovery behavior for newly created/imported faculty; the current API provides an explicit manual discovery trigger.

### Prince — provider ingestion

- Verify provider documentation and adapter behavior; add contract tests for paging, malformed responses, authentication/rate limits, timeout, and partial provider failures.
- Preserve provider provenance and ensure an unavailable provider is never counted as success. Live calls remain unverified.

### Yash — matching and deduplication

- Complete explainable matching evidence and conservative no-DOI corroboration; add production-service tests for contradictions, boundaries, DOI validity, author/venue evidence, and idempotent reruns.

### Shivanya — frontend and software CI/CD

- Implement the React frontend and Dockerfile, then update Compose and CI to cover API, frontend, Prefect worker/flow, security scans, image builds, smoke tests, and rollback. No staging target is configured.

## Key limitations

There is no frontend, no end-to-end database/API coverage, no live-provider verification, and no configured staging deployment. The team should not describe FRIS as a complete or production-ready pilot until the integration gates in the implementation brief pass.
