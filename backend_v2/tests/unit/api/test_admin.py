"""
Tests for the admin stats page endpoint.

Validates that /admin/stats returns HTML with expected sections,
/admin/stats.json returns structured data with full parity,
and both endpoints support time-windowed and iOS-only filtering.
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

    def test_contains_filter_controls(self, client):
        """Stats page has time window and client filter links."""
        response = client.get("/admin/stats")
        html = response.text

        assert "All time" in html
        assert "1h" in html
        assert "6h" in html
        assert "24h" in html
        assert "All clients" in html
        assert "iOS only" in html

    def test_contains_environment(self, client):
        """Stats page shows the current environment."""
        response = client.get("/admin/stats")
        html = response.text
        assert "TESTING" in html

    def test_contains_auto_refresh(self, client):
        """Stats page has auto-refresh meta tag."""
        response = client.get("/admin/stats")
        assert 'http-equiv="refresh"' in response.text

    def test_contains_unique_ip_count(self, client):
        """Stats page shows unique IP count in header."""
        reset_request_stats()
        stats = get_request_stats()
        stats.record_request(
            path_template="/test",
            status_code=200,
            user_agent="TrackRat/230",
            duration=0.01,
            client_ip="10.0.0.1",
        )

        response = client.get("/admin/stats")
        html = response.text
        assert "unique IPs" in html

    def test_contains_trend_column(self, client):
        """Stats page has a Trend column in the endpoint table."""
        response = client.get("/admin/stats")
        html = response.text
        assert "Trend" in html

    def test_shows_request_stats(self, client):
        """Stats page reflects in-memory request data after recording."""
        reset_request_stats()
        stats = get_request_stats()

        stats.record_request(
            path_template="/api/v2/trains/departures",
            status_code=200,
            user_agent="TrackRat/230 CFNetwork/1568",
            duration=0.05,
            client_ip="10.0.0.1",
            query_params={"from": "NY", "to": "TR"},
        )
        stats.record_request(
            path_template="/api/v2/trains/{train_id}",
            status_code=200,
            user_agent="curl/7.88",
            duration=0.03,
            client_ip="10.0.0.2",
        )

        response = client.get("/admin/stats")
        html = response.text

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
            client_ip="10.0.0.1",
            query_params={"from": "NY", "to": "TR"},
        )

        response = client.get("/admin/stats")
        html = response.text

        assert "New York Penn Station" in html
        assert "Trenton" in html

    def test_graceful_with_no_data(self, client):
        """Stats page renders cleanly when there's no traffic data."""
        reset_request_stats()
        response = client.get("/admin/stats")
        html = response.text

        assert response.status_code == 200
        assert "No requests yet" in html

    def test_hours_filter(self, client):
        """Stats page accepts ?hours= query parameter."""
        response = client.get("/admin/stats?hours=6")
        assert response.status_code == 200
        assert "last 6h" in response.text

    def test_ios_only_filter(self, client):
        """Stats page accepts ?ios_only=true and shows IP table."""
        reset_request_stats()
        stats = get_request_stats()
        stats.record_request(
            path_template="/test",
            status_code=200,
            user_agent="TrackRat/230",
            duration=0.01,
            client_ip="10.0.0.1",
        )

        response = client.get("/admin/stats?ios_only=true")
        html = response.text

        assert response.status_code == 200
        assert "(iOS only)" in html
        assert "Requests by IP" in html
        assert "10.0.0.1" in html

    def test_ios_only_no_ip_table_when_false(self, client):
        """IP table is not shown when ios_only is false."""
        reset_request_stats()
        response = client.get("/admin/stats")
        assert "Requests by IP" not in response.text

    def test_invalid_hours_rejected(self, client):
        """Invalid hours parameter returns 422."""
        response = client.get("/admin/stats?hours=0")
        assert response.status_code == 422

    def test_combined_filters(self, client):
        """Both hours and ios_only can be combined."""
        response = client.get("/admin/stats?hours=1&ios_only=true")
        assert response.status_code == 200
        html = response.text
        assert "last 1h" in html
        assert "(iOS only)" in html

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

    def test_json_includes_scheduler_jobs(self, client):
        """JSON response includes scheduler_jobs (parity with HTML)."""
        response = client.get("/admin/stats.json")
        data = response.json()
        assert (
            "scheduler_jobs" in data
        ), f"scheduler_jobs missing from JSON, keys: {list(data.keys())}"

    def test_json_includes_latency_trend(self, client):
        """JSON response includes latency_trend data."""
        reset_request_stats()
        stats = get_request_stats()
        stats.record_request(
            path_template="/test",
            status_code=200,
            user_agent="curl/7",
            duration=0.05,
            client_ip="10.0.0.1",
        )

        response = client.get("/admin/stats.json")
        data = response.json()
        assert "latency_trend" in data

    def test_json_includes_unique_ips(self, client):
        """JSON response includes unique_ips and requests_by_ip."""
        reset_request_stats()
        stats = get_request_stats()
        stats.record_request(
            path_template="/test",
            status_code=200,
            user_agent="TrackRat/230",
            duration=0.01,
            client_ip="10.0.0.1",
        )

        response = client.get("/admin/stats.json")
        data = response.json()
        assert "unique_ips" in data
        assert "requests_by_ip" in data

    def test_json_route_searches_resolved_names(self, client):
        """JSON route searches use resolved station names."""
        reset_request_stats()
        stats = get_request_stats()
        stats.record_request(
            path_template="/api/v2/trains/departures",
            status_code=200,
            user_agent="TrackRat/230",
            duration=0.04,
            client_ip="10.0.0.1",
            query_params={"from": "NY", "to": "TR"},
        )

        response = client.get("/admin/stats.json")
        data = response.json()

        # Station names should be resolved in JSON (not raw codes)
        route_keys = list(data["route_searches"].keys())
        assert len(route_keys) == 1, f"Expected 1 route, got: {route_keys}"
        assert (
            "New York Penn Station" in route_keys[0]
        ), f"Expected resolved station name, got: {route_keys[0]}"
        assert "Trenton" in route_keys[0]

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
                client_ip="10.0.0.1",
                query_params={"from": "NP", "to": "NY"},
            )

        response = client.get("/admin/stats.json")
        data = response.json()

        assert data["total_requests"] >= 5
        assert data["requests_by_path"].get("/api/v2/trains/departures", 0) >= 5
        # Route searches now use resolved names
        route_keys = list(data["route_searches"].keys())
        assert any(
            "Newark Penn Station" in k for k in route_keys
        ), f"Expected resolved NP station name, got: {route_keys}"

    def test_json_hours_filter(self, client):
        """JSON endpoint accepts ?hours= parameter."""
        response = client.get("/admin/stats.json?hours=6")
        assert response.status_code == 200
        data = response.json()
        assert data.get("window_hours") == 6

    def test_json_ios_only_filter(self, client):
        """JSON endpoint accepts ?ios_only=true parameter."""
        reset_request_stats()
        stats = get_request_stats()
        stats.record_request(
            path_template="/test",
            status_code=200,
            user_agent="TrackRat/230",
            duration=0.01,
            client_ip="10.0.0.1",
        )
        stats.record_request(
            path_template="/test",
            status_code=200,
            user_agent="curl/7",
            duration=0.01,
            client_ip="10.0.0.2",
        )

        response = client.get("/admin/stats.json?ios_only=true")
        data = response.json()

        assert data["ios_only"] is True
        assert (
            data["total_requests"] == 1
        ), f"Expected 1 iOS request, got {data['total_requests']}"
        assert "curl" not in data["requests_by_client"]

    def test_json_includes_route_search_metrics(self, client):
        """JSON endpoint includes avg_trains and empty_count in route searches."""
        reset_request_stats()
        stats = get_request_stats()

        stats.record_request(
            path_template="/api/v2/trains/departures",
            status_code=200,
            user_agent="TrackRat/230",
            duration=0.04,
            client_ip="10.0.0.1",
            query_params={"from": "NY", "to": "TR"},
        )
        stats.record_departure_results("NY", "TR", 4)
        stats.record_departure_results("NY", "TR", 0)

        response = client.get("/admin/stats.json")
        data = response.json()

        # Route key uses resolved station names
        route_key = next(k for k in data["route_searches"] if "Trenton" in k)
        route_data = data["route_searches"][route_key]
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
        # Station names are resolved in JSON output
        view_key = next(k for k in data["train_detail_views"] if "3254" in k)
        assert "Trenton" in view_key, f"Expected resolved station name, got: {view_key}"
        assert data["train_detail_views"][view_key] == 2
