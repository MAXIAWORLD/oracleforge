"""merge_dual_heads

Revision ID: 975c3fce2c49
Revises: b3_owner_email, e3_signup_attempts_email
Create Date: 2026-04-27 09:37:21.363756

"""

from typing import Sequence, Union


# revision identifiers, used by Alembic.
revision: str = "975c3fce2c49"
down_revision: Union[str, Sequence[str], None] = "b3_owner_email"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
