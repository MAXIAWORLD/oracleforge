"""add email column to signup_attempts for per-email rate limiting

Revision ID: e3_signup_attempts_email
Revises: daaa6555f2ce
Create Date: 2026-04-25
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "e3_signup_attempts_email"
down_revision = "daaa6555f2ce"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = inspect(bind)
    existing = {col["name"] for col in inspector.get_columns("signup_attempts")}
    if "email" not in existing:
        op.add_column("signup_attempts", sa.Column("email", sa.String(), nullable=True))
        op.create_index("ix_signup_attempts_email", "signup_attempts", ["email"])


def downgrade():
    bind = op.get_bind()
    inspector = inspect(bind)
    existing = {col["name"] for col in inspector.get_columns("signup_attempts")}
    if "email" in existing:
        op.drop_index("ix_signup_attempts_email", table_name="signup_attempts")
        op.drop_column("signup_attempts", "email")
