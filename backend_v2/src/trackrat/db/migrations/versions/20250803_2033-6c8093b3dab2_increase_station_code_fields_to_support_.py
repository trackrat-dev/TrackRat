"""Increase station code fields to support 3-character Amtrak codes

Revision ID: 6c8093b3dab2
Revises: 8b33228b4924
Create Date: 2025-08-03 20:33:07.037093

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '6c8093b3dab2'
down_revision = '8b33228b4924'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Apply migration."""
    # Increase station code fields from VARCHAR(2) to VARCHAR(3) to support Amtrak station codes
    
    # TrainJourney table
    op.alter_column('train_journeys', 'origin_station_code', 
                   existing_type=sa.VARCHAR(length=2),
                   type_=sa.VARCHAR(length=3),
                   existing_nullable=False)
    op.alter_column('train_journeys', 'terminal_station_code',
                   existing_type=sa.VARCHAR(length=2), 
                   type_=sa.VARCHAR(length=3),
                   existing_nullable=False)
    op.alter_column('train_journeys', 'discovery_station_code',
                   existing_type=sa.VARCHAR(length=2),
                   type_=sa.VARCHAR(length=3),
                   existing_nullable=True)
    
    # JourneyStop table
    op.alter_column('journey_stops', 'station_code',
                   existing_type=sa.VARCHAR(length=2),
                   type_=sa.VARCHAR(length=3),
                   existing_nullable=False)
    
    # DiscoveryRun table
    op.alter_column('discovery_runs', 'station_code',
                   existing_type=sa.VARCHAR(length=2),
                   type_=sa.VARCHAR(length=3),
                   existing_nullable=False)
    
    # LiveActivityToken table
    op.alter_column('live_activity_tokens', 'origin_code',
                   existing_type=sa.VARCHAR(length=2),
                   type_=sa.VARCHAR(length=3),
                   existing_nullable=False)
    op.alter_column('live_activity_tokens', 'destination_code',
                   existing_type=sa.VARCHAR(length=2),
                   type_=sa.VARCHAR(length=3),
                   existing_nullable=False)
    
    # SegmentTransitTime table
    op.alter_column('segment_transit_times', 'from_station_code',
                   existing_type=sa.VARCHAR(length=2),
                   type_=sa.VARCHAR(length=3),
                   existing_nullable=False)
    op.alter_column('segment_transit_times', 'to_station_code',
                   existing_type=sa.VARCHAR(length=2),
                   type_=sa.VARCHAR(length=3),
                   existing_nullable=False)
    
    # StationDwellTime table
    op.alter_column('station_dwell_times', 'station_code',
                   existing_type=sa.VARCHAR(length=2),
                   type_=sa.VARCHAR(length=3),
                   existing_nullable=False)
    
    # JourneyProgress table
    op.alter_column('journey_progress', 'last_departed_station',
                   existing_type=sa.VARCHAR(length=2),
                   type_=sa.VARCHAR(length=3),
                   existing_nullable=True)
    op.alter_column('journey_progress', 'next_station',
                   existing_type=sa.VARCHAR(length=2),
                   type_=sa.VARCHAR(length=3),
                   existing_nullable=True)


def downgrade() -> None:
    """Revert migration."""
    # Revert station code fields from VARCHAR(3) back to VARCHAR(2)
    
    # JourneyProgress table
    op.alter_column('journey_progress', 'next_station',
                   existing_type=sa.VARCHAR(length=3),
                   type_=sa.VARCHAR(length=2),
                   existing_nullable=True)
    op.alter_column('journey_progress', 'last_departed_station',
                   existing_type=sa.VARCHAR(length=3),
                   type_=sa.VARCHAR(length=2),
                   existing_nullable=True)
    
    # StationDwellTime table
    op.alter_column('station_dwell_times', 'station_code',
                   existing_type=sa.VARCHAR(length=3),
                   type_=sa.VARCHAR(length=2),
                   existing_nullable=False)
    
    # SegmentTransitTime table
    op.alter_column('segment_transit_times', 'to_station_code',
                   existing_type=sa.VARCHAR(length=3),
                   type_=sa.VARCHAR(length=2),
                   existing_nullable=False)
    op.alter_column('segment_transit_times', 'from_station_code',
                   existing_type=sa.VARCHAR(length=3),
                   type_=sa.VARCHAR(length=2),
                   existing_nullable=False)
    
    # LiveActivityToken table
    op.alter_column('live_activity_tokens', 'destination_code',
                   existing_type=sa.VARCHAR(length=3),
                   type_=sa.VARCHAR(length=2),
                   existing_nullable=False)
    op.alter_column('live_activity_tokens', 'origin_code',
                   existing_type=sa.VARCHAR(length=3),
                   type_=sa.VARCHAR(length=2),
                   existing_nullable=False)
    
    # DiscoveryRun table
    op.alter_column('discovery_runs', 'station_code',
                   existing_type=sa.VARCHAR(length=3),
                   type_=sa.VARCHAR(length=2),
                   existing_nullable=False)
    
    # JourneyStop table
    op.alter_column('journey_stops', 'station_code',
                   existing_type=sa.VARCHAR(length=3),
                   type_=sa.VARCHAR(length=2),
                   existing_nullable=False)
    
    # TrainJourney table
    op.alter_column('train_journeys', 'discovery_station_code',
                   existing_type=sa.VARCHAR(length=3),
                   type_=sa.VARCHAR(length=2),
                   existing_nullable=True)
    op.alter_column('train_journeys', 'terminal_station_code',
                   existing_type=sa.VARCHAR(length=3),
                   type_=sa.VARCHAR(length=2),
                   existing_nullable=False)
    op.alter_column('train_journeys', 'origin_station_code',
                   existing_type=sa.VARCHAR(length=3),
                   type_=sa.VARCHAR(length=2),
                   existing_nullable=False)