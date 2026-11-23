"""
Integration tests for migration 74985c32620b (issue #1928), run against real
Postgres: live_activity_tokens.train_number and route_alert_subscriptions.train_id
are widened from varchar(30) to varchar(64) so 34-char GTFS-scheduled subway
train ids fit, and the downgrade narrows them back by truncating.
"""

import importlib

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

migration = importlib.import_module(
    "trackrat.db.migrations.versions."
    "20261024_0904-74985c32620b_widen_client_train_id_columns_to_64"
)

LONG_ID = "S6X-L0S2-6-1091-S01_055500_6..S02R"  # 34 chars


def _run(session: Session, step: str) -> None:
    context = MigrationContext.configure(session.connection())
    with Operations.context(context):
        getattr(migration, step)()


async def _widths(db: AsyncSession) -> dict[str, int]:
    rows = await db.execute(
        text(
            "SELECT table_name, character_maximum_length FROM information_schema.columns"
            " WHERE (table_name, column_name) IN"
            " (('live_activity_tokens', 'train_number'),"
            "  ('route_alert_subscriptions', 'train_id'))"
        )
    )
    return {str(table): int(width) for table, width in rows.tuples()}


async def _narrow_to_pre_migration_width(db: AsyncSession) -> None:
    """The test schema is built from the (already widened) models; put the
    columns back to their pre-migration width."""
    await db.execute(
        text(
            "ALTER TABLE live_activity_tokens ALTER COLUMN train_number TYPE varchar(30)"
        )
    )
    await db.execute(
        text(
            "ALTER TABLE route_alert_subscriptions ALTER COLUMN train_id TYPE varchar(30)"
        )
    )


async def _insert_token(db: AsyncSession, push_token: str, train_number: str) -> None:
    await db.execute(
        text(
            "INSERT INTO live_activity_tokens"
            " (push_token, activity_id, train_number, origin_code, destination_code,"
            "  is_active)"
            " VALUES (:push_token, 'act', :train_number, 'S635', 'S631', true)"
        ),
        {"push_token": push_token, "train_number": train_number},
    )


class TestWidenClientTrainIdColumns:
    async def test_upgrade_widens_both_columns_so_long_subway_ids_fit(
        self, db_session: AsyncSession
    ) -> None:
        await _narrow_to_pre_migration_width(db_session)
        print(f"before upgrade: {await _widths(db_session)}")
        with pytest.raises(DBAPIError, match="value too long"):
            async with db_session.begin_nested():
                await _insert_token(db_session, "tok-before", LONG_ID)

        await db_session.run_sync(_run, "upgrade")

        widths = await _widths(db_session)
        print(f"after upgrade: {widths}")
        assert widths == {"live_activity_tokens": 64, "route_alert_subscriptions": 64}
        await _insert_token(db_session, "tok-after", LONG_ID)
        stored = await db_session.scalar(
            text(
                "SELECT train_number FROM live_activity_tokens"
                " WHERE push_token = 'tok-after'"
            )
        )
        assert stored == LONG_ID

    async def test_downgrade_truncates_long_ids_back_to_30(
        self, db_session: AsyncSession
    ) -> None:
        await _insert_token(db_session, "tok-long", LONG_ID)
        await _insert_token(db_session, "tok-short", "1989")

        await db_session.run_sync(_run, "downgrade")

        widths = await _widths(db_session)
        print(f"after downgrade: {widths}")
        assert widths == {"live_activity_tokens": 30, "route_alert_subscriptions": 30}
        rows = dict(
            (
                await db_session.execute(
                    text("SELECT push_token, train_number FROM live_activity_tokens")
                )
            ).all()
        )
        print(f"rows after downgrade: {rows}")
        assert rows == {"tok-long": LONG_ID[:30], "tok-short": "1989"}
