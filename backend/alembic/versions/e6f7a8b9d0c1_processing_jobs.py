"""processing jobs queue

Revision ID: e6f7a8b9d0c1
Revises: d5e6f7a8b9c0
Create Date: 2026-11-17

Creates processing_jobs (durable resume-processing queue) and adds
applications.processing_status.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'e6f7a8b9d0c1'
down_revision: Union[str, Sequence[str], None] = 'd5e6f7a8b9c0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'processing_jobs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('organization_id', sa.Integer(), nullable=True),
        sa.Column('job_id', sa.Integer(), nullable=False),
        sa.Column('application_id', sa.Integer(), nullable=False),
        sa.Column('candidate_id', sa.Integer(), nullable=True),
        sa.Column('storage_key', sa.String(length=300), nullable=False),
        sa.Column('batch_id', sa.String(length=64), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=True),
        sa.Column('attempt_count', sa.Integer(), nullable=True),
        sa.Column('max_attempts', sa.Integer(), nullable=True),
        sa.Column('last_error_code', sa.String(length=60), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('retry_after', sa.DateTime(), nullable=True),
        sa.Column('locked_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['application_id'], ['applications.id']),
        sa.ForeignKeyConstraint(['candidate_id'], ['users.id']),
        sa.ForeignKeyConstraint(['job_id'], ['jobs.id']),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_processing_jobs_id', 'processing_jobs', ['id'])
    op.create_index('ix_processing_jobs_organization_id', 'processing_jobs', ['organization_id'])
    op.create_index('ix_processing_jobs_job_id', 'processing_jobs', ['job_id'])
    op.create_index('ix_processing_jobs_application_id', 'processing_jobs', ['application_id'])
    op.create_index('ix_processing_jobs_batch_id', 'processing_jobs', ['batch_id'])
    op.create_index('ix_processing_jobs_status', 'processing_jobs', ['status'])

    with op.batch_alter_table('applications', schema=None) as batch_op:
        batch_op.add_column(sa.Column('processing_status', sa.String(length=20), nullable=True))
        batch_op.create_index('ix_applications_processing_status', ['processing_status'])


def downgrade() -> None:
    with op.batch_alter_table('applications', schema=None) as batch_op:
        batch_op.drop_index('ix_applications_processing_status')
        batch_op.drop_column('processing_status')
    op.drop_table('processing_jobs')
