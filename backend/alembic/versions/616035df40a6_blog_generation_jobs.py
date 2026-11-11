"""blog generation jobs

Revision ID: 616035df40a6
Revises: 66ef8222c7a5
Create Date: 2026-08-08 01:23:09.576726

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '616035df40a6'
down_revision: Union[str, None] = '66ef8222c7a5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('blog_generation_jobs',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('topic', sa.String(length=200), nullable=False),
    sa.Column('keywords', postgresql.ARRAY(sa.String(length=40)), server_default=sa.text("'{}'"), nullable=False),
    sa.Column('notes', sa.String(length=500), nullable=True),
    sa.Column('provider', sa.String(length=16), nullable=False),
    sa.Column('status', sa.Enum('pending', 'succeeded', 'failed', name='generationjobstatus', native_enum=False, length=16), nullable=False),
    sa.Column('error', sa.Text(), nullable=True),
    sa.Column('post_id', sa.Uuid(), nullable=True),
    sa.Column('requested_by_id', sa.Uuid(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['post_id'], ['blog_posts.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['requested_by_id'], ['users.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_blog_generation_jobs_status'), 'blog_generation_jobs', ['status'], unique=False)
    op.create_index('ix_blog_generation_jobs_status_created_at', 'blog_generation_jobs', ['status', 'created_at'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_blog_generation_jobs_status_created_at', table_name='blog_generation_jobs')
    op.drop_index(op.f('ix_blog_generation_jobs_status'), table_name='blog_generation_jobs')
    op.drop_table('blog_generation_jobs')
