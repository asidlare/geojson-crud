"""geojson data storage

Revision ID: 87f1757ced27
Revises: 
Create Date: 2025-01-05 19:38:01.023460

"""
from typing import Sequence, Union

from alembic import op
import geoalchemy2
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '87f1757ced27'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('projects',
    sa.Column('project_id', sa.BIGINT(), nullable=False),
    sa.Column('name', sa.VARCHAR(length=32), nullable=False),
    sa.Column('description', sa.VARCHAR(length=255), nullable=True),
    sa.Column('start_date', sa.DATE(), nullable=False),
    sa.Column('end_date', sa.DATE(), nullable=False),
    sa.Column('geo_project_type', sa.Enum('Feature', 'FeatureCollection', name='geo_project_type', create_constraint=True), nullable=False),
    sa.Column('bbox', sa.ARRAY(sa.Float()), nullable=True),
    sa.Column('created_at', postgresql.TIMESTAMP(), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', postgresql.TIMESTAMP(), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint('end_date >= start_date'),
    sa.PrimaryKeyConstraint('project_id'),
    sa.UniqueConstraint('name', 'start_date', 'end_date')
    )
    op.create_table('features',
    sa.Column('feature_id', sa.BIGINT(), nullable=False),
    sa.Column('geometry', geoalchemy2.types.Geometry(spatial_index=False, from_text='ST_GeomFromEWKT', name='geometry', nullable=False), nullable=False),
    sa.Column('properties', sa.JSON(), nullable=True),
    sa.Column('project_id', sa.BIGINT(), nullable=False),
    sa.ForeignKeyConstraint(['project_id'], ['projects.project_id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('feature_id')
    )
    op.create_index(op.f('ix_features_project_id'), 'features', ['project_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_features_project_id'), table_name='features')
    op.drop_table('features')
    op.drop_table('projects')
    op.execute('DROP TYPE geo_project_type')
