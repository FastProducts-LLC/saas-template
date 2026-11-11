"""blog tags and search index

Revision ID: 66ef8222c7a5
Revises: 97fc251c17ff
Create Date: 2026-08-08 00:59:55.173135

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '66ef8222c7a5'
down_revision: Union[str, None] = '97fc251c17ff'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'blog_posts',
        sa.Column(
            'tags',
            postgresql.ARRAY(sa.String(length=40)),
            server_default=sa.text("'{}'"),
            nullable=False,
        ),
    )
    op.create_index(
        'ix_blog_posts_tags',
        'blog_posts',
        ['tags'],
        unique=False,
        postgresql_using='gin',
    )
    op.execute(
        "CREATE INDEX ix_blog_posts_search ON blog_posts "
        "USING gin (to_tsvector('english', title || ' ' || excerpt || ' ' || content))"
    )


def downgrade() -> None:
    op.execute("DROP INDEX ix_blog_posts_search")
    op.drop_index('ix_blog_posts_tags', table_name='blog_posts', postgresql_using='gin')
    op.drop_column('blog_posts', 'tags')
