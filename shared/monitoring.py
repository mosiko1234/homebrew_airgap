"""
Monitoring and observability module for the Homebrew Bottles Sync System.

This module provides comprehensive monitoring capabilities including:
- CloudWatch custom metrics for sync progress and errors
- Structured logging for all components
- X-Ray tracing for Lambda functions
- Performance metrics and health checks
"""

import json
import logging
import time
import os
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, field
from enum import Enum
from contextlib import contextmanager
import boto3
from botocore.exceptions import ClientError

try:
    from aws_xray_sdk.core import xray_recorder, patch_all
    from aws_xray_sdk.core.context import Context
    XRAY_AVAILABLE = True
except ImportError:
    XRAY_AVAILABLE = False


class MetricType(Enum):
    """Types of metrics that can be recorded."""
    COUNTER = "counter"
    GAUGE = "gauge"
    TIMER = "timer"
    HISTOGRAM = "histogram"


class SyncPhase(Enum):
    """Phases of the sync process for tracking."""
    INITIALIZATION = "initialization"
    FORMULA_FETCH = "formula_fetch"
    HASH_LOADING = "hash_loading"
    DOWNLOAD_PLANNING = "download_planning"
    BOTTLE_DOWNLOAD = "bottle_download"
    S3_UPLOAD = "s3_upload"
    HASH_UPDATE = "hash_update"
    NOTIFICATION = "notification"
    CLEANUP = "cleanup"


@dataclass
class MetricData:
    """Data structure for metric information."""
    name: str
    value: Union[int, float]
    unit: str = "Count"
    dimensions: Dict[str, str] = field(default_factory=dict)
    timestamp: Optional[datetime] = None
    
    def __post_init__(self):
        """Set timestamp if not provided."""
        if self.timestamp is None:
            self.timestamp = datetime.now(timezone.utc)


@dataclass
class PerformanceMetrics:
    """Performance metrics for sync operations."""
    operation_name: str
    start_time: float
    end_time: Optional[float] = None
    success: bool = True
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def duration(self) -> Optional[float]:
        """Get operation duration in seconds."""
        if self.end_time:
            return self.end_time - self.start_time
        return None
    
    def finish(self, success: bool = True, error_message: Optional[str] = None):
        """Mark operation as finished."""
        self.end_time = time.time()
        self.success = success
        self.error_message = error_message


