# FRIS Project Status

**Reviewed:** 2026-11-26
**Branch:** `main`
**Overall status:** Working MVP with CI quality gates; not complete as specified and not production-ready.

## Summary

FRIS has a tenant-aware backend, a React frontend, a local Prefect discovery worker, and useful automated quality checks. The software pipeline currently provides CI, not end-to-end CI/CD: it does not publish release images or deploy and verify a release. No staging target or deployment credentials are configured.

The controlling acceptance criteria are in the [master implementation brief](specifications/master-implementation-brief.md), especially its software CI/CD, testing, and release-readiness sections. The [build status](BUILD_STATUS.md) contains the detailed implementation history and test evidence.

## Completed

### Application

- FastAPI backend with tenant-scoped authentication, faculty intake, CSV preview/import, and PostgreSQL persistence.
- Alembic database bootstrap, guarded opt-in demo seeding, and readiness checks.
- Prefect manual discovery deployment and worker. Faculty creation and successful CSV imports enqueue durable discovery jobs; submission failures remain visible.
- React/TypeScript frontend connected to the API, covering dashboard, faculty, import, discovery jobs, review, and provider readiness.
- Runtime Dockerfiles and Docker Compose configuration for the application, PostgreSQL, Prefect, and frontend.

### CI and quality checks

The [GitHub Actions workflow](../.github/workflows/backend-quality.yml) runs for pushes and pull requests targeting `main`. It includes backend unit and PostgreSQL integration tests, Ruff, mypy, Bandit and pip-audit; frontend lint, typecheck, tests and build; Trivy image scans; Gitleaks; and a frontend-container smoke test.

### Recorded validation

- Backend: **63 passed, 4 skipped**; Ruff, compileall and mypy passed. The skipped tests require a configured PostgreSQL test database.
- Frontend: **7 tests passed**; lint, typecheck and production build passed. The recorded `npm audit` reported zero vulnerabilities.
- `pip-audit --skip-editable`: no known vulnerabilities in the current recheck.
- `docker compose config --quiet`: passed with disposable interpolation values.
- The [build status](BUILD_STATUS.md) records earlier successful local image and Compose checks, including a live Prefect worker discovery run. Those runtime checks were not repeated during this review because Docker was unavailable.

## Remaining work

### Software CI/CD — highest priority

- Publish versioned, immutable backend, frontend, and Prefect worker/flow images to a chosen registry. Current CI builds local `:ci` images only.
- Configure a staging target and deployment credentials before enabling deployment. The target is currently unconfigured; do not report a deployment until one has run successfully.
- Add deployment steps for safe migrations, API/frontend rollout, and Prefect worker plus flow deployment.
- Verify API readiness, database connectivity, Prefect server/worker heartbeat, deployed flow, and an end-to-end discovery smoke test after deployment.
- Add protected promotion/approval and a tested rollback path that restores known immutable image versions.
- Confirm repository branch protection requires the appropriate CI checks. This could not be established from the local repository.
- Improve reproducibility: add a backend dependency lock and pin base images and workflow actions to controlled versions or immutable digests.

### Application and test acceptance

- Add connector contract tests for pagination, malformed responses, authentication failures, rate limits, timeouts, and provider server errors. `backend/tests/contract/` currently has no substantive tests.
- Run the skipped PostgreSQL intake/integration cases against a configured database and add CI coverage for Prefect worker/flow execution; the current integration job does not verify a deployed worker.
- Complete broader provider verification, matching and deduplication regression coverage, and a gold-standard evaluation with measured precision/recall. Do not invent evaluation results.
- Keep scheduled discovery deferred until a tenant-aware scheduled dispatcher exists; the current deployment is intentionally manual.
- Add or complete operational documentation for provider integrations, threat model, architecture/data model, evaluation, and backup/restore.

### Documentation cleanup

- Correct [operations-runbook.md](operations-runbook.md), which still says the frontend and its Compose service do not exist.
- Reconcile older status/handoff and team-prompt documents with the current implementation and shared-`main` contribution workflow, or clearly label them as historical.
- Keep this status and [BUILD_STATUS.md](BUILD_STATUS.md) aligned as verification changes.

## Repository and verification caveats

At review time, local `main` contained seven commits not present on `origin/main`. Consequently, GitHub Actions had not verified those local commits. The current review also could not rerun Docker image builds, live Compose services, or PostgreSQL integration tests because Docker and a configured `FRIS_TEST_DATABASE_URL` were unavailable.

Use the [README](../README.md) for the current implementation overview and local setup, and the [operations runbook](operations-runbook.md) for operational procedures, after correcting its stale frontend statements.
