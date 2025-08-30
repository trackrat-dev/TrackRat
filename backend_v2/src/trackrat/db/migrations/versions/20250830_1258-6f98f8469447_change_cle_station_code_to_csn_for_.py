"""Change CLE station code to CSN for Clemson

Revision ID: 6f98f8469447
Revises: 2d9bbf285b25
Create Date: 2025-08-30 12:58:02.242819

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '6f98f8469447'
down_revision = '2d9bbf285b25'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Apply migration."""
    # Update all CLE station codes to CSN for Clemson
    op.execute("UPDATE journey_stops SET station_code = 'CSN' WHERE station_code = 'CLE'")


def downgrade() -> None:
    """Revert migration."""
    # Revert CSN station codes back to CLE
    op.execute("UPDATE journey_stops SET station_code = 'CLE' WHERE station_code = 'CSN'")