class CloudWatchMetricsClient:
    """Enhanced CloudWatch metrics client with batching and error handling."""
    
    def __init__(self, namespace: str = "HomebrewSync", region: str = None):
        """
        Initialize CloudWatch metrics client.
        
        Args:
            namespace: CloudWatch namespace for metrics
            region: AWS region (defaults to environment or us-east-1)
        """
        self.namespace = namespace
        self.region = region or os.environ.get('AWS_REGION', 'us-east-1')
        self._cloudwatch = None
        self.logger = logging.getLogger(__name__)
        
        # Metric batching
        self._metric_buffer: List[MetricData] = []
        self._buffer_size = 20  # CloudWatch limit
        self._last_flush = time.time()
        self._flush_interval = 60  # seconds
    
    @property
    def cloudwatch(self):
        """Lazy initialization of CloudWatch client."""
        if self._cloudwatch is None:
            self._cloudwatch = boto3.client('cloudwatch', region_name=self.region)
        return self._cloudwatch
    
    def put_metric(self, name: str, value: Union[int, float], unit: str = "Count",
                   dimensions: Optional[Dict[str, str]] = None, 
                   timestamp: Optional[datetime] = None) -> bool:
        """
        Put a metric to CloudWatch (buffered).
        
        Args:
            name: Metric name
            value: Metric value
            unit: Metric unit
            dimensions: Optional dimensions
            timestamp: Optional timestamp
            
        Returns:
            True if metric was queued successfully
        """
        try:
            metric = MetricData(
                name=name,
                value=value,
                unit=unit,
                dimensions=dimensions or {},
                timestamp=timestamp
            )
            
            self._metric_buffer.append(metric)
            
            # Auto-flush if buffer is full or interval exceeded
            if (len(self._metric_buffer) >= self._buffer_size or 
                time.time() - self._last_flush > self._flush_interval):
                self.flush_metrics()
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to queue metric {name}: {e}")
            return False
    
    def flush_metrics(self) -> bool:
        """
        Flush buffered metrics to CloudWatch.
        
        Returns:
            True if all metrics were sent successfully
        """
        if not self._metric_buffer:
            return True
        
        try:
            # Prepare metric data for CloudWatch
            metric_data = []
            for metric in self._metric_buffer:
                data = {
                    'MetricName': metric.name,
                    'Value': metric.value,
                    'Unit': metric.unit,
                    'Timestamp': metric.timestamp
                }
                
                if metric.dimensions:
                    data['Dimensions'] = [
                        {'Name': k, 'Value': v} for k, v in metric.dimensions.items()
                    ]
                
                metric_data.append(data)
            
            # Send to CloudWatch
            self.cloudwatch.put_metric_data(
                Namespace=self.namespace,
                MetricData=metric_data
            )
            
            self.logger.debug(f"Flushed {len(metric_data)} metrics to CloudWatch")
            
            # Clear buffer
            self._metric_buffer.clear()
            self._last_flush = time.time()
            
            return True
            
        except ClientError as e:
            self.logger.error(f"Failed to flush metrics to CloudWatch: {e}")
            return False
    
    def put_sync_progress_metrics(self, completed: int, total: int, failed: int = 0,
                                  sync_phase: SyncPhase = SyncPhase.BOTTLE_DOWNLOAD) -> None:
        """
        Put sync progress metrics.
        
        Args:
            completed: Number of completed bottles
            total: Total number of bottles
            failed: Number of failed bottles
            sync_phase: Current sync phase
        """
        dimensions = {'SyncPhase': sync_phase.value}
        
        self.put_metric('BottlesCompleted', completed, 'Count', dimensions)
        self.put_metric('BottlesTotal', total, 'Count', dimensions)
        self.put_metric('BottlesFailed', failed, 'Count', dimensions)
        
        if total > 0:
            progress_percentage = (completed / total) * 100
            self.put_metric('SyncProgress', progress_percentage, 'Percent', dimensions)
    
    def put_download_metrics(self, bottle_name: str, size_bytes: int, 
                           duration_seconds: float, success: bool) -> None:
        """
        Put bottle download metrics.
        
        Args:
            bottle_name: Name of the bottle
            size_bytes: Size of the bottle in bytes
            duration_seconds: Download duration
            success: Whether download was successful
        """
        dimensions = {
            'BottleName': bottle_name,
            'Success': str(success)
        }
        
        self.put_metric('BottleDownloadCount', 1, 'Count', dimensions)
        self.put_metric('BottleDownloadSize', size_bytes, 'Bytes', dimensions)
        self.put_metric('BottleDownloadDuration', duration_seconds, 'Seconds', dimensions)
        
        if success and duration_seconds > 0:
            throughput_mbps = (size_bytes / (1024 * 1024)) / duration_seconds
            self.put_metric('DownloadThroughput', throughput_mbps, 'Count/Second', dimensions)
    
    def put_error_metrics(self, error_type: str, operation: str, 
                         component: str = "unknown") -> None:
        """
        Put error metrics.
        
        Args:
            error_type: Type of error
            operation: Operation that failed
            component: Component where error occurred
        """
        dimensions = {
            'ErrorType': error_type,
            'Operation': operation,
            'Component': component
        }
        
        self.put_metric('Errors', 1, 'Count', dimensions)
    
    def put_performance_metrics(self, perf_metrics: PerformanceMetrics) -> None:
        """
        Put performance metrics.
        
        Args:
            perf_metrics: Performance metrics data
        """
        dimensions = {
            'Operation': perf_metrics.operation_name,
            'Success': str(perf_metrics.success)
        }
        
        if perf_metrics.duration:
            self.put_metric('OperationDuration', perf_metrics.duration, 'Seconds', dimensions)
        
        self.put_metric('OperationCount', 1, 'Count', dimensions)
        
        # Add custom dimensions from metadata
        for key, value in perf_metrics.metadata.items():
            if isinstance(value, (str, int, float)):
                dimensions[key] = str(value)
        
        if not perf_metrics.success:
            self.put_metric('OperationFailures', 1, 'Count', dimensions)


