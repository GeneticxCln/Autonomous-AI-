"""
Initial database schema

This revision bootstraps all tables defined in agent_system.auth_models and
agent_system.database_models by invoking the project's SQLAlchemy metadata.

Note: This migration relies on the application metadata instead of explicit
op.create_table statements to keep it aligned with the models. Future revisions
can migrate with explicit operations as needed.
"""

from __future__ import annotations

from alembic import op

# revision identifiers, used by Alembic.
revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Import here to avoid Alembic config import ordering issues
    from agent_system.database_models import Base as AppBase

    bind = op.get_bind()
    AppBase.metadata.create_all(bind=bind)


def downgrade() -> None:
    # No automatic downgrade; keep data-safe. Future revisions can handle drops.
    pass
