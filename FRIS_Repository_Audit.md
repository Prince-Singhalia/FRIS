# FRIS Repository Audit — 24 November 2026

## Scope and verdict

The repository is a partially implemented backend scaffold. It is suitable for an initial source-controlled checkpoint after documentation and hygiene files are added, but it is not a production-ready FRIS pilot.

The current tree contains FastAPI routes, SQLAlchemy models, Pydantic schemas, Argon2/JWT helpers, OpenAlex/Crossref/ORCID/Semantic Scholar connector modules, matching/normalization/deduplication services, a Prefect discovery flow, demo seed code, Docker Compose configuration, and 58 passing unit tests. The React frontend, Alembic revision, production deployment, and end-to-end database/API coverage are missing.

## Implementation status

| Component | Status | Evidence / limitation |
| --- | --- | --- |
| Backend API | Partially implemented | Routes exist under `backend/app/api/v1`; database-backed startup still needs a migration. |
| Tenant/auth model | Partially implemented | Tenant fields and JWT type checks are present; broader authorization and cross-tenant integration tests are still needed. |
| Provider connectors | Partially implemented | Four adapter modules exist; live provider success was not claimed without configured credentials and network tests. |
| Research pipeline | Partially implemented | Prefect tasks and a flow exist, but deployment registration and full persistence/idempotency coverage remain. |
| Database | Partially implemented | SQLAlchemy metadata exists; `backend/migrations/versions/` is empty. |
| Frontend | Not yet implemented | `frontend/` has no source, package manifest, or Dockerfile. |
| CI/CD | Initial checks only | Backend compile, pytest, and Ruff workflow added; deployment/smoke/rollback are not implemented. |
| Documentation | Implemented for current checkpoint | README, contribution, security, license, and editor configuration added. |

## Security review

- No committed `.env` file, private key, database dump, or log file was found in the working tree.
- A source-pattern scan found configuration names and placeholder/default development values, but no exposed credential value. Actual secret values were not printed.
- `.env`, `.env.*` with an exception for `.env.example`, keys, certificates, database files, dumps, logs, caches, and local build outputs are ignored.
- The seed CSV has one row, an ORCID, and a public profile URL but no institutional email. It is treated as demo/test data and must not be presented as customer-university faculty.
- No credential rotation is indicated by this scan. Rotate any secret if one was ever placed in a local file that was shared or pushed elsewhere.
- Dependency license and vulnerability review remains incomplete because `pip-audit` was invoked against `pyproject.toml` (which it does not accept as a requirements file) and no separate lockfile or requirements export exists. No claim of full license compliance is made.

## Findings requiring development

1. Create and test an initial Alembic revision before relying on `alembic upgrade head`.
2. Make Compose startup fail fast on migration errors and keep demo seeding explicit, idempotent, and disabled for production.
3. Add connector contract tests, opt-in live tests, provider retry/limit coverage, and a registered Prefect deployment/worker path.
4. Add database/API integration tests for tenant isolation, authorization, persistence idempotency, and job state transitions.
5. Implement the React/TypeScript dashboard and its Dockerfile, or remove frontend assumptions from deployment documentation when the scope is backend-only.
6. Resolve the Ruff findings before making the quality workflow a required merge gate.

## Validation performed

| Check | Result | Limitation |
| --- | --- | --- |
| `python -m compileall -q backend/app backend/tests` | Passed | Syntax/bytecode check only. |
| `cd backend; python -m pytest -q` | Passed: 58 tests | Unit suite; no database/provider integration. |
| `cd backend; python -m ruff check app tests` | Failed: 169 findings | Existing lint findings, including import ordering, line length, and dependency-injection rule warnings. |
| `cd backend; python -m mypy app` | Unavailable | Windows Application Control blocked the installed mypy extension. |
| `docker compose config --quiet` | Passed | Compose syntax only; services were not started. |
| Bandit | Unavailable | Windows Application Control blocked the installed executable. |
| pip-audit | Not completed | The tool does not accept `pyproject.toml` as a requirements file; dependency export/lockfile is needed. |
| Gitleaks | Unavailable | Not installed. |
| Trivy | Unavailable | Not installed. |
| GitHub remote refs | Checked | Repository responded with no refs at audit time; authentication/push still requires GitHub access. |

## Provider documentation checked

Endpoint and authentication assumptions were checked against official documentation on 24 November 2026:

- https://docs.openalex.org/
- https://api.crossref.org/
- https://info.orcid.org/documentation/api-tutorials/
- https://api.semanticscholar.org/api-docs

This documents the sources consulted; it does not claim that live provider calls succeeded.