class StructuredLogger:
    """Enhanced structured logger with CloudWatch integration."""
    
    def __init__(self, name: str, level: str = "INFO", 
                 enable_cloudwatch: bool = True):
        """
        Initialize structured logger.
        
        Args:
            name: Logger name
            level: Log level
            enable_cloudwatch: Whether to enable CloudWatch structured logging
        """
        self.logger = logging.getLogger(name)
        self.logger.setLevel(getattr(logging, level.upper()))
        self.enable_cloudwatch = enable_cloudwatch
        
        # Remove existing handlers to avoid duplicates
        for handler in self.logger.handlers[:]:
            self.logger.removeHandler(handler)
        
        # Add structured handler
        self._setup_structured_handler()
    
    def _setup_structured_handler(self):
        """Setup structured logging handler."""
        handler = logging.StreamHandler()
        
        class StructuredFormatter(logging.Formatter):
            """JSON formatter for structured logging."""
            
            def format(self, record):
                # Base log entry
                log_entry = {
                    'timestamp': datetime.fromtimestamp(
                        record.created, timezone.utc
                    ).isoformat().replace('+00:00', 'Z'),
                    'level': record.levelname,
                    'logger': record.name,
                    'message': record.getMessage(),
                    'module': record.module,
                    'function': record.funcName,
                    'line': record.lineno,
                    'thread': record.thread,
                    'process': record.process
                }
                
                # Add exception info if present
                if record.exc_info:
                    log_entry['exception'] = self.formatException(record.exc_info)
                
                # Add extra fields from record
                for key, value in record.__dict__.items():
                    if key not in ['name', 'msg', 'args', 'levelname', 'levelno', 
                                  'pathname', 'filename', 'module', 'lineno', 
                                  'funcName', 'created', 'msecs', 'relativeCreated', 
                                  'thread', 'threadName', 'processName', 'process', 
                                  'getMessage', 'exc_info', 'exc_text', 'stack_info']:
                        log_entry[key] = value
                
                # Add AWS context if available
                if hasattr(record, 'aws_request_id'):
                    log_entry['aws_request_id'] = record.aws_request_id
                
                return json.dumps(log_entry, default=str)
        
        handler.setFormatter(StructuredFormatter())
        self.logger.addHandler(handler)
    
    def info(self, message: str, **kwargs):
        """Log info message with structured data."""
        self.logger.info(message, extra=kwargs)
    
    def warning(self, message: str, **kwargs):
        """Log warning message with structured data."""
        self.logger.warning(message, extra=kwargs)
    
    def error(self, message: str, **kwargs):
        """Log error message with structured data."""
        self.logger.error(message, extra=kwargs)
    
    def debug(self, message: str, **kwargs):
        """Log debug message with structured data."""
        self.logger.debug(message, extra=kwargs)
    
    def log_sync_event(self, event_type: str, details: Dict[str, Any]):
        """
        Log a sync-specific event.
        
        Args:
            event_type: Type of sync event
            details: Event details
        """
        self.info(f"Sync event: {event_type}", 
                 event_type=event_type, 
                 sync_event=True,
                 **details)
    
    def log_performance(self, perf_metrics: PerformanceMetrics):
        """
        Log performance metrics.
        
        Args:
            perf_metrics: Performance metrics to log
        """
        self.info(f"Performance: {perf_metrics.operation_name}",
                 operation=perf_metrics.operation_name,
                 duration=perf_metrics.duration,
                 success=perf_metrics.success,
                 error_message=perf_metrics.error_message,
                 performance_event=True,
                 **perf_metrics.metadata)


