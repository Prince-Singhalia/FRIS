"""Run required database bootstrap steps, then start the API server."""

from __future__ import annotations

import asyncio
import os
import subprocess
import sys
from pathlib import Path

from app.core.settings import get_settings


def _run_migrations(backend_dir: Path) -> None:
    """Apply checked-in migrations and fail startup if the database is not ready."""
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=backend_dir,
        check=True,
    )


def _validate_runtime_settings() -> None:
    settings = get_settings()
    if len(settings.secret_key) < 32 or "CHANGE" in settings.secret_key.upper():
        raise RuntimeError("Set SECRET_KEY to a unique random value of at least 32 characters")
    if not settings.postgres_password or "CHANGE" in settings.postgres_password.upper():
        raise RuntimeError("Set POSTGRES_PASSWORD to a non-placeholder value")


async def _seed_demo_data() -> None:
    from app.db.session import get_session_factory
    from app.seed.demo import seed_demo_data

    async with get_session_factory()() as session:
        await seed_demo_data(session)


def main() -> None:
    settings = get_settings()
    backend_dir = Path(__file__).resolve().parents[1]
    _validate_runtime_settings()

    if settings.fris_seed_demo:
        if settings.app_env.lower() == "production":
            raise RuntimeError("FRIS_SEED_DEMO cannot be enabled when APP_ENV=production")
        if len(settings.admin_default_password) < 12 or settings.admin_default_password.startswith(
            "CHANGE"
        ):
            raise RuntimeError(
                "Set ADMIN_DEFAULT_PASSWORD to a unique password of at least 12 characters "
                "before enabling FRIS_SEED_DEMO"
            )

    _run_migrations(backend_dir)
    if settings.fris_seed_demo:
        asyncio.run(_seed_demo_data())

    host = os.getenv("BACKEND_HOST", "0.0.0.0")  # noqa: S104
    port = os.getenv("BACKEND_PORT", "8000")
    os.execv(  # noqa: S606
        sys.executable,
        [sys.executable, "-m", "uvicorn", "app.main:app", "--host", host, "--port", port],
    )


if __name__ == "__main__":
    main()
