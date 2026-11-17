"""worker heartbeats

Revision ID: a8b9c0d1e2f3
Revises: f7a8b9c0d1e2
Create Date: 2026-11-17
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a8b9c0d1e2f3'
down_revision: Union[str, Sequence[str], None] = 'f7a8b9c0d1e2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'worker_heartbeats',
        sa.Column('worker_id', sa.String(length=80), nullable=False),
        sa.Column('hostname', sa.String(length=120), nullable=True),
        sa.Column('pid', sa.Integer(), nullable=True),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('last_tick_at', sa.DateTime(), nullable=True),
        sa.Column('jobs_completed', sa.Integer(), nullable=True),
        sa.Column('jobs_failed', sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint('worker_id'),
    )


def downgrade() -> None:
    op.drop_table('worker_heartbeats')
