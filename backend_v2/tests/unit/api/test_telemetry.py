"""Tests for the onboarding telemetry endpoint.

The endpoint exists so the iOS setup funnel can be measured from the structured
logs, so these tests assert on what actually lands in the log event — including
the field validator that keeps an unauthenticated caller from writing arbitrary
strings into the metric.
"""

from __future__ import annotations

import logging

from starlette.testclient import TestClient

from trackrat.api.telemetry import OnboardingCompletedRequest


class TestKeepKnownSources:
    """Unit tests for the systems field validator."""

    def test_keeps_known_data_sources(self) -> None:
        request = OnboardingCompletedRequest(systems="NJT,PATH")
        assert request.systems == "NJT,PATH"

    def test_sorts_and_deduplicates(self) -> None:
        """Sorted output keeps the same selection from splitting the metric
        across several spellings."""
        request = OnboardingCompletedRequest(systems="PATH,NJT,NJT")
        assert request.systems == "NJT,PATH"

    def test_drops_unknown_entries(self) -> None:
        """An arbitrary string must not reach the logs the funnel is read from."""
        request = OnboardingCompletedRequest(systems="NJT,NOT_A_SYSTEM,<script>")
        assert request.systems == "NJT"

    def test_empty_when_nothing_is_recognized(self) -> None:
        request = OnboardingCompletedRequest(systems="garbage")
        assert request.systems == ""

    def test_defaults_to_empty(self) -> None:
        request = OnboardingCompletedRequest()
        assert request.systems == ""
        assert request.favorites_count == 0
        assert request.home_station_set is False
        assert request.work_station_set is False
        assert request.used_location is False
        assert request.skipped is False
        assert request.app_version is None


class TestReportOnboardingCompleted:
    """Endpoint-level tests for /api/v2/telemetry/onboarding."""

    def test_logs_completed_setup(self, client: TestClient, caplog) -> None:
        caplog.set_level(logging.INFO)
        resp = client.post(
            "/api/v2/telemetry/onboarding",
            json={
                "systems": "NJT",
                "home_station_set": True,
                "work_station_set": True,
                "favorites_count": 2,
                "used_location": True,
                "skipped": False,
                "app_version": "3.8",
            },
        )

        assert resp.status_code == 200
        assert resp.json()["status"] == "received"
        assert "onboarding_completed" in caplog.text
        assert "systems=NJT" in caplog.text
        assert "home_station_set=True" in caplog.text
        assert "work_station_set=True" in caplog.text
        assert "favorites_count=2" in caplog.text
        assert "used_location=True" in caplog.text
        assert "skipped=False" in caplog.text
        assert "app_version=3.8" in caplog.text

    def test_logs_skipped_setup(self, client: TestClient, caplog) -> None:
        """A skipped run is the case the funnel most needs to count."""
        caplog.set_level(logging.INFO)
        resp = client.post(
            "/api/v2/telemetry/onboarding",
            json={"systems": "SUBWAY", "skipped": True},
        )

        assert resp.status_code == 200
        assert "onboarding_completed" in caplog.text
        assert "skipped=True" in caplog.text
        assert "home_station_set=False" in caplog.text

    def test_rejects_out_of_range_favorites_count(self, client: TestClient) -> None:
        """Bounds are enforced server-side, not trusted from the client."""
        resp = client.post(
            "/api/v2/telemetry/onboarding",
            json={"favorites_count": 10_000},
        )

        assert resp.status_code == 422

    def test_accepts_empty_body(self, client: TestClient, caplog) -> None:
        """Every field has a default, so a minimal client still records a run."""
        caplog.set_level(logging.INFO)
        resp = client.post("/api/v2/telemetry/onboarding", json={})

        assert resp.status_code == 200
        assert "onboarding_completed" in caplog.text
