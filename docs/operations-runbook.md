# Local operations runbook

## Configure and start

1. Copy `.env.example` to `.env`.
2. Set a unique `POSTGRES_PASSWORD` and a random `SECRET_KEY` with at least 32 characters. The API bootstrap rejects placeholders.
3. Keep `FRIS_SEED_DEMO=false` unless you intentionally want the isolated demo tenant. To seed locally, set it to `true` and set `ADMIN_DEFAULT_PASSWORD` to a unique value with at least 12 characters. Seeding is rejected in `APP_ENV=production`.
4. Start the stack with `docker compose up --build`.

The API waits for PostgreSQL health, applies `alembic upgrade head`, optionally seeds the demo data, then starts. The Prefect bootstrap registers `fris-discovery/manual` in the `fris-pool`; the process worker runs that deployment. Required setup failures stop the affected service.

## Local endpoints

- FastAPI: `http://localhost:8000`
- API docs: `http://localhost:8000/docs`
- API readiness: `http://localhost:8000/health/ready`
- Prefect UI: `http://localhost:4200`

The frontend has not been implemented and has no Compose service yet.

## Seed login

When enabled, the seed creates an admin in the `fris-demo` tenant. Use username `fris-demo/admin` and the configured seed password. A bare username is accepted only when it matches one active user across tenants.

## Import faculty

Use `POST /api/v1/faculty/import/preview` before `POST /api/v1/faculty/import/commit`. Accepted list values use semicolons. `previous_affiliations` are saved as historical affiliations; they do not replace the reported current institution. Imports into a real tenant are not marked as demo. Imports into the designated demo tenant inherit its demo status and label.

## Trigger discovery

An admin or research officer can trigger a faculty discovery run with `POST /api/v1/faculty/{faculty_id}/discover`. The API stores the job first, then asks the Prefect deployment to create a run. The resulting Prefect run identifier is available on the job response. If submission fails, inspect the failed job and the API logs; the route returns HTTP 503.

This deployment is manual because the current flow needs a specific `job_id`, `faculty_id`, and `tenant_id`. Do not add a recurring schedule until a tenant-aware scheduled dispatcher exists.

## Migrations

The API bootstrap runs `alembic upgrade head`. For direct development, run `alembic upgrade head` from `backend/`. The initial revision creates the schema for a clean database from the mapped metadata. Add new migration revisions for every later schema change. Back up persistent data before manual downgrade or destructive schema work.

## Troubleshooting

- **API exits before startup:** check PostgreSQL health and database credentials, then inspect the Alembic error. Migration failures are fatal.
- **Demo seed refuses to run:** verify `FRIS_SEED_DEMO=true`, `APP_ENV` is not `production`, and the configured seed password is unique and at least 12 characters.
- **Discovery returns 503:** check that Prefect is healthy and that deployment `fris-discovery/manual` exists in pool `fris-pool`; rebuild Compose services after changing the flow code.
- **Provider reports unavailable or not configured:** inspect the relevant environment variables and connector run status. Do not infer successful live access from a configured key alone.

## Not configured

No staging host or deployment credentials are configured. Compose currently provides local backend and Prefect services only. There is no frontend, release image pipeline, remote smoke test, or rollback deployment process yet.
