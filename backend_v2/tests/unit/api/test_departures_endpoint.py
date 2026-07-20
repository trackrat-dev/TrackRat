"""
Tests for GET /api/v2/trains/departures query parsing of the `lines` filter
(issue #1567 / PR #1585 review).

The web line-detail timeline's upcoming feed calls /trains/departures in line
mode. These pin the endpoint's parsing/threading and cache-bypass contract;
the SQL filter + filter-before-limit behavior is covered by
tests/integration/test_departures_line_filter.py.
"""

import inspect
from unittest.mock import AsyncMock, patch

from starlette.testclient import TestClient

from trackrat.api.trains import get_departures, get_recent_departures
from trackrat.models.api import DeparturesResponse
from trackrat.services.departure import ALL_DATA_SOURCES


class TestDeparturesLinesFilter:
    """GET /api/v2/trains/departures with the `lines` filter."""

    def _get(self, e2e_client: TestClient, params: dict) -> tuple[int, AsyncMock]:
        mock_get = AsyncMock(return_value=DeparturesResponse(departures=[]))
        with patch("trackrat.api.trains.DepartureService") as mock_service_cls:
            mock_service_cls.return_value.get_departures = mock_get
            resp = e2e_client.get("/api/v2/trains/departures", params=params)
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

    def test_line_scoped_request_bypasses_cache(self, e2e_client: TestClient):
        """A line-scoped request must skip the shared departures cache (and its
        data_sources superset fallback) so it can never serve unfiltered rows;
        the service is always invoked to compute a fresh, filtered result."""
        mock_get = AsyncMock(return_value=DeparturesResponse(departures=[]))
        with (
            patch("trackrat.api.trains.DepartureService") as mock_service_cls,
            patch(
                "trackrat.api.trains.ApiCacheService.get_cached_response",
                new=AsyncMock(return_value={"departures": [], "metadata": {}}),
            ) as mock_cache_get,
        ):
            mock_service_cls.return_value.get_departures = mock_get
            resp = e2e_client.get(
                "/api/v2/trains/departures",
                params={"from": "HB", "to": "SF", "lines": "MA,Ma"},
            )

        assert resp.status_code == 200
        assert mock_cache_get.await_count == 0, (
            "Line-scoped requests must not read the departures cache; a cache "
            "hit could serve unfiltered rows"
        )
        assert (
            mock_get.await_count == 1
        ), "Service must be invoked to compute the line-filtered result"


class TestDataSourcesDescriptionListsAllSources:
    """The `data_sources` param docs must list every served source (issue #1574).

    The default is "all" and `ALL_DATA_SOURCES` governs what is actually served,
    so a client passing an explicit `data_sources` filter has only these
    description strings to learn which values exist. They drifted out of sync
    when SEPTA_RR/SEPTA_METRO were added (present in `ALL_DATA_SOURCES`, absent
    from the docs). These tests pin the two strings to `ALL_DATA_SOURCES` so any
    future source addition that forgets the docs fails here.
    """

    @staticmethod
    def _data_sources_description(endpoint) -> str:
        param = inspect.signature(endpoint).parameters["data_sources"]
        # The default is a FastAPI Query(...) object carrying `.description`.
        return param.default.description or ""

    def test_get_departures_description_lists_every_served_source(self):
        description = self._data_sources_description(get_departures)
        missing = [s for s in ALL_DATA_SOURCES if s not in description]
        assert not missing, (
            f"get_departures data_sources description omits served sources "
            f"{missing}; description={description!r}"
        )

    def test_get_recent_departures_description_lists_every_served_source(self):
        description = self._data_sources_description(get_recent_departures)
        missing = [s for s in ALL_DATA_SOURCES if s not in description]
        assert not missing, (
            f"get_recent_departures data_sources description omits served "
            f"sources {missing}; description={description!r}"
        )
