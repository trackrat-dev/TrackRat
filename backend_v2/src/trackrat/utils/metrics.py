"""
Metrics collection for upstream API usage tracking.

This module provides simple decorators to track API calls to upstream services
like NJ Transit and Amtrak. Metrics are exposed via Prometheus and automatically
available in GCP Metrics Explorer when running on Cloud Run.
"""

import functools
import time
from collections.abc import Awaitable, Callable
from typing import Any

from prometheus_client import Counter, Histogram
from structlog import get_logger

logger = get_logger(__name__)

# Prometheus metrics for tracking upstream API usage
upstream_api_requests = Counter(
    "upstream_api_requests_total",
    "Total upstream API requests",
    ["api", "endpoint", "status"],
)

upstream_api_duration = Histogram(
    "upstream_api_request_duration_seconds",
    "Upstream API request duration in seconds",
    ["api", "endpoint"],
)

upstream_api_errors = Counter(
    "upstream_api_errors_total",
    "Total upstream API errors",
    ["api", "endpoint", "error_type"],
)


def track_api_call(
    api_name: str, endpoint: str
) -> Callable[[Callable[..., Awaitable[Any]]], Callable[..., Awaitable[Any]]]:
    """
    Decorator to track API calls with Prometheus metrics.

    Args:
        api_name: Name of the API (e.g., 'njtransit', 'amtrak')
        endpoint: Endpoint name (e.g., 'train_schedule', 'train_stops')

    Tracks:
        - Request count by API, endpoint, and status
        - Request duration by API and endpoint
        - Error count by API, endpoint, and error type
    """

    def decorator(func: Callable[..., Awaitable[Any]]) -> Callable[..., Awaitable[Any]]:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            start_time = time.time()
            status = "success"

            try:
                result = await func(*args, **kwargs)
                return result
            except Exception as e:
                status = "error"
                error_type = type(e).__name__

                # Track the error
                upstream_api_errors.labels(
                    api=api_name, endpoint=endpoint, error_type=error_type
                ).inc()

                logger.warning(
                    "API call failed",
                    api=api_name,
                    endpoint=endpoint,
                    error_type=error_type,
                    duration=time.time() - start_time,
                )
                raise
            finally:
                # Track request count
                upstream_api_requests.labels(
                    api=api_name, endpoint=endpoint, status=status
                ).inc()

                # Track request duration
                duration = time.time() - start_time
                upstream_api_duration.labels(api=api_name, endpoint=endpoint).observe(
                    duration
                )

                if status == "success":
                    logger.debug(
                        "API call completed",
                        api=api_name,
                        endpoint=endpoint,
                        duration=duration,
                    )

        return wrapper

    return decorator
