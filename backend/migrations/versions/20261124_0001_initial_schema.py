"""Create the initial FRIS schema.

Revision ID: 20261124_0001
Revises:
Create Date: 2026-11-24

This first revision is a baseline for a brand-new database. Keep future schema
changes in explicit Alembic revisions; do not edit this revision after release.
"""

from alembic import op

from app.db import models as _models  # noqa: F401 — register all mapped tables
from app.db.base import Base

revision = "20261124_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create every table and PostgreSQL enum from the initial model metadata."""
    Base.metadata.create_all(bind=op.get_bind(), checkfirst=False)


def downgrade() -> None:
    """Drop the initial schema in foreign-key-safe dependency order."""
    Base.metadata.drop_all(bind=op.get_bind(), checkfirst=False)
