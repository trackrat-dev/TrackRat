"""OpenTelemetry configuration for TrackCast backend.

Provides centralized setup for tracing to GCP Cloud Trace with minimal performance impact.
Automatically instruments FastAPI, SQLAlchemy, and HTTP clients.
"""

import logging
import os
from contextlib import contextmanager
from typing import Optional

from opentelemetry import propagate, trace
from opentelemetry.exporter.cloud_trace import CloudTraceSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.instrumentation.logging import LoggingInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.propagators.cloud_trace_propagator import CloudTraceFormatPropagator
from opentelemetry.resourcedetector.gcp_resource_detector import GoogleCloudResourceDetector
from opentelemetry.sdk.resources import Resource, get_aggregated_resources
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from opentelemetry.sdk.trace.sampling import Decision, StaticSampler, TraceIdRatioBased

logger = logging.getLogger(__name__)

# Global tracer instance
_tracer: Optional[trace.Tracer] = None
_instrumented = False


def setup_telemetry(
    service_name: str = "trackcast",
    sample_rate: float = None,
    enable_gcp_trace: bool = None,
    enable_console: bool = None,
) -> trace.Tracer:
    """Initialize OpenTelemetry with GCP Cloud Trace.

    Args:
        service_name: Name of the service for tracing
        sample_rate: Sampling rate (0.0-1.0). Defaults to env OTEL_SAMPLE_RATE or 0.1
        enable_gcp_trace: Enable GCP Cloud Trace export. Auto-detects if None
        enable_console: Enable console export for development. Auto-detects if None

    Returns:
        Configured tracer instance
    """
    global _tracer

    # Skip if already initialized
    if _tracer is not None:
        return _tracer

    # Environment-based configuration
    if sample_rate is None:
        sample_rate = float(os.getenv("OTEL_SAMPLE_RATE", "0.1"))

    if enable_gcp_trace is None:
        # Enable GCP trace when GOOGLE_CLOUD_PROJECT is set (works in both dev and prod)
        enable_gcp_trace = bool(os.getenv("GOOGLE_CLOUD_PROJECT"))

    if enable_console is None:
        # Only enable console tracing if explicitly requested via environment variable
        enable_console = os.getenv("OTEL_ENABLE_CONSOLE", "false").lower() == "true"

    logger.info(
        f"Initializing telemetry: service={service_name}, sample_rate={sample_rate}, "
        f"gcp_trace={enable_gcp_trace}, console={enable_console}"
    )

    # Determine final service name with proper precedence
    final_service_name = _get_service_name()

    logger.info(f"Service name determined: {final_service_name}")

    # Create resource with GCP metadata
    try:
        # Try to detect GCP resources first
        gcp_resource = GoogleCloudResourceDetector().detect()
    except Exception as e:
        logger.warning(f"Failed to detect GCP resources: {e}")
        gcp_resource = Resource.empty()

    # Create manual resource attributes (these will override GCP detected ones)
    manual_resource = Resource.create(
        {
            "service.name": final_service_name,
            "service.version": os.getenv("K_REVISION", os.getenv("SERVICE_VERSION", "unknown")),
            "service.instance.id": os.getenv("HOSTNAME", "localhost"),
            "deployment.environment": _get_environment(),
            "cloud.provider": "gcp",
            "cloud.platform": "gcp_cloud_run",
            "cloud.region": os.getenv("GOOGLE_CLOUD_REGION", "unknown"),
            "gcp.cloud_run.job.name": os.getenv("CLOUD_RUN_JOB"),
            "gcp.cloud_run.service.name": os.getenv("K_SERVICE"),
        }
    )

    # Merge resources (manual resource takes precedence)
    resource = gcp_resource.merge(manual_resource)

    # Verify service name is set correctly
    service_name_attr = resource.attributes.get("service.name")
    logger.info(f"Final service name in resource: {service_name_attr}")

    # Set up the tracer provider with intelligent sampling
    sampler = _create_intelligent_sampler(sample_rate)
    provider = TracerProvider(resource=resource, sampler=sampler)

    # Add exporters
    if enable_gcp_trace:
        try:
            cloud_trace_exporter = CloudTraceSpanExporter()
            provider.add_span_processor(BatchSpanProcessor(cloud_trace_exporter))
            logger.info("GCP Cloud Trace exporter enabled")
        except Exception as e:
            logger.warning(f"Failed to initialize GCP Cloud Trace exporter: {e}")

    if enable_console:
        console_exporter = ConsoleSpanExporter()
        provider.add_span_processor(BatchSpanProcessor(console_exporter))
        logger.info("Console trace exporter enabled")

    # Set the global tracer provider
    trace.set_tracer_provider(provider)

    # Set up propagator for distributed tracing
    propagate.set_global_textmap(CloudTraceFormatPropagator())

    # Get tracer
    _tracer = trace.get_tracer(__name__)

    return _tracer


