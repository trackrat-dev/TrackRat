"""
Tests for GET /api/v2/trains/recent-departures query parsing.

The `lines` filter (issue #1567) lets the web line-detail departures
timeline scope the board to one line when two lines share terminal
stations (NJT Main/Bergen both HB→SF). These tests pin the endpoint's
parsing/threading contract; the SQL filter itself is covered by
tests/integration/test_recent_departures.py::test_line_codes_filter.
"""

from unittest.mock import AsyncMock, patch

from starlette.testclient import TestClient

from trackrat.models.api import DeparturesResponse


class TestRecentDeparturesLinesFilter:
    """GET /api/v2/trains/recent-departures with the `lines` filter."""

    def _get(self, e2e_client: TestClient, params: dict) -> tuple[int, AsyncMock]:
        mock_get = AsyncMock(return_value=DeparturesResponse(departures=[]))
        with patch("trackrat.api.trains.DepartureService") as mock_service_cls:
            mock_service_cls.return_value.get_recent_departures = mock_get
            resp = e2e_client.get("/api/v2/trains/recent-departures", params=params)
        return resp.status_code, mock_get

    def test_lines_param_is_parsed_and_threaded_to_service(
        self, e2e_client: TestClient
    ):
        status, mock_get = self._get(
            e2e_client, {"from": "HB", "to": "SF", "lines": "MA, Ma"}
        )

        assert status == 200
        assert mock_get.call_count == 1
        kwargs = mock_get.call_args.kwargs
        assert kwargs["line_codes"] == ["MA", "Ma"], (
            "The comma-separated `lines` value must be parsed (whitespace "
            f"stripped) and passed through; got {kwargs.get('line_codes')!r}"
        )

    def test_omitted_lines_threads_none(self, e2e_client: TestClient):
        status, mock_get = self._get(e2e_client, {"from": "HB", "to": "SF"})

        assert status == 200
        assert mock_get.call_args.kwargs["line_codes"] is None
