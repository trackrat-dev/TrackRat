"""
Tests for the admin stats page endpoint.

Validates that /admin/stats returns HTML with expected sections,
and /admin/stats.json returns structured data.
"""

from trackrat.utils.request_stats import get_request_stats, reset_request_stats


class TestAdminStatsPage:
    """Tests for the /admin/stats HTML endpoint."""

    def test_returns_html(self, client):
        """Stats page returns 200 with HTML content type."""
        response = client.get("/admin/stats")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    def test_contains_page_structure(self, client):
        """Stats page contains expected HTML structure."""
        response = client.get("/admin/stats")
        html = response.text

        assert "<title>TrackRat Stats" in html
        assert "TrackRat Server Stats" in html
        assert "Traffic by Endpoint" in html
        assert "Popular Route Searches" in html
        assert "Clients" in html
        assert "Providers (Today)" in html
        assert "Scheduler Jobs" in html

    def test_contains_environment(self, client):
        """Stats page shows the current environment."""
        response = client.get("/admin/stats")
        html = response.text
        assert "TESTING" in html

    def test_contains_auto_refresh(self, client):
        """Stats page has auto-refresh meta tag."""
        response = client.get("/admin/stats")
        assert 'http-equiv="refresh"' in response.text

    def test_shows_request_stats(self, client):
        """Stats page reflects in-memory request data after recording."""
        reset_request_stats()
        stats = get_request_stats()

        # Simulate some recorded traffic
        stats.record_request(
            path_template="/api/v2/trains/departures",
            status_code=200,
            user_agent="TrackRat/230 CFNetwork/1568",
            duration=0.05,
            query_params={"from": "NY", "to": "TR"},
        )
        stats.record_request(
            path_template="/api/v2/trains/{train_id}",
            status_code=200,
            user_agent="curl/7.88",
            duration=0.03,
        )

        response = client.get("/admin/stats")
        html = response.text

        # Verify request data appears in the page
        assert "/api/v2/trains/departures" in html
        assert "/api/v2/trains/{train_id}" in html
        assert "iOS/230" in html
        assert "curl" in html

    def test_shows_route_searches_with_station_names(self, client):
        """Stats page shows route searches with human-readable station names."""
        reset_request_stats()
        stats = get_request_stats()

        stats.record_request(
            path_template="/api/v2/trains/departures",
            status_code=200,
            user_agent="TrackRat/230",
            duration=0.05,
            query_params={"from": "NY", "to": "TR"},
        )

        response = client.get("/admin/stats")
        html = response.text

        # Station names should be resolved (NY = New York Penn Station, TR = Trenton)
        assert "New York Penn Station" in html
        assert "Trenton" in html

    def test_graceful_with_no_data(self, client):
        """Stats page renders cleanly when there's no traffic data."""
        reset_request_stats()
        response = client.get("/admin/stats")
        html = response.text

        assert response.status_code == 200
        assert "No requests yet" in html


    def test_shows_route_search_result_metrics(self, client):
        """Stats page shows avg trains and empty response count per route."""
        reset_request_stats()
        stats = get_request_stats()

        stats.record_request(
            path_template="/api/v2/trains/departures",
            status_code=200,
            user_agent="TrackRat/230",
            duration=0.05,
            query_params={"from": "NY", "to": "TR"},
        )
        stats.record_departure_results("NY", "TR", 5)
        stats.record_departure_results("NY", "TR", 0)
        stats.record_departure_results("NY", "TR", 3)

        response = client.get("/admin/stats")
        html = response.text

        # Table headers
        assert "Avg Trains" in html
        assert "Empty" in html
        # Average of 5,0,3 = 2.7
        assert "2.7" in html
        # One empty response
        assert "warn" in html  # empty count > 0 gets warn class

    def test_shows_train_detail_views(self, client):
        """Stats page shows Popular Train Details section."""
        reset_request_stats()
        stats = get_request_stats()

        stats.record_train_detail_view("3254", "NY", "TR")
        stats.record_train_detail_view("3254", "NY", "TR")

        response = client.get("/admin/stats")
        html = response.text

        assert "Popular Train Details" in html
        assert "3254" in html
        assert "New York Penn Station" in html
        assert "Trenton" in html

    def test_train_detail_views_empty_state(self, client):
        """Stats page shows empty state for train detail views when none recorded."""
        reset_request_stats()
        response = client.get("/admin/stats")
        html = response.text

        assert "Popular Train Details" in html
        assert "No views yet" in html


class TestAdminStatsJson:
    """Tests for the /admin/stats.json JSON endpoint."""

    def test_returns_json(self, client):
        """JSON endpoint returns 200 with application/json."""
        response = client.get("/admin/stats.json")
        assert response.status_code == 200
        assert "application/json" in response.headers["content-type"]

    def test_json_structure(self, client):
        """JSON response contains expected top-level keys."""
        reset_request_stats()
        response = client.get("/admin/stats.json")
        data = response.json()

        assert "uptime_seconds" in data
        assert "total_requests" in data
        assert "requests_by_path" in data
        assert "requests_by_status" in data
        assert "requests_by_client" in data
        assert "route_searches" in data
        assert "providers" in data
        assert "device_count" in data
        assert "alert_subscription_count" in data
        assert "live_activity_count" in data

    def test_json_reflects_recorded_data(self, client):
        """JSON endpoint reflects in-memory request stats."""
        reset_request_stats()
        stats = get_request_stats()

        for _ in range(5):
            stats.record_request(
                path_template="/api/v2/trains/departures",
                status_code=200,
                user_agent="TrackRat/230",
                duration=0.04,
                query_params={"from": "NP", "to": "NY"},
            )

        response = client.get("/admin/stats.json")
        data = response.json()

        assert data["total_requests"] >= 5
        assert data["requests_by_path"].get("/api/v2/trains/departures", 0) >= 5
        assert "NP -> NY" in data["route_searches"]

    def test_json_includes_route_search_metrics(self, client):
        """JSON endpoint includes avg_trains and empty_count in route searches."""
        reset_request_stats()
        stats = get_request_stats()

        stats.record_request(
            path_template="/api/v2/trains/departures",
            status_code=200,
            user_agent="TrackRat/230",
            duration=0.04,
            query_params={"from": "NY", "to": "TR"},
        )
        stats.record_departure_results("NY", "TR", 4)
        stats.record_departure_results("NY", "TR", 0)

        response = client.get("/admin/stats.json")
        data = response.json()

        route_data = data["route_searches"]["NY -> TR"]
        assert route_data["count"] == 1
        assert route_data["avg_trains"] == 2.0
        assert route_data["empty_count"] == 1

    def test_json_includes_train_detail_views(self, client):
        """JSON endpoint includes train_detail_views."""
        reset_request_stats()
        stats = get_request_stats()

        stats.record_train_detail_view("3254", "NY", "TR")
        stats.record_train_detail_view("3254", "NY", "TR")

        response = client.get("/admin/stats.json")
        data = response.json()

        assert "train_detail_views" in data
        assert data["train_detail_views"]["3254 (NY -> TR)"] == 2
