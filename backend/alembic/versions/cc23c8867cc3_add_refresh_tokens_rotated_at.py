"""add refresh_tokens.rotated_at

Marks tokens consumed by a rotation (as opposed to logout / revoke-all) so
RefreshSession can detect reuse of a rotated token and revoke the user's
sessions. Nullable, no backfill: tokens rotated before this migration simply
don't trigger reuse detection.

Revision ID: cc23c8867cc3
Revises: d63101354a64
Create Date: 2026-11-10 05:05:58.091900

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'cc23c8867cc3'
down_revision: Union[str, None] = 'd63101354a64'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'refresh_tokens',
        sa.Column('rotated_at', sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('refresh_tokens', 'rotated_at')
