"""application resume storage fields

Revision ID: d5e6f7a8b9c0
Revises: c4d5e6f7a8b9
Create Date: 2026-11-17

Adds applications.resume_storage_key (opaque object key in private
storage) and applications.content_hash (sha256, dedupe support).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'd5e6f7a8b9c0'
down_revision: Union[str, Sequence[str], None] = 'c4d5e6f7a8b9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('applications', schema=None) as batch_op:
        batch_op.add_column(sa.Column('resume_storage_key', sa.String(length=300), nullable=True))
        batch_op.add_column(sa.Column('content_hash', sa.String(length=64), nullable=True))
        batch_op.create_index('ix_applications_resume_storage_key', ['resume_storage_key'])
        batch_op.create_index('ix_applications_content_hash', ['content_hash'])


def downgrade() -> None:
    with op.batch_alter_table('applications', schema=None) as batch_op:
        batch_op.drop_index('ix_applications_content_hash')
        batch_op.drop_index('ix_applications_resume_storage_key')
        batch_op.drop_column('content_hash')
        batch_op.drop_column('resume_storage_key')
