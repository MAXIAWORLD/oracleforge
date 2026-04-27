"""merge_heads_for_bloc_c

Revision ID: 9f74d9d864f0
Revises: 975c3fce2c49, e3_signup_attempts_email
Create Date: 2026-04-27 12:31:11.264888

"""

from typing import Sequence, Union



# revision identifiers, used by Alembic.
revision: str = "9f74d9d864f0"
down_revision: Union[str, Sequence[str], None] = (
    "975c3fce2c49",
    "e3_signup_attempts_email",
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
