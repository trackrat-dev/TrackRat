"""add_schedule_data_fields

Revision ID: 4215e4085a4e
Revises: add_updated_times_and_raw_status_fields
Create Date: 2025-07-25 12:35:41.914154

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '4215e4085a4e'
down_revision = 'add_updated_times_and_raw_status_fields'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Apply migration."""
    # Add fields to distinguish schedule vs realtime data
    op.add_column('train_journeys', 
        sa.Column('data_source_type', sa.String(20), nullable=False, server_default='realtime')
    )
    op.add_column('train_journeys',
        sa.Column('schedule_collected_at', sa.DateTime(timezone=True), nullable=True)
    )
    
    # Add index for efficient filtering by data source type
    op.create_index('idx_data_source_type', 'train_journeys', ['data_source_type'])


def downgrade() -> None:
    """Revert migration."""
    op.drop_index('idx_data_source_type', 'train_journeys')
    op.drop_column('train_journeys', 'schedule_collected_at')
    op.drop_column('train_journeys', 'data_source_type')