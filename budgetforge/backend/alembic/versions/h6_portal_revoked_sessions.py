"""add portal_revoked_sessions table for session revocation (H6)

Revision ID: h6_portal_revoked_sessions
Revises: e2_signup_attempts
Create Date: 2026-04-24
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "h6_portal_revoked_sessions"
down_revision = "e2_signup_attempts"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = inspect(bind)
    if "portal_revoked_sessions" not in inspector.get_table_names():
        op.create_table(
            "portal_revoked_sessions",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("email", sa.String(), nullable=False),
            sa.Column("iat", sa.Integer(), nullable=False),
            sa.Column("revoked_at", sa.DateTime(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            "ix_portal_revoked_sessions_id", "portal_revoked_sessions", ["id"]
        )
        op.create_index(
            "ix_portal_revoked_sessions_email", "portal_revoked_sessions", ["email"]
        )


def downgrade():
    op.drop_index(
        "ix_portal_revoked_sessions_email", table_name="portal_revoked_sessions"
    )
    op.drop_index("ix_portal_revoked_sessions_id", table_name="portal_revoked_sessions")
    op.drop_table("portal_revoked_sessions")
