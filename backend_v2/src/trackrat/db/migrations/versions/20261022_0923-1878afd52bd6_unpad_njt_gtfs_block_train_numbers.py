"""unpad NJT GTFS block train numbers

Revision ID: 1878afd52bd6
Revises: 3cb8b7a54aa2
Create Date: 2026-10-22 09:23:39.505037

NJT zero-pads the block_id of its 2- and 3-digit trains to four characters
("0081", "0409", "0535"), and #1860 stored that block_id verbatim as the GTFS
train number, while NJT's real-time feed and nightly schedule report the bare
number (issue #1921). The parser now strips the padding; this migration
repairs what was stored before the next GTFS parse would:

- ``gtfs_trips.train_id`` is unpadded in place, so boards and train details
  stop showing "Train 0409" from the moment the migration runs rather than
  from the next daily refresh.
- NJT SCHEDULED ``train_journeys`` rows under a padded number are deleted
  (their stops cascade). Only Live Activity materialization from GTFS creates
  them; real time never reports a padded number, so such a row is never
  upgraded and the unobserved-train sweep turns it into a phantom
  cancellation beside the real train (the #1839 ghost pattern). OBSERVED rows
  and every other source are left alone.
- Active NJT ``live_activity_tokens`` registered against a padded number are
  unpadded too. The push scheduler exact-matches ``train_number`` to
  ``TrainJourney.train_id``, so once the padded journey is deleted such a
  token would find no journey and get no updates for the rest of its life;
  unpadded, it follows the real train.
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "1878afd52bd6"
down_revision = "3cb8b7a54aa2"
branch_labels = None
depends_on = None

_PADDED_NUMBER = "'^0[0-9]+$'"


_UNPADDED = "COALESCE(NULLIF(ltrim({col}, '0'), ''), '0')"


def upgrade() -> None:
    """Unpad stored GTFS train numbers and Live Activity tokens, and delete
    phantom journeys."""
    op.execute(
        f"UPDATE gtfs_trips SET train_id = {_UNPADDED.format(col='train_id')} "
        f"WHERE data_source = 'NJT' AND train_id ~ {_PADDED_NUMBER}"
    )
    op.execute(
        "UPDATE live_activity_tokens "
        f"SET train_number = {_UNPADDED.format(col='train_number')} "
        "WHERE data_source = 'NJT' AND is_active "
        f"AND train_number ~ {_PADDED_NUMBER}"
    )
    op.execute(
        "DELETE FROM train_journeys "
        "WHERE data_source = 'NJT' AND observation_type = 'SCHEDULED' "
        f"AND train_id ~ {_PADDED_NUMBER}"
    )


def downgrade() -> None:
    """No-op: the padded numbers never matched a real train."""
