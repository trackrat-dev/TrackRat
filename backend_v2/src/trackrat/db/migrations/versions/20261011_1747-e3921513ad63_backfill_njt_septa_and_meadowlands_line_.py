"""backfill njt septa and meadowlands line codes

Revision ID: e3921513ad63
Revises: 6f2d7f054922
Create Date: 2026-10-11 17:47:53.901216

Discovery truncated three real-time LINE names it did not recognize to two
characters (issue #1883): "Septa" -> "Se", "BetMGM Meadowlands" -> "Be" and
"DoorDash Meadowlands Line" -> "Do". "Be" is Bergen County's legacy alias, so
Meadowlands event trains were counted as Bergen County Line trains in route
history, congestion baselines and line-mode alerts. The parser now yields
NJT's own LINECODE ("SP", "SL"); this rewrites the stored rows to match.

"Be" and "Do" are rewritten only where the journey's line_name names the
Meadowlands: genuine pre-2026-03 Bergen County rows also carry "Be". "Se" is
rewritten unconditionally: discovery stores the real-time LINE_NAME, which is
blank for SEPTA trains, so a line_name guard would match nothing — and no NJT
line name or legacy alias produces "Se" otherwise.

Startup cost matches c96a9e34aa8b (one sequential scan per derived table,
~15s locally over 10M rows); journey_stops is not touched.
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "e3921513ad63"
down_revision = "6f2d7f054922"
branch_labels = None
depends_on = None


# Tables that copy train_journeys.line_code per journey (transit_analyzer).
_DERIVED_TABLES = ("segment_transit_times", "station_dwell_times")

_MEADOWLANDS_JOURNEYS = (
    "SELECT id FROM train_journeys "
    "WHERE data_source = 'NJT' AND line_name ILIKE '%meadowlands%'"
)


def upgrade() -> None:
    """Rewrite truncated SEPTA / Meadowlands NJT line codes to SP / SL."""
    # A derived row is judged by its journey's line_name: journey collection
    # may since have healed the journey itself to "SL".
    for table in ("train_journeys", *_DERIVED_TABLES):
        journey_id = "id" if table == "train_journeys" else "journey_id"
        op.execute(
            f"UPDATE {table} "
            "SET line_code = CASE line_code WHEN 'Se' THEN 'SP' ELSE 'SL' END "
            "WHERE data_source = 'NJT' AND (line_code = 'Se' "
            f"OR (line_code IN ('Be', 'Do') AND {journey_id} IN ({_MEADOWLANDS_JOURNEYS})))"
        )


def downgrade() -> None:
    """No-op: the truncated codes were never valid, and a rewritten row cannot
    be told apart from one the fixed parser wrote."""
