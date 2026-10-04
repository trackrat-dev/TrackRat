"""delete NJT journeys materialized under GTFS trip ids

Revision ID: 6f2d7f054922
Revises: c96a9e34aa8b
Create Date: 2026-10-04 01:06:36.905397

Before NJT GTFS train numbers were read from block_id (issue #1839), every
NJT GTFS trip carried its internal trip_id as its train number. Starting a
Live Activity on such a "Train TBD" departure materialized a SCHEDULED
train_journeys row under that trip_id — a number NJT's real-time feed never
reports, so the row was never upgraded and the unobserved-train sweep marked
it cancelled 50 minutes after departure. Each one is a phantom cancellation
in history (cancellation rates, route alerts, summaries) beside the real train
that ran under its own number.

These are the rows production logged as `gtfs_scheduled_journey_materialized`
for NJT within log retention, each mapped through the NJT bundle published
2026-09-17 to the train it shadowed (trip_id -> block_id): 2938 -> 6437 and
1920 -> 1212. Matching on the full unique key plus SCHEDULED and the sweep's
cancellation reason means a real train that later took the same row (it would
be OBSERVED) is never touched, and the statement is a no-op where the rows do
not exist (staging, fresh databases). Older materializations predate log
retention and age out with the retention window.
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "6f2d7f054922"
down_revision = "c96a9e34aa8b"
branch_labels = None
depends_on = None


# (train_id, journey_date) of each phantom row; see module docstring.
_PHANTOM_JOURNEYS = (("2938", "2026-09-22"), ("1920", "2026-10-01"))


def upgrade() -> None:
    """Delete the phantom rows; their stops cascade."""
    keys = ", ".join(
        f"('{train_id}', DATE '{journey_date}')"
        for train_id, journey_date in _PHANTOM_JOURNEYS
    )
    op.execute(
        "DELETE FROM train_journeys "
        f"WHERE (train_id, journey_date) IN ({keys}) "
        "AND data_source = 'NJT' AND observation_type = 'SCHEDULED' "
        "AND cancellation_reason = 'Not observed in real-time feed'"
    )


def downgrade() -> None:
    """No-op: the deleted rows described trains that never existed."""
