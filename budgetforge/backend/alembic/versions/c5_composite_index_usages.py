"""add composite index usages project_id created_at

Revision ID: c5_composite_index_usages
Revises: 9f74d9d864f0
Create Date: 2026-04-27

"""

from typing import Sequence, Union
from alembic import op

revision: str = "c5_composite_index_usages"
down_revision: Union[str, Sequence[str], None] = "9f74d9d864f0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        "ix_usages_project_created",
        "usages",
        ["project_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_usages_project_created", table_name="usages")
