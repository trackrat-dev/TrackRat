"""Tests for the share-link OG-preview endpoints.

Covers:
- Pure string-formatting helpers (no DB)
- The HTML route's tag structure for found/not-found cases
- The image route's PNG output / 404 behavior

Helper-level tests use synthesized ``TrainJourney``/``JourneyStop`` instances
to avoid DB setup; route-level tests use the ``db_session`` fixture and the
``client`` fixture to hit FastAPI through ``TestClient``.
"""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.testclient import TestClient

from trackrat.api.share import (
    _arrival_at,
    _build_image_url,
    _build_spa_url,
    _format_clock_time,
    _format_share_strings,
)
from trackrat.models.database import JourneyStop, TrainJourney

# Hoboken at 5:42 PM ET = 21:42 UTC
HOBOKEN_ARRIVAL_UTC = datetime(2026, 4, 24, 21, 42, tzinfo=UTC)


def _make_journey(
    *,
    train_id: str = "3957",
    data_source: str = "NJT",
    terminal: str = "HB",  # Hoboken
    is_cancelled: bool = False,
    observation_type: str = "OBSERVED",
    stops: list[JourneyStop] | None = None,
) -> TrainJourney:
    """Synthesize a TrainJourney. Not persisted — for pure-function tests."""
    j = TrainJourney(
        train_id=train_id,
        journey_date=date(2026, 4, 24),
        line_code="MC",
        line_name="Morris & Essex",
        destination="Hoboken",
        origin_station_code="DV",
        terminal_station_code=terminal,
        data_source=data_source,
        observation_type=observation_type,
        scheduled_departure=datetime(2026, 4, 24, 20, 30, tzinfo=UTC),
        is_cancelled=is_cancelled,
        has_complete_journey=True,
        stops_count=(len(stops) if stops is not None else 0),
    )
    j.stops = stops or []
    return j


# ---- pure-function helpers ----


class TestFormatClockTime:
    def test_pm_strips_leading_zero(self) -> None:
        # 21:42 UTC = 17:42 ET = "5:42 PM"
        from trackrat.utils.time import normalize_to_et

        assert _format_clock_time(normalize_to_et(HOBOKEN_ARRIVAL_UTC)) == "5:42 PM"

    def test_am_strips_leading_zero(self) -> None:
        from trackrat.utils.time import normalize_to_et

        # 12:15 UTC = 8:15 AM ET (during daylight savings)
        dt = datetime(2026, 4, 24, 12, 15, tzinfo=UTC)
        assert _format_clock_time(normalize_to_et(dt)) == "8:15 AM"


class TestArrivalAt:
    def test_prefers_actual_over_updated(self) -> None:
        actual = datetime(2026, 4, 24, 21, 40, tzinfo=UTC)
        updated = datetime(2026, 4, 24, 21, 50, tzinfo=UTC)
        scheduled = datetime(2026, 4, 24, 21, 30, tzinfo=UTC)
        stop = JourneyStop(
            station_code="HB",
            station_name="Hoboken",
            actual_arrival=actual,
            updated_arrival=updated,
            scheduled_arrival=scheduled,
        )
        journey = _make_journey(data_source="AMTRAK", stops=[stop])
        assert _arrival_at(journey, "HB") == actual

    def test_falls_back_to_scheduled_when_no_live_data(self) -> None:
        scheduled = datetime(2026, 4, 24, 21, 30, tzinfo=UTC)
        stop = JourneyStop(
            station_code="HB", station_name="Hoboken", scheduled_arrival=scheduled
        )
        journey = _make_journey(stops=[stop])
        assert _arrival_at(journey, "HB") == scheduled

    def test_njt_uses_max_of_updated_arrival_and_departure(self) -> None:
        """NJT semantic mismatch — updated_departure can be the live estimate."""
        updated_arr = datetime(2026, 4, 24, 21, 30, tzinfo=UTC)
        updated_dep = datetime(2026, 4, 24, 21, 50, tzinfo=UTC)  # later
        stop = JourneyStop(
            station_code="HB",
            station_name="Hoboken",
            updated_arrival=updated_arr,
            updated_departure=updated_dep,
        )
        journey = _make_journey(data_source="NJT", stops=[stop])
        assert _arrival_at(journey, "HB") == updated_dep

    def test_returns_none_when_no_matching_stop_for_non_terminal(self) -> None:
        """User asked about XYZ which isn't a stop on this journey: return None,
        don't lie with the terminal time."""
        terminal_stop = JourneyStop(
            station_code="HB",
            station_name="Hoboken",
            actual_arrival=HOBOKEN_ARRIVAL_UTC,
        )
        journey = _make_journey(terminal="HB", stops=[terminal_stop])
        assert _arrival_at(journey, "XYZ") is None

    def test_falls_back_to_journey_arrival_when_terminal_has_no_stop_record(
        self,
    ) -> None:
        """Schedule-only journeys may not have JourneyStop rows yet; the
        journey-level arrival is the right fallback for the terminal."""
        scheduled_arrival = datetime(2026, 4, 24, 21, 30, tzinfo=UTC)
        journey = _make_journey(terminal="HB", stops=[])
        journey.scheduled_arrival = scheduled_arrival
        assert _arrival_at(journey, "HB") == scheduled_arrival