def instrument_app(app, engine=None):
    """Instrument FastAPI app and SQLAlchemy engine with comprehensive tracing.

    Args:
        app: FastAPI application instance
        engine: SQLAlchemy engine instance (optional)
    """
    global _instrumented

    if _instrumented:
        logger.warning("Application already instrumented, skipping")
        return

    logger.info("Instrumenting application components")

    # Instrument FastAPI with detailed configuration
    FastAPIInstrumentor.instrument_app(
        app,
        # Skip health and metrics endpoints to reduce noise
        excluded_urls="/health,/metrics,/favicon.ico,/robots.txt",
        tracer_provider=trace.get_tracer_provider(),
        # Capture request/response bodies for debugging (be careful with sensitive data)
        server_request_hook=_server_request_hook,
        client_request_hook=_client_request_hook,
    )

    # Instrument SQLAlchemy with detailed query information
    if engine:
        SQLAlchemyInstrumentor().instrument(
            engine=engine,
            tracer_provider=trace.get_tracer_provider(),
            # Capture SQL statements (be careful with sensitive data)
            enable_commenter=True,
            commenter_options={
                "db_driver": True,
                "db_framework": True,
                "opentelemetry_values": True,
            },
        )
        logger.info("SQLAlchemy instrumentation enabled")

    # Instrument HTTP clients for external API calls
    HTTPXClientInstrumentor().instrument(
        tracer_provider=trace.get_tracer_provider(),
        request_hook=_http_request_hook,
        response_hook=_http_response_hook,
    )

    RequestsInstrumentor().instrument(
        tracer_provider=trace.get_tracer_provider(),
        name_callback=_requests_name_callback,
    )

    # Instrument logging to correlate logs with traces
    LoggingInstrumentor().instrument(
        tracer_provider=trace.get_tracer_provider(),
        set_logging_format=True,
    )

    _instrumented = True
    logger.info("Application instrumentation complete")


def get_tracer(name: str = None) -> trace.Tracer:
    """Get a tracer instance for creating custom spans.

    Args:
        name: Tracer name (defaults to calling module)

    Returns:
        Tracer instance
    """
    global _tracer
    if _tracer is None:
        _tracer = setup_telemetry()

    if name:
        return trace.get_tracer(name)
    return _tracer


def _sanitize_attribute_value(value):
    """Sanitize attribute values for security and OpenTelemetry compliance."""
    if value is None:
        return None

    # Convert to string if needed
    value_str = str(value)

    # Redact sensitive patterns
    import re

    # Credit card numbers
    value_str = re.sub(r"\b\d{4}[-\s]\d{4}[-\s]\d{4}[-\s]\d{4}\b", "****-****-****-****", value_str)
    # Email addresses
    value_str = re.sub(r"\b[\w.-]+@[\w.-]+\.\w+\b", "***@***.***", value_str)
    # Potential passwords or keys (simple heuristic)
    if len(value_str) > 20 and any(
        c in value_str.lower() for c in ["password", "key", "secret", "token"]
    ):
        value_str = "***REDACTED***"

    # Truncate very long values to prevent excessive span size
    if len(value_str) > 1000:
        value_str = value_str[:997] + "..."

    return value_str


@contextmanager
def trace_operation(operation_name: str, **attributes):
    """Context manager for tracing custom operations with enhanced error handling.

    Usage:
        with trace_operation("data_collection.fetch_trains", station="NY") as span:
            # do work
            span.set_attribute("trains.count", train_count)
    """
    tracer = get_tracer()
    with tracer.start_as_current_span(operation_name) as span:
        # Set initial attributes with sanitization
        for key, value in attributes.items():
            if value is not None:
                try:
                    sanitized_value = _sanitize_attribute_value(value)
                    if sanitized_value is not None:
                        span.set_attribute(key, sanitized_value)
                except Exception as e:
                    # Don't let attribute setting break the operation
                    logger.warning(f"Failed to set span attribute {key}: {e}")

        try:
            yield span
            # Mark span as successful if no exception occurred
            span.set_status(trace.Status(trace.StatusCode.OK))
        except Exception as e:
            # Record the exception and mark span as error
            span.record_exception(e)
            span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
            # Re-raise the exception to not interfere with normal error handling
            raise


def trace_function(operation_name: str = None, **default_attributes):
    """Decorator for tracing function calls.

    Usage:
        @trace_function("prediction.generate", station="NY")
        def generate_prediction(train_id: str):
            return prediction
    """

    def decorator(func):
        def wrapper(*args, **kwargs):
            name = operation_name or f"{func.__module__}.{func.__name__}"
            with trace_operation(name, **default_attributes) as span:
                try:
                    result = func(*args, **kwargs)
                    span.set_status(trace.Status(trace.StatusCode.OK))
                    return result
                except Exception as e:
                    span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
                    span.record_exception(e)
                    raise

        return wrapper

    return decorator