class XRayTracer:
    """X-Ray tracing wrapper for Lambda functions."""
    
    def __init__(self, enabled: bool = None):
        """
        Initialize X-Ray tracer.
        
        Args:
            enabled: Whether X-Ray tracing is enabled (auto-detect if None)
        """
        if enabled is None:
            enabled = XRAY_AVAILABLE and os.environ.get('_X_AMZN_TRACE_ID') is not None
        
        self.enabled = enabled
        self.logger = logging.getLogger(__name__)
        
        if self.enabled and XRAY_AVAILABLE:
            # Patch AWS SDK calls
            patch_all()
            self.logger.info("X-Ray tracing enabled")
        else:
            self.logger.info("X-Ray tracing disabled")
    
    @contextmanager
    def trace_subsegment(self, name: str, metadata: Optional[Dict[str, Any]] = None):
        """
        Create a traced subsegment.
        
        Args:
            name: Subsegment name
            metadata: Optional metadata to attach
        """
        if self.enabled and XRAY_AVAILABLE:
            subsegment = xray_recorder.begin_subsegment(name)
            try:
                if metadata:
                    subsegment.put_metadata('custom', metadata)
                yield subsegment
            except Exception as e:
                subsegment.add_exception(e)
                raise
            finally:
                xray_recorder.end_subsegment()
        else:
            # No-op context manager when tracing is disabled
            yield None
    
    def trace_function(self, name: Optional[str] = None):
        """
        Decorator for tracing functions.
        
        Args:
            name: Optional custom name for the trace
        """
        def decorator(func):
            def wrapper(*args, **kwargs):
                trace_name = name or f"{func.__module__}.{func.__name__}"
                with self.trace_subsegment(trace_name):
                    return func(*args, **kwargs)
            return wrapper
        return decorator
    
    def add_annotation(self, key: str, value: Union[str, int, float, bool]):
        """
        Add annotation to current trace.
        
        Args:
            key: Annotation key
            value: Annotation value
        """
        if self.enabled and XRAY_AVAILABLE:
            try:
                xray_recorder.put_annotation(key, value)
            except Exception as e:
                self.logger.warning(f"Failed to add X-Ray annotation: {e}")
    
    def add_metadata(self, namespace: str, data: Dict[str, Any]):
        """
        Add metadata to current trace.
        
        Args:
            namespace: Metadata namespace
            data: Metadata dictionary
        """
        if self.enabled and XRAY_AVAILABLE:
            try:
                xray_recorder.put_metadata(namespace, data)
            except Exception as e:
                self.logger.warning(f"Failed to add X-Ray metadata: {e}")


