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
            resp = e2e_client.get(
                "/api/v2/routes/summary", params={"scope": "network"}
            )

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
            resp = e2e_client.get(
                "/api/v2/routes/summary", params={"scope": "network"}
            )

        assert resp.status_code == 200, resp.text
        metrics = resp.json()["metrics"]
        assert "arrival_on_time_percentage" in metrics
        assert metrics["arrival_on_time_percentage"] is None
        assert "arrival_average_delay_minutes" in metrics
        assert metrics["arrival_average_delay_minutes"] is None
