"""B3: add owner_email to projects for multi-project support (C19/C20)

Revision ID: b3_owner_email
Revises: h6_portal_revoked_sessions
Create Date: 2026-04-25
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect, text

revision = "b3_owner_email"
down_revision = "h6_portal_revoked_sessions"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = inspect(bind)
    cols = [c["name"] for c in inspector.get_columns("projects")]
    if "owner_email" not in cols:
        op.add_column("projects", sa.Column("owner_email", sa.String(), nullable=True))
        op.create_index("ix_projects_owner_email", "projects", ["owner_email"])
        # Backfill: owner_email = name pour tous les projets existants
        bind.execute(
            text("UPDATE projects SET owner_email = name WHERE owner_email IS NULL")
        )


def downgrade():
    op.drop_index("ix_projects_owner_email", table_name="projects")
    op.drop_column("projects", "owner_email")
