"""Create the durable fixture identity registry.

Revision ID: 20260804_01
Revises:
Create Date: 2026-08-04
"""

from alembic import op
import sqlalchemy as sa


revision = '20260804_01'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'fixture_identities',
        sa.Column('public_id', sa.String(length=27), primary_key=True),
        sa.Column('canonical_competition_id', sa.String(length=255), nullable=True),
        sa.Column('canonical_home_team_id', sa.String(length=255), nullable=True),
        sa.Column('canonical_away_team_id', sa.String(length=255), nullable=True),
        sa.Column('season_key', sa.String(length=128), nullable=True),
        sa.Column('stage_key', sa.String(length=128), nullable=True),
        sa.Column('kickoff_utc', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        'ix_fixture_identity_match',
        'fixture_identities',
        [
            'canonical_competition_id',
            'canonical_home_team_id',
            'canonical_away_team_id',
            'season_key',
            'stage_key',
            'kickoff_utc',
        ],
    )
    op.create_table(
        'fixture_provider_aliases',
        sa.Column('provider', sa.String(length=64), primary_key=True),
        sa.Column('provider_event_id', sa.String(length=255), primary_key=True),
        sa.Column(
            'public_id',
            sa.String(length=27),
            sa.ForeignKey('fixture_identities.public_id', ondelete='CASCADE'),
            nullable=False,
        ),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        'ix_fixture_provider_alias_public_id',
        'fixture_provider_aliases',
        ['public_id'],
    )
    op.create_table(
        'fixture_public_aliases',
        sa.Column('alias_public_id', sa.String(length=27), primary_key=True),
        sa.Column(
            'canonical_public_id',
            sa.String(length=27),
            sa.ForeignKey('fixture_identities.public_id', ondelete='CASCADE'),
            nullable=False,
        ),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        'identity_resolution_issues',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('kind', sa.String(length=32), nullable=False),
        sa.Column('provider', sa.String(length=64), nullable=False),
        sa.Column('provider_id', sa.String(length=255), nullable=False),
        sa.Column('display_name', sa.String(length=255), nullable=True),
        sa.Column('occurrences', sa.Integer(), nullable=False),
        sa.Column('first_seen_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('last_seen_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('resolved', sa.Boolean(), nullable=False),
        sa.UniqueConstraint(
            'kind',
            'provider',
            'provider_id',
            name='uq_identity_resolution_issue',
        ),
    )
    op.create_table(
        'schema_metadata',
        sa.Column('key', sa.String(length=64), primary_key=True),
        sa.Column('value', sa.String(length=255), nullable=False),
    )
    metadata = sa.table(
        'schema_metadata',
        sa.column('key', sa.String()),
        sa.column('value', sa.String()),
    )
    op.bulk_insert(metadata, [{'key': 'schema_version', 'value': revision}])


def downgrade():
    op.drop_table('schema_metadata')
    op.drop_table('identity_resolution_issues')
    op.drop_table('fixture_public_aliases')
    op.drop_index('ix_fixture_provider_alias_public_id', table_name='fixture_provider_aliases')
    op.drop_table('fixture_provider_aliases')
    op.drop_index('ix_fixture_identity_match', table_name='fixture_identities')
    op.drop_table('fixture_identities')
