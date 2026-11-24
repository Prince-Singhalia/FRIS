# Contributing to FRIS

This project currently uses the shared `main` workflow. Keep changes focused and commit them directly to `main` as agreed by the team.

1. Copy `.env.example` to `.env` for local development; never commit credentials or private data.
2. Install backend development dependencies from `backend/` with `python -m pip install -e '.[dev]'`.
3. Run `python -m compileall -q app tests`, `python -m pytest -q`, and `python -m ruff check app tests` from `backend/` when validating a change.
4. Add or update tests for production modules, especially tenant isolation, idempotency, provenance, and no-DOI review behavior.
5. Document provider API assumptions with official documentation links. Do not scrape Google Scholar or bypass publisher access controls.
6. Keep README and `docs/BUILD_STATUS.md` factual. Record exact commands and outcomes; use `not_run` or `not_configured` when appropriate.

Never report a provider, test, container, or deployment as successful unless it was actually exercised.
