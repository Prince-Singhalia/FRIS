"""FRIS FastAPI application entry point."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.settings import get_settings
from app.core.errors import FRISError, fris_error_handler
from app.core.logging import setup_logging, get_logger
from app.db.session import dispose_engine
from app.api.v1.router import api_router

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    setup_logging(debug=settings.debug)
    logger.info("fris_starting", version=settings.app_version)
    yield
    await dispose_engine()
    logger.info("fris_shutdown")


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="FRIS — Faculty Research Intelligence System",
        version=settings.app_version,
        description="Automated research publication tracking for universities",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Error handlers
    app.add_exception_handler(FRISError, fris_error_handler)

    # Health routes (unauthenticated)
    @app.get("/health/live", tags=["health"])
    async def health_live():
        return {"status": "ok"}

    @app.get("/health/ready", tags=["health"])
    async def health_ready():
        from app.db.session import get_engine
        try:
            engine = get_engine()
            async with engine.connect() as conn:
                await conn.execute(__import__("sqlalchemy").text("SELECT 1"))
            return {"status": "ready", "database": "connected"}
        except Exception as e:
            return {"status": "not_ready", "database": str(e)}

    # API v1
    app.include_router(api_router, prefix="/api/v1")

    return app


app = create_app()
