"""
Google Cloud Monitoring metrics exporter service.

This module provides integration between Prometheus metrics and Google Cloud Monitoring,
allowing TrackCast metrics to be exported to GCP's Metrics Explorer for monitoring and alerting.
"""

import asyncio
import logging
import os
import random
import time
from datetime import datetime, timezone
from threading import Lock, Thread
from typing import Dict, List, Optional, Union

from google.cloud import monitoring_v3
from google.oauth2 import service_account
from google.protobuf.timestamp_pb2 import Timestamp
from prometheus_client import REGISTRY
from prometheus_client.samples import Sample

logger = logging.getLogger(__name__)


class GCPMetricsExporter:
    """
    Google Cloud Monitoring metrics exporter for Prometheus metrics.

    Exports Prometheus metrics to Google Cloud Monitoring with automatic batching,
    error handling, and environment detection.
    """

    def __init__(
        self,
        project_id: Optional[str] = None,
        service_account_path: Optional[str] = None,
        metric_prefix: str = "trackcast",
        export_interval_seconds: int = 180,
        max_batch_size: int = 50,
        enabled: bool = None,
    ):
        """
        Initialize the GCP metrics exporter.

        Args:
            project_id: GCP project ID (auto-detected if None)
            service_account_path: Path to service account JSON (optional)
            metric_prefix: Prefix for all metric names in GCP
            export_interval_seconds: How often to export metrics to GCP
            max_batch_size: Maximum number of metrics per batch request
            enabled: Enable/disable export (auto-detected based on environment if None)
        """
        self.project_id = (
            project_id or os.getenv("GOOGLE_CLOUD_PROJECT") or os.getenv("GCP_PROJECT")
        )
        self.service_account_path = service_account_path or os.getenv(
            "GOOGLE_APPLICATION_CREDENTIALS"
        )
        self.metric_prefix = metric_prefix
        self.export_interval = export_interval_seconds
        self.max_batch_size = max_batch_size

        # Auto-detect if we should enable export
        if enabled is None:
            enabled = bool(self.project_id)
        self.enabled = enabled

        # Initialize client and state
        self._client: Optional[monitoring_v3.MetricServiceClient] = None
        self._project_name: Optional[str] = None
        self._last_export_time = 0
        self._export_thread: Optional[Thread] = None
        self._stop_export = False
        self._export_lock = Lock()
        self._export_stats = {
            "last_export_time": None,
            "last_export_success": None,
            "total_exports": 0,
            "total_errors": 0,
            "last_error": None,
        }

        # Metric type cache to avoid repeated creation
        self._metric_type_cache: Dict[str, str] = {}

        # Backoff state for rate limiting
        self._consecutive_failures = 0
        self._last_failure_time = 0

        # Timestamp tracking for deduplication
        self._last_export_timestamp = 0

        if self.enabled:
            try:
                self._initialize_client()
                logger.info(f"GCP Metrics Exporter initialized for project: {self.project_id}")
            except Exception as e:
                logger.warning(f"Failed to initialize GCP Metrics Exporter: {e}")
                self.enabled = False
        else:
            logger.info("GCP Metrics Exporter disabled (no project ID or explicitly disabled)")

    def _initialize_client(self):
        """Initialize the Google Cloud Monitoring client."""
        if not self.project_id:
            raise ValueError("Project ID is required for GCP metrics export")

        # Initialize credentials if service account path is provided
        credentials = None
        if self.service_account_path and os.path.exists(self.service_account_path):
            credentials = service_account.Credentials.from_service_account_file(
                self.service_account_path
            )

        # Create the monitoring client
        self._client = monitoring_v3.MetricServiceClient(credentials=credentials)
        self._project_name = f"projects/{self.project_id}"

        logger.info(f"GCP Monitoring client initialized for project: {self.project_id}")

    def start_background_export(self):
        """Start background thread for periodic metric export."""
        if not self.enabled:
            logger.info("GCP metrics export disabled, not starting background export")
            return

        if self._export_thread and self._export_thread.is_alive():
            logger.warning("Background export thread already running")
            return

        self._stop_export = False
        self._export_thread = Thread(target=self._export_loop, daemon=True)
        self._export_thread.start()
        logger.info(f"Started background metrics export (interval: {self.export_interval}s)")

    def stop_background_export(self):
        """Stop background metric export thread."""
        self._stop_export = True
        if self._export_thread and self._export_thread.is_alive():
            self._export_thread.join(timeout=5.0)
            logger.info("Stopped background metrics export")

    def _export_loop(self):
        """Background export loop."""
        while not self._stop_export:
            try:
                self.export_metrics()
                time.sleep(self.export_interval)
            except Exception as e:
                logger.error(f"Error in background metrics export: {e}")
                time.sleep(min(self.export_interval, 30))  # Back off on errors

    def export_metrics(self) -> bool:
        """
        Export current Prometheus metrics to Google Cloud Monitoring.

        Returns:
            True if export succeeded, False otherwise
        """
        if not self.enabled:
            return False

        try:
            with self._export_lock:
                return self._do_export()
        except Exception as e:
            logger.error(f"Failed to export metrics to GCP: {e}")
            self._export_stats["total_errors"] += 1
            self._export_stats["last_error"] = str(e)
            self._export_stats["last_export_success"] = False
            return False

    def _do_export(self) -> bool:
        """Perform the actual metrics export."""
        if not self._client:
            logger.error("GCP Monitoring client not initialized")
            return False

        start_time = time.time()

        # Collect all metrics from Prometheus registry
        metric_families = list(REGISTRY.collect())
        time_series = []

        base_time = datetime.now(timezone.utc)

        # Ensure this export timestamp is after the last one
        base_timestamp = base_time.timestamp()
        if base_timestamp <= self._last_export_timestamp:
            # Add 1 second to ensure monotonic progression
            base_timestamp = self._last_export_timestamp + 1
            base_time = datetime.fromtimestamp(base_timestamp, timezone.utc)

        self._last_export_timestamp = base_timestamp
        nanos_offset = 0  # Offset to ensure unique timestamps

        for family in metric_families:
            # Skip internal Prometheus metrics
            if family.name.startswith("python_") or family.name.startswith("process_"):
                continue

            for sample in family.samples:
                try:
                    # Create unique timestamp for each metric to avoid GCP collisions
                    microsecond_offset = nanos_offset % 1000000  # Keep within microsecond range
                    current_time = base_time.replace(
                        microsecond=min(base_time.microsecond + microsecond_offset, 999999)
                    )
                    nanos_offset += 100  # 100 microsecond increment per metric

                    # Validate timestamp is not in the future (GCP requirement)
                    if current_time > datetime.now(timezone.utc):
                        current_time = datetime.now(timezone.utc)

                    # Create time series for this metric
                    ts = self._create_time_series(sample, family, current_time)
                    if ts:
                        time_series.append(ts)
                except Exception as e:
                    logger.warning(f"Failed to create time series for {sample.name}: {e}")
                    continue

        if not time_series:
            logger.debug("No metrics to export")
            return True

        # Export in batches
        success = True
        total_exported = 0
        last_error = None

        for i in range(0, len(time_series), self.max_batch_size):
            batch = time_series[i : i + self.max_batch_size]
            try:
                request = monitoring_v3.CreateTimeSeriesRequest(
                    name=self._project_name, time_series=batch
                )
                self._client.create_time_series(request=request)
                total_exported += len(batch)
                logger.debug(f"Exported batch of {len(batch)} metrics to GCP")

                # Reset backoff on success
                self._consecutive_failures = 0

            except Exception as e:
                error_msg = str(e)
                logger.error(f"Failed to export metrics batch: {error_msg}")
                success = False
                last_error = error_msg

                # Implement exponential backoff for rate limiting errors
                if (
                    "more frequently than the maximum sampling period" in error_msg
                    or "RESOURCE_EXHAUSTED" in error_msg
                    or "400" in error_msg
                ):
                    self._consecutive_failures += 1
                    self._last_failure_time = time.time()

                    # Calculate backoff delay: 2^failures seconds with jitter, max 300s
                    backoff_delay = min(2**self._consecutive_failures, 300)
                    jitter = random.uniform(0.5, 1.5)  # Add jitter to prevent thundering herd
                    actual_delay = backoff_delay * jitter

                    logger.warning(
                        f"Rate limited by GCP, backing off for {actual_delay:.1f}s "
                        f"(failure #{self._consecutive_failures})"
                    )
                    time.sleep(actual_delay)

        # Update export stats
        export_time = time.time() - start_time
        self._export_stats.update(
            {
                "last_export_time": current_time.isoformat(),
                "last_export_success": success,
                "total_exports": self._export_stats["total_exports"] + 1,
                "last_error": last_error,
            }
        )

        if success:
            logger.info(
                f"Successfully exported {total_exported} metrics to GCP in {export_time:.2f}s"
            )

        return success

    def _create_time_series(
        self, sample: Sample, family, timestamp: datetime
    ) -> Optional[monitoring_v3.TimeSeries]:
        """
        Create a GCP TimeSeries from a Prometheus sample.

        Args:
            sample: Prometheus sample
            family: Metric family
            timestamp: Timestamp for the metric

        Returns:
            TimeSeries object or None if conversion failed
        """
        try:
            # Create metric type (cached to avoid repeated API calls)
            metric_type = self._get_or_create_metric_type(sample.name, family)

            # Convert labels to GCP format
            labels = {}
            for label_name, label_value in sample.labels.items():
                # GCP label names must start with letter and contain only alphanumeric + underscore
                clean_name = self._clean_label_name(label_name)
                labels[clean_name] = str(label_value)

            # Create the time series
            series = monitoring_v3.TimeSeries()
            series.metric.type = metric_type
            series.resource.type = "global"  # Use global resource for simplicity
            series.metric.labels.update(labels)

            # Add the data point
            point = monitoring_v3.Point()
            ts = Timestamp()
            # Use full timestamp precision to ensure uniqueness
            seconds = int(timestamp.timestamp())
            nanos = int((timestamp.timestamp() - seconds) * 1e9)
            ts.seconds = seconds
            ts.nanos = nanos
            point.interval.end_time = ts

            # Set value based on metric type
            if family.type == "counter":
                point.value.double_value = float(sample.value)
            elif family.type == "gauge":
                point.value.double_value = float(sample.value)
            elif family.type == "histogram":
                # For histograms, we'll export the individual bucket/sum/count metrics
                point.value.double_value = float(sample.value)
            else:
                # Default to double value
                point.value.double_value = float(sample.value)

            series.points.append(point)

            return series

        except Exception as e:
            logger.warning(f"Failed to create time series for {sample.name}: {e}")
            return None

    def _get_or_create_metric_type(self, metric_name: str, family) -> str:
        """Get or create a metric type in GCP, with caching."""
        # Clean the metric name for GCP (must start with letter)
        clean_name = self._clean_metric_name(metric_name)
        full_metric_type = f"custom.googleapis.com/{self.metric_prefix}/{clean_name}"

        # Return from cache if available
        if full_metric_type in self._metric_type_cache:
            return full_metric_type

        # Store in cache (we don't need to actually create the descriptor in advance)
        # GCP will create it automatically when we send the first data point
        self._metric_type_cache[full_metric_type] = full_metric_type

        return full_metric_type

    def _clean_metric_name(self, name: str) -> str:
        """Clean metric name for GCP compatibility."""
        # Replace invalid characters with underscores
        clean = "".join(c if c.isalnum() or c == "_" else "_" for c in name)

        # Ensure it starts with a letter
        if clean and not clean[0].isalpha():
            clean = "metric_" + clean

        return clean or "unknown_metric"

    def _clean_label_name(self, name: str) -> str:
        """Clean label name for GCP compatibility."""
        # Replace invalid characters with underscores
        clean = "".join(c if c.isalnum() or c == "_" else "_" for c in name)

        # Ensure it starts with a letter
        if clean and not clean[0].isalpha():
            clean = "label_" + clean

        return clean or "unknown_label"

    def get_export_stats(self) -> Dict[str, Union[str, int, bool, None]]:
        """Get export statistics for health checks."""
        return self._export_stats.copy()

    def is_enabled(self) -> bool:
        """Check if GCP metrics export is enabled."""
        return self.enabled

    def export_single_metric(
        self,
        metric_name: str,
        value: float,
        labels: Optional[Dict[str, str]] = None,
        metric_type: str = "gauge",
    ) -> bool:
        """
        Export a single metric immediately.

        Args:
            metric_name: Name of the metric
            value: Metric value
            labels: Optional labels for the metric
            metric_type: Type of metric (gauge, counter)

        Returns:
            True if export succeeded, False otherwise
        """
        if not self.enabled or not self._client:
            return False

        try:
            labels = labels or {}
            timestamp = datetime.now(timezone.utc)

            # Create metric type
            clean_name = self._clean_metric_name(metric_name)
            full_metric_type = f"custom.googleapis.com/{self.metric_prefix}/{clean_name}"

            # Create time series
            series = monitoring_v3.TimeSeries()
            series.metric.type = full_metric_type
            series.resource.type = "global"

            # Add labels
            for label_name, label_value in labels.items():
                clean_label = self._clean_label_name(label_name)
                series.metric.labels[clean_label] = str(label_value)

            # Add data point
            point = monitoring_v3.Point()
            ts = Timestamp()
            seconds = int(timestamp.timestamp())
            nanos = int((timestamp.timestamp() - int(timestamp.timestamp())) * 1e9)
            ts.seconds = seconds
            ts.nanos = nanos
            point.interval.end_time = ts
            point.value.double_value = float(value)
            series.points.append(point)

            # Export
            request = monitoring_v3.CreateTimeSeriesRequest(
                name=self._project_name, time_series=[series]
            )
            self._client.create_time_series(request=request)

            logger.debug(f"Exported single metric {metric_name}={value} to GCP")
            return True

        except Exception as e:
            logger.error(f"Failed to export single metric {metric_name}: {e}")
            return False


