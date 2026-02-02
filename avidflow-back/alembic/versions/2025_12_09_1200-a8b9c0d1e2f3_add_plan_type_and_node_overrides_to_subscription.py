"""add plan_type and node_overrides to subscription

Revision ID: a8b9c0d1e2f3
Revises: 221a5955a35e
Create Date: 2025-12-09 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a8b9c0d1e2f3'
down_revision: Union[str, None] = '221a5955a35e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add plan_type column with default 'custom' for new subscriptions
    op.add_column(
        'subscriptions',
        sa.Column('plan_type', sa.String(50), nullable=False, server_default='custom')
    )
    
    # Add node_overrides JSON column for per-user node customization
    # Structure: {"nodes": ["node1", "node2", ...]} for custom plan
    # Or: {"add": ["node1"], "remove": ["node2"]} for overrides
    op.add_column(
        'subscriptions',
        sa.Column('node_overrides', sa.JSON(), nullable=True)
    )


def downgrade() -> None:
    op.drop_column('subscriptions', 'node_overrides')
    op.drop_column('subscriptions', 'plan_type')
