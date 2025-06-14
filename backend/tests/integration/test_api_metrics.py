import pytest
from httpx import AsyncClient
from backend.trackcast.api.app import app # Your FastAPI app

# Mark all tests in this file as asyncio to be run by pytest-asyncio
pytestmark = pytest.mark.asyncio

@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for each test session."""
    # This is a common fixture for pytest-asyncio if not using the default one.
    # However, often pytest-asyncio handles this automatically.
    # If tests fail due to loop issues, this might be needed.
    # For now, let's assume pytest-asyncio's default loop management is sufficient.
    import asyncio
    policy = asyncio.get_event_loop_policy()
    loop = policy.new_event_loop()
    yield loop
    loop.close()

async def test_metrics_endpoint_basic_access():
    """Test that the /metrics endpoint is accessible and returns Prometheus format."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get("/metrics")
        assert response.status_code == 200
        assert "text/plain" in response.headers["content-type"]
        # Check for at least one common Prometheus metric format indicator
        assert "# TYPE http_requests_total counter" in response.text or \
               "# TYPE http_requests_created gauge" in response.text # Depending on instrumentator version

async def test_metrics_endpoint_exposes_default_fastapi_metrics():
    """Test for default metrics from prometheus-fastapi-instrumentator."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        # Make a sample call to a known endpoint (e.g., /health or /)
        await client.get("/health")

        response = await client.get("/metrics")
        assert response.status_code == 200
        metrics_text = response.text

        # Check for some standard metrics provided by the instrumentator
        assert "http_requests_total" in metrics_text # Counter for total requests
        assert "http_request_duration_seconds_bucket" in metrics_text # Histogram for latencies
        assert "http_request_duration_seconds_count" in metrics_text
        assert "http_request_duration_seconds_sum" in metrics_text
        # Check for a metric that might include labels like method and path
        assert "method=" in metrics_text
        assert "path=" in metrics_text


async def test_metrics_endpoint_exposes_custom_application_metrics():
    """Test for custom metrics defined in the application."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        # It's good to hit an endpoint that might trigger some of these custom metrics,
        # though their initial registration should make them appear anyway.
        # The /health endpoint now triggers DB and external API checks, which might generate some metrics.
        await client.get("/health")
        # A call to a data endpoint might be better for other metrics if they are not registered globally at startup.
        # However, Prometheus client typically registers metrics when they are defined globally.

        response = await client.get("/metrics")
        assert response.status_code == 200
        metrics_text = response.text

        # --- Data Collector Metrics ---
        assert "nj_transit_fetch_success_total" in metrics_text
        assert "nj_transit_fetch_failures_total" in metrics_text
        assert "amtrak_fetch_success_total" in metrics_text
        assert "amtrak_fetch_failures_total" in metrics_text

        # --- Prediction Service Metrics ---
        # Histograms expose _count and _sum, and potentially _bucket
        assert "model_inference_time_seconds_count" in metrics_text
        assert "model_inference_time_seconds_sum" in metrics_text
        assert "trains_processed_total" in metrics_text
        assert "track_prediction_confidence_ratio_count" in metrics_text
        assert "track_prediction_confidence_ratio_sum" in metrics_text
        # The accuracy gauge might not have a value if not set, but its definition should appear
        assert "model_prediction_accuracy" in metrics_text


        # --- Database Metrics ---
        # DB Query Duration Histogram
        assert "db_query_duration_seconds_count" in metrics_text
        assert "db_query_duration_seconds_sum" in metrics_text
        # DB Connection Pool Utilization Gauge
        assert "db_connection_pool_utilization_ratio" in metrics_text

        # Check for labels if they are fundamental to a metric
        # For db_query_duration_seconds, we expect a "query_type" label
        # This check is a bit more brittle if no DB calls have been made with diverse query_types yet in this test context
        # However, the metric should be registered with its labels.
        if "db_query_duration_seconds_count{" in metrics_text : # Check if there are any samples with labels
             assert "query_type=" in metrics_text
        else: # If no samples yet, check the # HELP or # TYPE definition
            assert "# TYPE db_query_duration_seconds histogram" in metrics_text


# Note: These tests primarily check for the *presence* of metric names in the /metrics output.
# They don't usually check for specific metric *values* because those can be unpredictable
# in an integration test environment and depend on the exact sequence of operations.
# The goal is to ensure that metrics are being exposed through the endpoint.
# Making a few sample API calls before scraping /metrics can help ensure some metrics are populated.
# The `/health` endpoint itself now involves DB calls and could trigger `db_query_duration_seconds`.
# It also updates `db_connection_pool_utilization_ratio`.
```
