"""merge blog and community branches

Revision ID: d63101354a64
Revises: 616035df40a6, 98548f4a7cfc
Create Date: 2026-08-08 01:26:55.209725

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd63101354a64'
down_revision: Union[str, None] = ('616035df40a6', '98548f4a7cfc')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