class TestFormatShareStrings:
    def test_normal_arriving(self) -> None:
        stop = JourneyStop(
            station_code="HB",
            station_name="Hoboken",
            actual_arrival=HOBOKEN_ARRIVAL_UTC,
        )
        journey = _make_journey(data_source="NJT", stops=[stop])
        headline, status = _format_share_strings(journey, None)
        assert headline == "NJT 3957 to Hoboken"
        assert status == "Arriving 5:42 PM"

    def test_cancelled_overrides_arrival(self) -> None:
        stop = JourneyStop(
            station_code="HB",
            station_name="Hoboken",
            actual_arrival=HOBOKEN_ARRIVAL_UTC,
        )
        journey = _make_journey(is_cancelled=True, stops=[stop])
        headline, status = _format_share_strings(journey, None)
        assert headline == "NJT 3957 to Hoboken"
        assert status == "Cancelled"

    def test_scheduled_observation_type(self) -> None:
        stop = JourneyStop(
            station_code="HB",
            station_name="Hoboken",
            scheduled_arrival=HOBOKEN_ARRIVAL_UTC,
        )
        journey = _make_journey(observation_type="SCHEDULED", stops=[stop])
        _, status = _format_share_strings(journey, None)
        assert status == "Scheduled 5:42 PM"

    def test_user_to_station_overrides_terminal(self) -> None:
        # User shared from NY → Newark Penn (NP), train terminates at HB
        np_arrival = datetime(2026, 4, 24, 21, 0, tzinfo=UTC)  # 5:00 PM ET
        stops = [
            JourneyStop(
                station_code="NP", station_name="Newark", actual_arrival=np_arrival
            ),
            JourneyStop(
                station_code="HB",
                station_name="Hoboken",
                actual_arrival=HOBOKEN_ARRIVAL_UTC,
            ),
        ]
        journey = _make_journey(stops=stops)
        headline, status = _format_share_strings(journey, "NP")
        assert "to Newark" in headline
        assert status == "Arriving 5:00 PM"

    def test_no_eta_falls_back_to_generic_status(self) -> None:
        # Stop is at terminal but has no times set (rare edge case)
        stop = JourneyStop(station_code="HB", station_name="Hoboken")
        journey = _make_journey(stops=[stop])
        _, status = _format_share_strings(journey, None)
        assert status == "View train details"


# ---- URL builders ----


class TestBuildSpaUrl:
    def test_no_params(self) -> None:
        assert (
            _build_spa_url("3957", None, None, None)
            == "https://trackrat.net/train/3957"
        )

    def test_full_params(self) -> None:
        url = _build_spa_url("3957", date(2026, 4, 24), "NY", "HB")
        assert url == "https://trackrat.net/train/3957?date=2026-04-24&from=NY&to=HB"

    def test_train_id_with_special_chars_is_escaped(self) -> None:
        """A malicious train_id must not be able to inject URL structure."""
        # Path traversal attempt
        url = _build_spa_url("../evil.com", None, None, None)
        assert url == "https://trackrat.net/train/..%2Fevil.com"
        # Query-string injection attempt
        url2 = _build_spa_url("3957?x=evil", date(2026, 4, 24), None, None)
        assert url2 == "https://trackrat.net/train/3957%3Fx%3Devil?date=2026-04-24"


class TestBuildImageUrl:
    def test_uses_request_host_and_drops_from_param(self) -> None:
        from unittest.mock import MagicMock

        request = MagicMock()
        request.url.scheme = "https"
        request.url.netloc = "apiv2.trackrat.net"
        url = _build_image_url(request, "3957", date(2026, 4, 24), "NY", "HB")
        assert url == (
            "https://apiv2.trackrat.net/share/train/3957/image?date=2026-04-24&to=HB"
        )


