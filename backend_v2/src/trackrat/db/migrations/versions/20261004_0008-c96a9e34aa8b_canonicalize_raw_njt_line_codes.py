"""canonicalize raw NJT line codes

Revision ID: c96a9e34aa8b
Revises: 600992355efa
Create Date: 2026-10-04 00:08:13.920973

Journey collection wrote NJT's own getTrainStopList LINECODE verbatim ("ML",
"BC", "GS", "MC"), and discovery stored the real-time "No Jersey Coast" as its
truncation "No". None of those codes is in any route_topology line_codes set,
so the rows were invisible to every exact line_code filter: the historical
track predictor and delay forecaster (60-day history), line-mode route alert
evaluation, and route-history baselines over segment_transit_times. Since
issue #1839 the collectors write canonical codes; this rewrites the stored
rows so history written before and after the fix agrees.

"No" is only rewritten where the journey's line_name identifies the Coast
Line: before the "northeast" prefix existed, "Northeast Corridor" was
truncated to "No" too.

Startup cost: one sequential scan per derived table (a single UPDATE each
covers both rewrites). Production held ~7M segment_transit_times rows on
2026-10-03. A local run of this migration over 5M segment_transit_times and
5M station_dwell_times rows, a fifth of them rewritten (a heavier share than
production's), took ~15s — well inside the MIG's 300s initial health-check
delay. (Backfill migration f7a8b9c0d1e2 was pulled for scanning the 35M-row
journey_stops at startup; that table is not touched here.)
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "c96a9e34aa8b"
down_revision = "600992355efa"
branch_labels = None
depends_on = None


# Frozen copy of utils.train.NJT_LINECODE_ALIASES at this revision — a
# migration must not change meaning when the live map grows.
_NJT_LINECODE_ALIASES = {"ML": "MA", "BC": "BE", "GS": "GL", "MC": "MO"}

# Tables that copy train_journeys.line_code per journey (transit_analyzer).
_DERIVED_TABLES = ("segment_transit_times", "station_dwell_times")

# 'No' maps to NC only on rows the predicate below confines to the Coast Line.
_CANONICAL_CASE = "CASE line_code {} WHEN 'No' THEN 'NC' END".format(
    " ".join(
        f"WHEN '{raw}' THEN '{canonical}'"
        for raw, canonical in _NJT_LINECODE_ALIASES.items()
    )
)
_RAW_CODES = ", ".join(f"'{raw}'" for raw in _NJT_LINECODE_ALIASES)
_COAST_LINE_JOURNEYS = (
    "SELECT id FROM train_journeys "
    "WHERE data_source = 'NJT' AND line_name ILIKE '%jersey coast%'"
)


def upgrade() -> None:
    """Rewrite raw NJT line codes to TrackRat's canonical codes."""
    # A derived row's "No" is judged by its journey's line_name: journey
    # collection may since have healed the journey itself to "NC".
    for table in ("train_journeys", *_DERIVED_TABLES):
        journey_id = "id" if table == "train_journeys" else "journey_id"
        op.execute(
            f"UPDATE {table} SET line_code = {_CANONICAL_CASE} "
            f"WHERE data_source = 'NJT' AND (line_code IN ({_RAW_CODES}) "
            f"OR (line_code = 'No' AND {journey_id} IN ({_COAST_LINE_JOURNEYS})))"
        )


def downgrade() -> None:
    """No-op: the raw codes were never valid, and a canonical row cannot be
    told apart from one that was rewritten here."""
