"""multi-tenant organizations

Revision ID: c4d5e6f7a8b9
Revises: 8f5ec017bea2
Create Date: 2026-11-17

Creates organizations / memberships / invitations and adds
jobs.organization_id with a backfill: one default organization per
existing recruiter, owner membership, and their jobs assigned.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c4d5e6f7a8b9'
down_revision: Union[str, Sequence[str], None] = '8f5ec017bea2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()

    op.create_table(
        'organizations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_organizations_id', 'organizations', ['id'])

    op.create_table(
        'organization_memberships',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('org_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('role', sa.String(length=20), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['org_id'], ['organizations.id']),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('org_id', 'user_id', name='uq_membership_org_user'),
    )
    op.create_index('ix_organization_memberships_id', 'organization_memberships', ['id'])
    op.create_index('ix_organization_memberships_org_id', 'organization_memberships', ['org_id'])
    op.create_index('ix_organization_memberships_user_id', 'organization_memberships', ['user_id'])

    op.create_table(
        'organization_invitations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('org_id', sa.Integer(), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('role', sa.String(length=20), nullable=False),
        sa.Column('token', sa.String(length=64), nullable=False),
        sa.Column('invited_by', sa.Integer(), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('accepted_at', sa.DateTime(), nullable=True),
        sa.Column('revoked_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['org_id'], ['organizations.id']),
        sa.ForeignKeyConstraint(['invited_by'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('token', name='uq_invitation_token'),
    )
    op.create_index('ix_organization_invitations_id', 'organization_invitations', ['id'])
    op.create_index('ix_organization_invitations_org_id', 'organization_invitations', ['org_id'])
    op.create_index('ix_organization_invitations_email', 'organization_invitations', ['email'])
    op.create_index('ix_organization_invitations_token', 'organization_invitations', ['token'])

    with op.batch_alter_table('jobs', schema=None) as batch_op:
        batch_op.add_column(sa.Column('organization_id', sa.Integer(), nullable=True))
        batch_op.create_index('ix_jobs_organization_id', ['organization_id'], unique=False)
        batch_op.create_foreign_key('fk_jobs_organization_id', 'organizations', ['organization_id'], ['id'])

    # Backfill: one default organization per recruiter, owner membership,
    # and assign that recruiter's jobs to the new org.
    recruiters = bind.execute(
        sa.text("SELECT id, name, email FROM users WHERE role IN ('recruiter','admin')")
    ).fetchall()
    for uid, name, email in recruiters:
        org_name = f"{name or email}'s Organization"
        org_id = bind.execute(
            sa.text("INSERT INTO organizations (name, created_at) VALUES (:n, CURRENT_TIMESTAMP) RETURNING id"),
            {"n": org_name},
        ).scalar()
        if org_id is None:  # SQLite has no RETURNING on older versions
            org_id = bind.execute(
                sa.text("SELECT id FROM organizations WHERE name = :n ORDER BY id DESC LIMIT 1"),
                {"n": org_name},
            ).scalar()
        bind.execute(
            sa.text(
                "INSERT INTO organization_memberships (org_id, user_id, role, created_at) "
                "VALUES (:o, :u, 'owner', CURRENT_TIMESTAMP)"
            ),
            {"o": org_id, "u": uid},
        )
        bind.execute(
            sa.text("UPDATE jobs SET organization_id = :o WHERE recruiter_id = :u"),
            {"o": org_id, "u": uid},
        )


def downgrade() -> None:
    with op.batch_alter_table('jobs', schema=None) as batch_op:
        batch_op.drop_constraint('fk_jobs_organization_id', type_='foreignkey')
        batch_op.drop_index('ix_jobs_organization_id')
        batch_op.drop_column('organization_id')
    op.drop_table('organization_invitations')
    op.drop_table('organization_memberships')
    op.drop_table('organizations')
