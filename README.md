# Faculty Research Intelligence System (FRIS)

FRIS is a free-first, modular-monolith scaffold for discovering, matching, normalizing, and reviewing faculty research publications from permitted scholarly APIs. It keeps university-provided faculty identity data separate from independently discovered publication evidence and source provenance.

## Current status

This repository is an early backend implementation, not a production-ready pilot. The FastAPI service, SQLAlchemy models, Pydantic schemas, authentication helpers, provider connector modules, Prefect discovery flow, normalization/matching/deduplication services, demo seed module, and unit tests are present. The React frontend, Alembic revision, production deployment, and end-to-end database/API tests are not yet implemented.

| Area | Status | Notes |
| --- | --- | --- |
| Backend API | Partially implemented | FastAPI routes and tenant-scoped query patterns exist. |
| Research data pipeline | Partially implemented | Provider adapters and a Prefect flow exist; persistence and live orchestration still need hardening and integration tests. |
| Provider integrations | Partially implemented | OpenAlex, Crossref, ORCID, and Semantic Scholar adapters exist; live credentials/rate-limit behavior is environment-dependent and not claimed as verified here. |
| Frontend | Not yet implemented | `frontend/` is empty. |
| PostgreSQL schema migration | Not yet implemented | SQLAlchemy models exist, but `backend/migrations/versions/` has no revision. |
| CI/CD | Initial checks only | A GitHub Actions quality workflow is included; deployment, smoke tests, and rollback are planned. |

## Problem and objectives

Universities can provide authoritative faculty identity information without providing faculty publication lists. FRIS is intended to discover public publication metadata independently, resolve likely researcher identities, preserve provider evidence, deduplicate works, and make uncertain matches reviewable. Confidence values are evidence scores, not probabilities.

The MVP objectives are to provide:

- tenant-isolated faculty and identity management;
- DOI-first publication deduplication with review for ambiguous no-DOI matches;
- source-specific raw evidence, normalized values, retrieval timestamps, and URLs;
- bounded, idempotent discovery runs with clear provider status;
- a reviewable dashboard/API surface without bypassing publisher access controls.

## Architecture

Research data pipeline:

```text
Faculty Profile -> Publication Discovery -> Extraction -> Validation
  -> Normalization -> Author Identity Matching -> Deduplication
  -> Canonical Database -> Dashboard/API
```

Software CI/CD pipeline:

```text
Code Push -> Quality Checks -> Tests -> Security Scans
  -> Container Build -> Staging Deployment -> Smoke Tests
  -> Production Deployment
```

Only the quality-check portion of the software pipeline is currently automated. These two pipelines are intentionally separate.

## Technology stack

- Python 3.11+; FastAPI; Pydantic; SQLAlchemy async; PostgreSQL
- HTTPX provider clients; Prefect OSS workflow scaffolding
- Docker Compose for local services
- pytest, Ruff, mypy, Bandit, pip-audit, and Trivy as the intended quality/security tools
- React + TypeScript is planned; no frontend code is currently present

No Kubernetes, Kafka, Redis, or paid services are required by this repository.

## Repository layout

```text
backend/app/api/          FastAPI route modules
backend/app/connectors/   Provider adapter interfaces and adapters
backend/app/core/         Settings, auth, logging, and errors
backend/app/db/           SQLAlchemy base, session, and models
backend/app/domain/       Pydantic request/response schemas
backend/app/services/     Matching, normalization, and deduplication
backend/app/workflows/    Prefect discovery flow and tasks
backend/app/seed/         Explicit demo seed helpers
backend/tests/             Unit-test modules and reserved integration/contract areas
backend/migrations/       Alembic environment and template; revisions are pending
.github/workflows/        Backend quality checks
docs/                     Reserved for project documentation
infra/                    Reserved for deployment scripts
```

## Prerequisites

- Python 3.11 or newer
- PostgreSQL 16 for database-backed development
- Docker Desktop and Compose, if using containers
- Node.js is not currently needed because the frontend is not implemented

