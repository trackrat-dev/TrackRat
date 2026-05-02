"""Tests for the Live Activity registration endpoint.

Specifically covers issue #1050: when train_ids collide across transit
systems, the Live Activity must carry data_source so backend push updates
target the right journey.
"""

from sqlalchemy import select
from sqlalchemy.orm import sessionmaker
from starlette.testclient import TestClient

from trackrat.models.database import LiveActivityToken


def test_register_persists_data_source(e2e_client: TestClient, sync_engine):
    """data_source on the request body must be saved on the token row."""
    resp = e2e_client.post(
        "/api/v2/live-activities/register",
        json={
            "push_token": "tok-issue-1050-amtrak",
            "activity_id": "act-1",
            "train_number": "1989",
            "origin_code": "NYP",
            "destination_code": "WAS",
            "data_source": "AMTRAK",
        },
    )
    assert resp.status_code == 200, resp.text

    Session = sessionmaker(bind=sync_engine)
    with Session() as session:
        token = session.scalar(
            select(LiveActivityToken).where(
                LiveActivityToken.push_token == "tok-issue-1050-amtrak"
            )
        )
        assert token is not None
        assert token.data_source == "AMTRAK"


def test_register_accepts_missing_data_source_for_legacy_clients(
    e2e_client: TestClient, sync_engine
):
    """Older iOS clients omit data_source entirely; we must still accept them."""
    resp = e2e_client.post(
        "/api/v2/live-activities/register",
        json={
            "push_token": "tok-legacy-client",
            "activity_id": "act-legacy",
            "train_number": "1989",
            "origin_code": "NYP",
            "destination_code": "WAS",
        },
    )
    assert resp.status_code == 200, resp.text

    Session = sessionmaker(bind=sync_engine)
    with Session() as session:
        token = session.scalar(
            select(LiveActivityToken).where(
                LiveActivityToken.push_token == "tok-legacy-client"
            )
        )
        assert token is not None
        assert token.data_source is None


def test_register_updates_existing_token_data_source(
    e2e_client: TestClient, sync_engine
):
    """Re-registering the same push_token must overwrite data_source so users
    who restart a Live Activity for a different system pick up the new value."""
    payload = {
        "push_token": "tok-reregister",
        "activity_id": "act-reregister",
        "train_number": "1989",
        "origin_code": "NYP",
        "destination_code": "WAS",
        "data_source": "AMTRAK",
    }
    assert (
        e2e_client.post("/api/v2/live-activities/register", json=payload).status_code
        == 200
    )
    payload["data_source"] = "NJT"
    assert (
        e2e_client.post("/api/v2/live-activities/register", json=payload).status_code
        == 200
    )

    Session = sessionmaker(bind=sync_engine)
    with Session() as session:
        token = session.scalar(
            select(LiveActivityToken).where(
                LiveActivityToken.push_token == "tok-reregister"
            )
        )
        assert token is not None
        assert token.data_source == "NJT"
