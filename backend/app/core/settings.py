"""Application settings loaded from environment variables."""

from __future__ import annotations

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Central configuration — loaded from .env / environment."""

    # --- App ---
    app_name: str = "FRIS"
    app_version: str = "0.1.0"
    debug: bool = False
    app_env: str = "development"

    # --- Database ---
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "fris"
    postgres_user: str = "fris"
    postgres_password: str = "changeme"

    @property
    def database_url(self) -> str:
        from sqlalchemy.engine import URL

        return URL.create(
            "postgresql+asyncpg",
            username=self.postgres_user,
            password=self.postgres_password,
            host=self.postgres_host,
            port=self.postgres_port,
            database=self.postgres_db,
        ).render_as_string(hide_password=False)

    @property
    def database_url_sync(self) -> str:
        from sqlalchemy.engine import URL

        return URL.create(
            "postgresql+psycopg2",
            username=self.postgres_user,
            password=self.postgres_password,
            host=self.postgres_host,
            port=self.postgres_port,
            database=self.postgres_db,
        ).render_as_string(hide_password=False)

    # --- Auth / Security ---
    secret_key: str = "CHANGE-ME-IN-PRODUCTION"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7

    # --- CORS ---
    backend_cors_origins: str = "http://localhost:5173,http://localhost:3000"

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.backend_cors_origins.split(",") if o.strip()]

    # --- Prefect ---
    prefect_api_url: str = "http://localhost:4200/api"
    prefect_deployment_name: str = "fris-discovery/manual"

    # --- Explicit local/demo bootstrap ---
    fris_seed_demo: bool = False

    # --- Provider keys (all optional) ---
    openalex_email: str = ""
    crossref_mailto: str = ""
    orcid_client_id: str = ""
    orcid_client_secret: str = ""
    semantic_scholar_api_key: str = ""
    ieee_api_key: str = ""

    # --- Admin seed ---
    admin_default_password: str = "CHANGE-ME"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