## Local setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".\backend[dev]"
Copy-Item .env.example .env
```

Replace placeholder values in `.env` before starting any service. Never commit `.env` or provider credentials. `SECRET_KEY`, database credentials, and `ADMIN_DEFAULT_PASSWORD` must be unique, strong values outside a disposable local environment.

## Configuration

`.env.example` contains the variables currently read by the application:

- `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`: database connection settings.
- `DATABASE_URL`, `DATABASE_URL_SYNC`: optional explicit async/sync URLs; the settings module can build them from the PostgreSQL fields.
- `SECRET_KEY`: JWT signing key; required for a non-development deployment.
- `BACKEND_HOST`, `BACKEND_PORT`, `BACKEND_CORS_ORIGINS`: API runtime settings.
- `PREFECT_API_URL`, `PREFECT_SERVER_API_HOST`, `PREFECT_SERVER_API_PORT`: Prefect settings.
- `OPENALEX_EMAIL`, `CROSSREF_MAILTO`: optional polite-pool contact values; do not use institutional email by default.
- `ORCID_CLIENT_ID`, `ORCID_CLIENT_SECRET`: optional ORCID public API credentials; ORCID access is not assumed without credentials.
- `SEMANTIC_SCHOLAR_API_KEY`: optional higher-rate-limit credential.
- `IEEE_API_KEY`: reserved for a future, institution-authorized connector and not used by the MVP flow.
- `VITE_API_BASE_URL`: reserved for the planned frontend.
- `ADMIN_DEFAULT_PASSWORD`, `ACCESS_TOKEN_EXPIRE_MINUTES`, `REFRESH_TOKEN_EXPIRE_DAYS`: authentication settings; demo seeding must remain explicit and non-production.

## Docker and database

`docker-compose.yml` describes PostgreSQL, the backend, and Prefect services. The repository currently has no migration revision and no frontend Dockerfile, so a clean end-to-end `docker compose up` is not yet a supported deployment path. Do not treat the Compose defaults as production secrets. Before enabling the stack, add a reviewed Alembic initial revision and remove any development-only defaults.

When migrations exist, the intended commands are:

```powershell
Set-Location backend
alembic upgrade head
uvicorn app.main:app --reload
```

## Testing and API documentation

From the repository root:

```powershell
python -m compileall -q backend/app backend/tests
Set-Location backend
python -m pytest -q
python -m ruff check app tests
python -m mypy app
```

The FastAPI OpenAPI document is exposed by the application at `/openapi.json`, with Swagger UI at `/docs`, when the backend is running. Provider live calls are not part of the default unit suite and must be explicitly configured and tested against the provider's permitted API.

## Supported data sources

The connector modules target official/public interfaces only:

- [OpenAlex API](https://docs.openalex.org/): adapter present; live access was not claimed in this audit.
- [Crossref REST API](https://api.crossref.org/): adapter present; live access was not claimed in this audit.
- [ORCID API documentation](https://info.orcid.org/documentation/api-tutorials/): adapter present but credentials are required and unconfigured by default.
- [Semantic Scholar Academic Graph API](https://api.semanticscholar.org/api-docs): adapter present; API-key/rate-limit behavior remains environment-dependent.

Provider endpoint and authentication assumptions were checked against the linked official documentation on 24 November 2026. This is not a claim that every live provider call succeeded in this environment.

## Security, privacy, and data handling

FRIS must not contain secrets, private keys, database dumps, or confidential faculty data. Raw provider evidence and normalized/canonical values must remain separate. Store only identity attributes needed for matching and governance, use Argon2 password hashing, enforce tenant scoping in every tenant-owned query, and do not send institutional email to providers by default. Review provider terms, API limits, licenses, and retention requirements before production use.

The pilot seed is demo/test data and must not be presented as customer-university faculty. The demo researcher is external and must be labelled `DEMO — external researcher` in any UI or seed workflow.

Report security issues privately according to [SECURITY.md](SECURITY.md); do not publish credentials in an issue.

## Known limitations and roadmap

Current limitations include no frontend, no Alembic revision, no production deployment, incomplete database/API integration coverage, incomplete Prefect deployment registration, and no verified live-provider test run. Ruff currently reports pre-existing lint findings that are tracked for cleanup; the CI workflow will make them visible.

Next development steps are: add and test the initial migration; harden Compose startup and explicit demo seeding; add connector contract/live opt-in tests; complete idempotent database persistence and Prefect deployment wiring; add cross-tenant denial tests; implement the React dashboard; then add container, smoke-test, and staged deployment workflows.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Keep changes small, preserve provenance, add tests for production modules, and do not describe planned integrations as operational.

## License

Original FRIS project code is released under the MIT License in [LICENSE](LICENSE). This does not license third-party APIs, publication metadata, research papers, datasets, or dependencies; their terms remain applicable.
