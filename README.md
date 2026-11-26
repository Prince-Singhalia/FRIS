# Faculty Research Intelligence System (FRIS)

FRIS is a free-first research intelligence system for discovering scholarly works from permitted provider APIs, resolving author identities, deduplicating works, and preserving source evidence. The repository includes a FastAPI/PostgreSQL backend, a React/TypeScript frontend, and a Prefect discovery deployment. Production release and staging deployment are not configured.

## Current implementation

| Area | Status | Notes |
| --- | --- | --- |
| Faculty and tenant API | Partially implemented | Tenant-scoped faculty CRUD and CSV preview/import are present. |
| CSV intake | Implemented for current schema | Validates name, ORCID, profile URL, and email; persists previous affiliations; real tenant imports are not marked demo. |
| Database | Initial migration added | Alembic bootstraps the SQLAlchemy model metadata for a clean database. |
| Demo seed | Explicit and opt-in | Separate `FRIS Demo Tenant`, external-researcher label, password guard, and CSV-backed seed input. |
| Discovery trigger | Wired to Prefect | Faculty creation and successful CSV imports automatically create jobs; the API persists jobs before Prefect submission and reports failed submissions. Manual triggers remain available for retries. |
| Provider adapters | Present, not live-verified here | OpenAlex, Crossref, ORCID, and Semantic Scholar modules are included. Credentials and provider behavior remain environment-dependent. |
| Matching and deduplication | Partially implemented | Existing production services are wired into the discovery flow; conservative evidence and persistence hardening remain. |
| Frontend | MVP implemented | Dashboard, faculty directory/profile, CSV preview/import, discovery jobs, review queue, and provider readiness screens use the versioned API. |
| Software CI/CD | Quality gates implemented | GitHub Actions runs backend and frontend checks, builds/scans runtime images, and smoke-tests the frontend image. Image release, staging deployment, and rollback are not configured. |

See [the current build status](docs/BUILD_STATUS.md), [operations runbook](docs/operations-runbook.md), [implementation brief](docs/specifications/master-implementation-brief.md), and [dated repository audit](docs/archive/repository-audit-2026-11-24.md).

## Local setup

Requirements: Docker Desktop with Compose, or Python 3.11+ and PostgreSQL 16 for direct backend development.

1. Copy `.env.example` to `.env`.
2. Replace `POSTGRES_PASSWORD` and `SECRET_KEY` with unique values. `SECRET_KEY` must contain at least 32 characters. Startup rejects placeholders.
3. To create the isolated demo tenant and demo admin locally, set `FRIS_SEED_DEMO=true` and set `ADMIN_DEFAULT_PASSWORD` to a unique password of at least 12 characters. Leave demo seeding off for production.
4. Start the local stack:

```sh
docker compose up --build
```

The API waits for PostgreSQL health, applies Alembic migrations, optionally seeds demo data, then starts. Any migration or enabled seed failure stops startup. Compose registers the `fris-discovery/manual` Prefect deployment, starts a process worker, and serves the frontend on port 3000 by default. Override `FRONTEND_HOST_PORT` to change the published port.

Local endpoints:

- FRIS frontend: <http://localhost:3000>
- API: <http://localhost:8000>
- Swagger UI: <http://localhost:8000/docs>
- Liveness: <http://localhost:8000/health/live>
- Readiness: <http://localhost:8000/health/ready>
- Prefect UI: <http://localhost:4200>

If demo seeding is enabled, sign in with username `fris-demo/admin` and the configured `ADMIN_DEFAULT_PASSWORD`. Tenant-specific login uses `tenant-slug/username`; a bare username works only when it is unique across tenants.

For frontend development with Vite, run these commands from `frontend/`. The Vite development server proxies `/api` requests to `http://localhost:8000`; set `FRONTEND_API_PROXY_TARGET` if the backend is elsewhere.

```sh
npm ci
npm run dev
```

For direct backend development:

```sh
python -m venv .venv
. .venv/bin/activate
python -m pip install -e '.[dev]'
cp ../.env.example .env
alembic upgrade head
uvicorn app.main:app --reload
```

Run these commands from `backend/`. On Windows PowerShell, activate with `.\.venv\Scripts\Activate.ps1` and copy with `Copy-Item ..\.env.example .env`.

## Data intake and discovery

Faculty may be created through `POST /api/v1/faculty` or imported through the CSV preview and commit routes. Each newly created profile and each valid, unique imported row automatically creates a discovery job. The create response includes its job; the import response includes every generated job, including failed submissions. A Prefect submission failure leaves the faculty profile saved, marks its job failed, and reports that failure in the response. CSV list fields (`name_variants`, `previous_affiliations`, and `research_interests`) use semicolons between values. Previous affiliation values are stored as historical affiliations with `is_current=false`. The demo pilot CSV is in `backend/fixtures/pilot_faculty_seed.csv`.

An authorized admin or research officer can call `POST /api/v1/faculty/{faculty_id}/discover` to retry discovery after a prior job has finished or failed. The API persists each job before submitting it to Prefect. A failed manual submission returns `503` and retains a failed job rather than leaving a false pending record. The worker runs the configured sources and writes connector/job outcomes. Provider responses are not considered verified merely because adapter code exists.

The demo researcher is Fei-Fei Li in a separate demo tenant and must remain labelled `DEMO — external researcher; not a member of the customer's university`. The seed includes identity data only and does not preload publications.

## Development checks

From `backend/`:

```sh
python -m compileall -q app tests
python -m pytest -q
python -m ruff check app tests
```

These commands are run by the backend CI workflow. See [the current build status](docs/BUILD_STATUS.md) for the latest local test and container-verification results.

From `frontend/`, run the UI quality checks:

```sh
npm ci
npm run lint
npm run typecheck
npm test
npm run build
```

## Data sources and limits

FRIS targets official/public interfaces only: [OpenAlex](https://docs.openalex.org/), [Crossref REST API](https://www.crossref.org/documentation/retrieve-metadata/rest-api/), [ORCID API](https://info.orcid.org/documentation/api-tutorials/), and [Semantic Scholar API](https://api.semanticscholar.org/api-docs/). Follow provider authentication, rate limits, retention terms, and attribution rules. Do not scrape Google Scholar or bypass publisher access controls. A live local discovery run was verified; see [the build status](docs/BUILD_STATUS.md) for exact outcomes. Provider availability and coverage are not guaranteed.

## Security and privacy

Never commit `.env`, provider credentials, database dumps, or private faculty data. Passwords are hashed. Institutional email is not sent to providers by default and is omitted from ordinary faculty responses. Confidence values are evidence scores, not probabilities. See [SECURITY.md](SECURITY.md) for vulnerability reporting.

## License

Original FRIS code is under the MIT License in [LICENSE](LICENSE). Provider metadata, research works, and third-party dependencies remain subject to their own terms.