# ---- Route-level smoke tests (no DB data; mock client returns None) ----


class TestShareRoutes:
    def test_html_returns_fallback_when_train_not_found(
        self, client: TestClient
    ) -> None:
        resp = client.get("/share/train/UNKNOWN")
        assert resp.status_code == 200
        body = resp.text
        assert resp.headers["content-type"].startswith("text/html")
        # OG tags present
        assert '<meta property="og:title" content="TrackRat">' in body
        assert "Real-time train tracking" in body
        # No og:image when train missing
        assert "og:image" not in body
        # Redirect to SPA
        assert (
            'http-equiv="refresh" content="0; url=https://trackrat.net/train/UNKNOWN"'
            in body
        )

    def test_image_returns_404_when_train_not_found(self, client: TestClient) -> None:
        resp = client.get("/share/train/UNKNOWN/image")
        assert resp.status_code == 404


class TestAppleAppSiteAssociation:
    """The AASA file enables Universal Links into the iOS app for /share/train/*."""

    def test_returns_json_with_correct_appid_and_path(self, client: TestClient) -> None:
        resp = client.get("/.well-known/apple-app-site-association")
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "application/json"

        data = resp.json()
        details = data["applinks"]["details"]
        assert len(details) == 1
        assert details[0]["appIDs"] == ["D5RZZ55J9R.net.trackrat.TrackRat"]
        components = details[0]["components"]
        assert any(c.get("/") == "/share/train/*" for c in components)


# ---- DB-backed integration tests for the happy path ----


@pytest.mark.asyncio
class TestShareRoutesWithRealJourney:
    async def test_html_includes_rich_og_tags_when_journey_present(
        self, db_session: AsyncSession, e2e_client: TestClient
    ) -> None:
        # Insert a journey
        journey = TrainJourney(
            train_id="3957",
            journey_date=date(2026, 4, 24),
            line_code="MC",
            line_name="Morris & Essex",
            destination="Hoboken",
            origin_station_code="DV",
            terminal_station_code="HB",
            data_source="NJT",
            observation_type="OBSERVED",
            scheduled_departure=datetime(2026, 4, 24, 20, 30, tzinfo=UTC),
            is_cancelled=False,
            has_complete_journey=True,
            stops_count=1,
        )
        db_session.add(journey)
        await db_session.flush()
        db_session.add(
            JourneyStop(
                journey_id=journey.id,
                station_code="HB",
                station_name="Hoboken",
                stop_sequence=0,
                actual_arrival=HOBOKEN_ARRIVAL_UTC,
            )
        )
        await db_session.commit()

        resp = e2e_client.get("/share/train/3957?date=2026-04-24")
        assert resp.status_code == 200
        body = resp.text
        assert '<meta property="og:title" content="NJT 3957 to Hoboken">' in body
        assert '<meta property="og:description" content="Arriving 5:42 PM">' in body
        assert "og:image" in body  # exact URL depends on TestClient host
        assert (
            'http-equiv="refresh" content="0; url=https://trackrat.net/train/3957?date=2026-04-24"'
            in body
        )

    async def test_image_returns_png_when_journey_present(
        self, db_session: AsyncSession, e2e_client: TestClient
    ) -> None:
        journey = TrainJourney(
            train_id="3957",
            journey_date=date(2026, 4, 24),
            line_code="MC",
            line_name="Morris & Essex",
            destination="Hoboken",
            origin_station_code="DV",
            terminal_station_code="HB",
            data_source="NJT",
            observation_type="OBSERVED",
            scheduled_departure=datetime(2026, 4, 24, 20, 30, tzinfo=UTC),
            is_cancelled=False,
            has_complete_journey=True,
            stops_count=1,
        )
        db_session.add(journey)
        await db_session.flush()
        db_session.add(
            JourneyStop(
                journey_id=journey.id,
                station_code="HB",
                station_name="Hoboken",
                stop_sequence=0,
                actual_arrival=HOBOKEN_ARRIVAL_UTC,
            )
        )
        await db_session.commit()

        resp = e2e_client.get("/share/train/3957/image?date=2026-04-24")
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "image/png"
        assert resp.content.startswith(b"\x89PNG\r\n\x1a\n")
        assert "max-age=" in resp.headers.get("cache-control", "")
