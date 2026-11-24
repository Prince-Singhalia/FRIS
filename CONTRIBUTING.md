# Contributing to FRIS

1. Create a focused branch from `main`.
2. Copy `.env.example` to `.env` for local development; never commit credentials or private data.
3. Install backend development dependencies with `python -m pip install -e ".\backend[dev]"`.
4. Run `python -m compileall -q backend/app backend/tests`, `python -m pytest -q`, and `python -m ruff check app tests` from `backend` as applicable.
5. Add or update tests for production modules, especially tenant isolation, idempotency, provenance, and no-DOI review behavior.
6. Document provider API assumptions with links to official documentation. Do not scrape Google Scholar or bypass publisher access controls.
7. Keep README status labels factual: use Planned, Partially implemented, or Not yet implemented where appropriate.

Pull requests should explain validation performed and call out checks that could not run because a tool, database, Docker daemon, or provider credential was unavailable.