# Global instance for use throughout the application
_gcp_exporter: Optional[GCPMetricsExporter] = None


def get_gcp_exporter() -> Optional[GCPMetricsExporter]:
    """Get the global GCP metrics exporter instance."""
    return _gcp_exporter


def initialize_gcp_exporter(
    project_id: Optional[str] = None,
    service_account_path: Optional[str] = None,
    metric_prefix: str = "trackcast",
    export_interval_seconds: int = 180,
    enabled: bool = None,
) -> GCPMetricsExporter:
    """
    Initialize the global GCP metrics exporter.

    Args:
        project_id: GCP project ID (auto-detected if None)
        service_account_path: Path to service account JSON (optional)
        metric_prefix: Prefix for all metric names in GCP
        export_interval_seconds: How often to export metrics to GCP
        enabled: Enable/disable export (auto-detected if None)

    Returns:
        GCPMetricsExporter instance
    """
    global _gcp_exporter

    _gcp_exporter = GCPMetricsExporter(
        project_id=project_id,
        service_account_path=service_account_path,
        metric_prefix=metric_prefix,
        export_interval_seconds=export_interval_seconds,
        enabled=enabled,
    )

    return _gcp_exporter


def start_gcp_export():
    """Start background GCP metrics export if initialized."""
    if _gcp_exporter:
        _gcp_exporter.start_background_export()


def stop_gcp_export():
    """Stop background GCP metrics export if running."""
    if _gcp_exporter:
        _gcp_exporter.stop_background_export()


def export_metrics_now() -> bool:
    """Export metrics immediately. Returns True if successful."""
    if _gcp_exporter:
        return _gcp_exporter.export_metrics()
    return False


def export_single_metric(
    metric_name: str, value: float, labels: Optional[Dict[str, str]] = None
) -> bool:
    """Export a single metric immediately. Returns True if successful."""
    if _gcp_exporter:
        return _gcp_exporter.export_single_metric(metric_name, value, labels)
    return False