# Hook functions for detailed instrumentation


def _server_request_hook(span: trace.Span, scope: dict):
    """Hook for FastAPI server requests to add custom attributes."""
    if span and span.is_recording():
        # Add query parameters as attributes (be careful with sensitive data)
        query_string = scope.get("query_string", b"").decode()
        if query_string:
            span.set_attribute("http.query_string", query_string)

        # Add path parameters
        path_info = scope.get("path_info", "")
        if path_info:
            span.set_attribute("http.path_info", path_info)


def _client_request_hook(span: trace.Span, scope: dict):
    """Hook for FastAPI client requests."""
    # Add any client-specific attributes here
    pass


def _http_request_hook(span: trace.Span, request_info):
    """Hook for HTTP client requests (external APIs)."""
    if span and span.is_recording():
        # Identify external API calls
        url = str(request_info.url) if hasattr(request_info, "url") else str(request_info)

        if "njtransit.com" in url:
            span.set_attribute("external.service", "njtransit")
        elif "amtraker.com" in url:
            span.set_attribute("external.service", "amtrak")
        elif "googleapis.com" in url:
            span.set_attribute("external.service", "gcp")


def _http_response_hook(span: trace.Span, request_info, response_info):
    """Hook for HTTP client responses."""
    if span and span.is_recording() and hasattr(response_info, "status_code"):
        span.set_attribute("http.response.status_code", response_info.status_code)

        # Mark external API failures
        if response_info.status_code >= 400:
            span.set_status(
                trace.Status(trace.StatusCode.ERROR, f"HTTP {response_info.status_code}")
            )


def _requests_name_callback(request):
    """Generate span names for requests library calls."""
    url = request.url
    if "njtransit.com" in url:
        return "njtransit.api_call"
    elif "amtraker.com" in url:
        return "amtrak.api_call"
    return "http.request"


def _create_intelligent_sampler(base_rate: float):
    """Create intelligent sampler that adapts based on environment and span characteristics."""
    env = _get_environment()

    # Environment-specific sampling rates
    if base_rate is None:
        environment_rates = {
            "dev": 1.0,  # 100% in development for debugging
            "development": 1.0,
            "staging": 0.5,  # 50% in staging for testing
            "prod": 0.1,  # 10% in production for efficiency
            "production": 0.1,
        }
        base_rate = environment_rates.get(env, 0.1)

    # For now, return a standard ratio-based sampler
    # Future enhancement: implement custom sampler that always samples errors
    # and uses different rates for different span types
    return TraceIdRatioBased(base_rate)


def _get_environment() -> str:
    """Get deployment environment."""
    return (
        os.getenv("TRACKCAST_ENV") or os.getenv("ENV") or os.getenv("K_SERVICE", "").split("-")[-1]
        if os.getenv("K_SERVICE")
        else None or "unknown"
    )


def _get_service_name() -> str:
    """Determine service name based on environment and type."""
    # Priority order: OTEL_SERVICE_NAME > calculated name
    base_name = os.getenv("OTEL_SERVICE_NAME")
    if base_name:
        return base_name

    # Fallback logic based on service type and environment
    service_type = os.getenv("SERVICE_TYPE", "unknown")
    job_type = os.getenv("JOB_TYPE")
    env = _get_environment()

    if service_type == "api":
        return f"trackcast-api-{env}"
    elif service_type == "job" and job_type:
        return f"trackcast-{job_type}-{env}"
    else:
        return f"trackcast-{service_type}-{env}"


def _is_development() -> bool:
    """Check if running in development environment."""
    # Don't enable console tracing during tests
    if "pytest" in os.getenv("_", ""):
        return False

    env = _get_environment()
    return env in ("dev", "development") or os.getenv("K_SERVICE") is None  # Not in Cloud Run


# Convenience functions for common tracing patterns


def trace_repository_operation(operation_name: str, **attributes):
    """Trace database repository operations."""
    return trace_operation(f"repository.{operation_name}", **attributes)


def trace_service_operation(service_name: str, operation_name: str, **attributes):
    """Trace service layer operations."""
    return trace_operation(f"service.{service_name}.{operation_name}", **attributes)


def trace_external_api_call(api_name: str, **attributes):
    """Trace external API calls."""
    return trace_operation(f"external.{api_name}", **attributes)


def trace_ml_operation(operation_name: str, **attributes):
    """Trace machine learning operations."""
    return trace_operation(f"ml.{operation_name}", **attributes)