class MonitoringManager:
    """Central monitoring manager that coordinates all monitoring components."""
    
    def __init__(self, component_name: str, 
                 enable_metrics: bool = True,
                 enable_xray: bool = True,
                 log_level: str = "INFO"):
        """
        Initialize monitoring manager.
        
        Args:
            component_name: Name of the component being monitored
            enable_metrics: Whether to enable CloudWatch metrics
            enable_xray: Whether to enable X-Ray tracing
            log_level: Logging level
        """
        self.component_name = component_name
        
        # Initialize components
        self.metrics = CloudWatchMetricsClient() if enable_metrics else None
        self.logger = StructuredLogger(component_name, log_level)
        self.tracer = XRayTracer(enable_xray)
        
        # Performance tracking
        self._active_operations: Dict[str, PerformanceMetrics] = {}
        
        self.logger.info("Monitoring manager initialized",
                        component=component_name,
                        metrics_enabled=enable_metrics,
                        xray_enabled=enable_xray)
    
    @contextmanager
    def track_operation(self, operation_name: str, 
                       metadata: Optional[Dict[str, Any]] = None):
        """
        Context manager for tracking operation performance.
        
        Args:
            operation_name: Name of the operation
            metadata: Optional metadata
        """
        perf_metrics = PerformanceMetrics(
            operation_name=operation_name,
            start_time=time.time(),
            metadata=metadata or {}
        )
        
        operation_id = f"{operation_name}_{id(perf_metrics)}"
        self._active_operations[operation_id] = perf_metrics
        
        self.logger.info(f"Started operation: {operation_name}",
                        operation=operation_name,
                        operation_id=operation_id,
                        **perf_metrics.metadata)
        
        try:
            with self.tracer.trace_subsegment(operation_name, metadata):
                yield perf_metrics
            
            # Mark as successful
            perf_metrics.finish(success=True)
            
        except Exception as e:
            # Mark as failed
            perf_metrics.finish(success=False, error_message=str(e))
            
            # Log error
            self.logger.error(f"Operation failed: {operation_name}",
                            operation=operation_name,
                            operation_id=operation_id,
                            error=str(e),
                            **perf_metrics.metadata)
            
            # Record error metrics
            if self.metrics:
                self.metrics.put_error_metrics(
                    error_type=type(e).__name__,
                    operation=operation_name,
                    component=self.component_name
                )
            
            raise
        
        finally:
            # Record performance metrics
            if self.metrics:
                self.metrics.put_performance_metrics(perf_metrics)
            
            # Log completion
            self.logger.log_performance(perf_metrics)
            
            # Clean up
            self._active_operations.pop(operation_id, None)
    
    def record_sync_progress(self, completed: int, total: int, failed: int = 0,
                           phase: SyncPhase = SyncPhase.BOTTLE_DOWNLOAD):
        """
        Record sync progress metrics and logs.
        
        Args:
            completed: Number of completed items
            total: Total number of items
            failed: Number of failed items
            phase: Current sync phase
        """
        if self.metrics:
            self.metrics.put_sync_progress_metrics(completed, total, failed, phase)
        
        self.logger.log_sync_event("progress_update", {
            'completed': completed,
            'total': total,
            'failed': failed,
            'phase': phase.value,
            'progress_percentage': (completed / total * 100) if total > 0 else 0
        })
        
        self.tracer.add_annotation('sync_progress', f"{completed}/{total}")
    
    def record_bottle_download(self, bottle_name: str, size_bytes: int,
                             duration_seconds: float, success: bool):
        """
        Record bottle download metrics.
        
        Args:
            bottle_name: Name of the bottle
            size_bytes: Size in bytes
            duration_seconds: Download duration
            success: Whether download succeeded
        """
        if self.metrics:
            self.metrics.put_download_metrics(
                bottle_name, size_bytes, duration_seconds, success
            )
        
        self.logger.log_sync_event("bottle_download", {
            'bottle_name': bottle_name,
            'size_bytes': size_bytes,
            'duration_seconds': duration_seconds,
            'success': success,
            'throughput_mbps': (size_bytes / (1024 * 1024)) / duration_seconds if success and duration_seconds > 0 else 0
        })
    
    def flush_metrics(self):
        """Flush any buffered metrics."""
        if self.metrics:
            self.metrics.flush_metrics()
    
    def get_health_status(self) -> Dict[str, Any]:
        """
        Get current health status of the monitoring system.
        
        Returns:
            Health status dictionary
        """
        return {
            'component': self.component_name,
            'metrics_enabled': self.metrics is not None,
            'xray_enabled': self.tracer.enabled,
            'active_operations': len(self._active_operations),
            'timestamp': datetime.now(timezone.utc).isoformat()
        }


def create_monitoring_manager(component_name: str) -> MonitoringManager:
    """
    Factory function to create a monitoring manager with environment-based configuration.
    
    Args:
        component_name: Name of the component
        
    Returns:
        Configured MonitoringManager instance
    """
    enable_metrics = os.environ.get('ENABLE_CLOUDWATCH_METRICS', 'true').lower() == 'true'
    enable_xray = os.environ.get('ENABLE_XRAY_TRACING', 'true').lower() == 'true'
    log_level = os.environ.get('LOG_LEVEL', 'INFO').upper()
    
    return MonitoringManager(
        component_name=component_name,
        enable_metrics=enable_metrics,
        enable_xray=enable_xray,
        log_level=log_level
    )