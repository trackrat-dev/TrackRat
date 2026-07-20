"""
Tests for the GET /api/v2/routes/summary endpoint.

These exercise the actual FastAPI response_model serialization boundary
(trackrat.models.api.SummaryMetricsResponse), not just the SummaryService
dataclasses in tests/unit/services/test_summary.py. A field present on
SummaryMetrics but missing from SummaryMetricsResponse is silently dropped
by FastAPI at this boundary and would not be caught by service-level tests
alone (issue #1376).
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

from starlette.testclient import TestClient

from trackrat.services.summary import OperationsSummary, SummaryMetrics


class TestOperationsSummaryEndpointMetrics:
    """GET /api/v2/routes/summary"""

    def test_arrival_metrics_survive_response_serialization(
        self, e2e_client: TestClient
    ):
        """Arrival stats computed by the service must reach the JSON response.

        Regression test for issue #1376: SummaryMetricsResponse previously
        omitted arrival_on_time_percentage / arrival_average_delay_minutes,
        so FastAPI's response_model filter silently stripped them even
        though SummaryService always computed them.
        """
        fake_summary = OperationsSummary(
            headline="On track",
            body="Trains are running on time.",
            scope="network",
            time_window_minutes=90,
            data_freshness_seconds=30,
            generated_at=datetime.now(UTC),
            metrics=SummaryMetrics(
                on_time_percentage=80.0,
                average_delay_minutes=3.0,
                arrival_on_time_percentage=72.5,
                arrival_average_delay_minutes=6.25,
                cancellation_count=1,
                train_count=10,
            ),
        )

        with patch(
            "trackrat.services.summary.summary_service.get_network_summary",
            new=AsyncMock(return_value=fake_summary),
        ):
            resp = e2e_client.get("/api/v2/routes/summary", params={"scope": "network"})

        assert resp.status_code == 200, resp.text
        metrics = resp.json()["metrics"]
        assert metrics["arrival_on_time_percentage"] == 72.5, (
            "arrival_on_time_percentage was dropped by the response model "
            f"(got metrics={metrics})"
        )
        assert metrics["arrival_average_delay_minutes"] == 6.25, (
            "arrival_average_delay_minutes was dropped by the response model "
            f"(got metrics={metrics})"
        )
        # Existing departure-based fields must still round-trip too.
        assert metrics["on_time_percentage"] == 80.0
        assert metrics["average_delay_minutes"] == 3.0

    def test_null_arrival_metrics_serialize_as_null(self, e2e_client: TestClient):
        """When no arrival data exists, the fields should be null, not absent."""
        fake_summary = OperationsSummary(
            headline="No data",
            body="No trains observed recently.",
            scope="network",
            time_window_minutes=90,
            data_freshness_seconds=30,
            generated_at=datetime.now(UTC),
            metrics=SummaryMetrics(
                on_time_percentage=None,
                average_delay_minutes=None,
                arrival_on_time_percentage=None,
                arrival_average_delay_minutes=None,
                cancellation_count=0,
                train_count=0,
            ),
        )

        with patch(
            "trackrat.services.summary.summary_service.get_network_summary",
            new=AsyncMock(return_value=fake_summary),
        ):
            resp = e2e_client.get("/api/v2/routes/summary", params={"scope": "network"})

        assert resp.status_code == 200, resp.text
        metrics = resp.json()["metrics"]
        assert "arrival_on_time_percentage" in metrics
        assert metrics["arrival_on_time_percentage"] is None
        assert "arrival_average_delay_minutes" in metrics
        assert metrics["arrival_average_delay_minutes"] is None


def _fake_route_summary(headline: str) -> OperationsSummary:
    return OperationsSummary(
        headline=headline,
        body=f"{headline} body.",
        scope="route",
        time_window_minutes=120,
        data_freshness_seconds=30,
        generated_at=datetime.now(UTC),
        metrics=None,
    )


class TestOperationsSummaryLinesFilter:
    """GET /api/v2/routes/summary with the `lines` filter (issue #1567).

    Lines sharing terminal stations (NJT Main/Bergen both HB→SF) need
    per-line summaries; the endpoint must parse `lines` into line codes,
    thread them to SummaryService.get_route_summary, and key its response
    cache on them so the two lines never serve each other's summary.
    """

    def test_lines_param_is_parsed_and_threaded_to_service(
        self, e2e_client: TestClient
    ):
        mock_get = AsyncMock(return_value=_fake_route_summary("Main only"))
        with patch(
            "trackrat.services.summary.summary_service.get_route_summary",
            new=mock_get,
        ):
            resp = e2e_client.get(
                "/api/v2/routes/summary",
                params={
                    "scope": "route",
                    "from_station": "HB",
                    "to_station": "SF",
                    "lines": "MA, Ma",
                },
            )

        assert resp.status_code == 200, resp.text
        assert mock_get.call_count == 1
        # Positional call: (db, from_station, to_station, data_source, line_codes)
        args = mock_get.call_args.args
        assert args[1] == "HB"
        assert args[2] == "SF"
        assert args[4] == ["MA", "Ma"], (
            "The comma-separated `lines` value must be parsed (whitespace "
            f"stripped) and passed through; got {args[4]!r}"
        )

    def test_omitted_lines_threads_none(self, e2e_client: TestClient):
        mock_get = AsyncMock(return_value=_fake_route_summary("Combined"))
        with patch(
            "trackrat.services.summary.summary_service.get_route_summary",
            new=mock_get,
        ):
            resp = e2e_client.get(
                "/api/v2/routes/summary",
                params={"scope": "route", "from_station": "HB", "to_station": "SF"},
            )

        assert resp.status_code == 200, resp.text
        assert mock_get.call_args.args[4] is None

    def test_response_cache_is_keyed_on_lines(self, e2e_client: TestClient):
        """Same station pair, different `lines` → distinct cache entries.

        The first Main request populates the DB response cache; a repeat Main
        request must be served from it (no second service call), while a
        Bergen request must miss and compute its own summary rather than being
        served Main's cached response.
        """
        mock_get = AsyncMock(
            side_effect=[
                _fake_route_summary("Main only"),
                _fake_route_summary("Bergen only"),
            ]
        )
        base_params = {"scope": "route", "from_station": "HB", "to_station": "SF"}
        with patch(
            "trackrat.services.summary.summary_service.get_route_summary",
            new=mock_get,
        ):
            main_first = e2e_client.get(
                "/api/v2/routes/summary", params={**base_params, "lines": "MA,Ma"}
            )
            main_cached = e2e_client.get(
                "/api/v2/routes/summary", params={**base_params, "lines": "MA,Ma"}
            )
            bergen = e2e_client.get(
                "/api/v2/routes/summary", params={**base_params, "lines": "BE,Be"}
            )

        assert main_first.status_code == 200, main_first.text
        assert main_cached.status_code == 200, main_cached.text
        assert bergen.status_code == 200, bergen.text

        assert main_first.json()["headline"] == "Main only"
        assert main_cached.json()["headline"] == "Main only"
        assert bergen.json()["headline"] == "Bergen only", (
            "Bergen was served Main's cached response — the response cache "
            "params must include `lines`"
        )
        assert mock_get.call_count == 2, (
            "Expected exactly two service computations (Main once + Bergen "
            f"once, with the repeat Main served from cache); got "
            f"{mock_get.call_count}"
        )
