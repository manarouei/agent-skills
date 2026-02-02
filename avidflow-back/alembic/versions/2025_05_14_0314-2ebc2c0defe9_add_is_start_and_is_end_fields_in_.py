"""add is_start and is_end fields in DynamicNode

Revision ID: 2ebc2c0defe9
Revises: 91b344c708ab
Create Date: 2025-05-14 03:14:35.510114+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2ebc2c0defe9'
down_revision: Union[str, None] = '91b344c708ab'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("dynamic_nodes", sa.Column("is_start", sa.Boolean(), default=False))
    op.add_column("dynamic_nodes", sa.Column("is_end", sa.Boolean(), default=False))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("dynamic_nodes", "is_start")
    op.drop_column("dynamic_nodes", "is_end")
