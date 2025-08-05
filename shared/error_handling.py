"""
Error handling and recovery mechanisms for the Homebrew Bottles Sync System.

This module provides comprehensive error handling, retry logic with exponential backoff,
partial sync recovery, and CloudWatch metrics integration.
"""

import time
import logging
import traceback
import asyncio
from typing import Any, Callable, Dict, List, Optional, Tuple, Union
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import boto3
from botocore.exceptions import ClientError, BotoCoreError
import json


class ErrorType(Enum):
    """Types of errors that can occur during sync operations."""
    NETWORK_ERROR = "network_error"
    S3_ERROR = "s3_error"
    VALIDATION_ERROR = "validation_error"
    HASH_CORRUPTION = "hash_corruption"
    RESOURCE_EXHAUSTION = "resource_exhaustion"
    TIMEOUT_ERROR = "timeout_error"
    AUTHENTICATION_ERROR = "authentication_error"
    UNKNOWN_ERROR = "unknown_error"


class RecoveryAction(Enum):
    """Recovery actions that can be taken for different error types."""
    RETRY = "retry"
    SKIP = "skip"
    ABORT = "abort"
    REBUILD = "rebuild"
    FALLBACK = "fallback"


@dataclass
class ErrorContext:
    """Context information for an error occurrence."""
    error_type: ErrorType
    error_message: str
    operation: str
    resource_id: Optional[str] = None
    attempt_number: int = 1
    timestamp: Optional[str] = None
    stack_trace: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Set timestamp if not provided."""
        if self.timestamp is None:
            self.timestamp = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')


@dataclass
class RetryConfig:
    """Configuration for retry logic."""
    max_attempts: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    exponential_base: float = 2.0
    jitter: bool = True
    backoff_multiplier: float = 1.0


@dataclass
class RecoveryState:
    """State information for partial sync recovery."""
    sync_id: str
    start_time: str
    last_successful_bottle: Optional[str] = None
    completed_bottles: List[str] = field(default_factory=list)
    failed_bottles: List[str] = field(default_factory=list)
    skipped_bottles: List[str] = field(default_factory=list)
    total_bottles: int = 0
    recovery_checkpoint: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert recovery state to dictionary for serialization."""
        return {
            'sync_id': self.sync_id,
            'start_time': self.start_time,
            'last_successful_bottle': self.last_successful_bottle,
            'completed_bottles': self.completed_bottles,
            'failed_bottles': self.failed_bottles,
            'skipped_bottles': self.skipped_bottles,
            'total_bottles': self.total_bottles,
            'recovery_checkpoint': self.recovery_checkpoint,
            'metadata': self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'RecoveryState':
        """Create RecoveryState from dictionary data."""
        return cls(
            sync_id=data['sync_id'],
            start_time=data['start_time'],
            last_successful_bottle=data.get('last_successful_bottle'),
            completed_bottles=data.get('completed_bottles', []),
            failed_bottles=data.get('failed_bottles', []),
            skipped_bottles=data.get('skipped_bottles', []),
            total_bottles=data.get('total_bottles', 0),
            recovery_checkpoint=data.get('recovery_checkpoint'),
            metadata=data.get('metadata', {})
        )


class CloudWatchMetrics:
    """CloudWatch metrics client for sync operations."""
    
    def __init__(self, namespace: str = "HomebrewSync", region: str = "us-east-1"):
        """
        Initialize CloudWatch metrics client.
        
        Args:
            namespace: CloudWatch namespace for metrics
            region: AWS region
        """
        self.namespace = namespace
        self.region = region
        self._cloudwatch = None
        self.logger = logging.getLogger(__name__)
    
    @property
    def cloudwatch(self):
        """Lazy initialization of CloudWatch client."""
        if self._cloudwatch is None:
            self._cloudwatch = boto3.client('cloudwatch', region_name=self.region)
        return self._cloudwatch
    
    def put_metric(self, metric_name: str, value: float, unit: str = 'Count', 
                   dimensions: Optional[Dict[str, str]] = None) -> bool:
        """
        Put a single metric to CloudWatch.
        
        Args:
            metric_name: Name of the metric
            value: Metric value
            unit: Metric unit
            dimensions: Optional dimensions for the metric
            
        Returns:
            True if metric was sent successfully, False otherwise
        """
        try:
            metric_data = {
                'MetricName': metric_name,
                'Value': value,
                'Unit': unit,
                'Timestamp': datetime.now(timezone.utc)
            }
            
            if dimensions:
                metric_data['Dimensions'] = [
                    {'Name': k, 'Value': v} for k, v in dimensions.items()
                ]
            
            self.cloudwatch.put_metric_data(
                Namespace=self.namespace,
                MetricData=[metric_data]
            )
            
            self.logger.debug(f"Sent metric {metric_name}={value} to CloudWatch")
            return True
            
        except (ClientError, BotoCoreError) as e:
            self.logger.error(f"Failed to send metric {metric_name} to CloudWatch: {e}")
            return False
    
    def put_error_metric(self, error_context: ErrorContext) -> bool:
        """
        Put error metrics to CloudWatch.
        
        Args:
            error_context: Error context information
            
        Returns:
            True if metrics were sent successfully, False otherwise
        """
        dimensions = {
            'ErrorType': error_context.error_type.value,
            'Operation': error_context.operation
        }
        
        if error_context.resource_id:
            dimensions['ResourceId'] = error_context.resource_id
        
        return self.put_metric('Errors', 1, 'Count', dimensions)
    
    def put_retry_metric(self, operation: str, attempt_number: int, success: bool) -> bool:
        """
        Put retry metrics to CloudWatch.
        
        Args:
            operation: Operation being retried
            attempt_number: Current attempt number
            success: Whether the retry was successful
            
        Returns:
            True if metrics were sent successfully, False otherwise
        """
        dimensions = {
            'Operation': operation,
            'AttemptNumber': str(attempt_number),
            'Success': str(success)
        }
        
        return self.put_metric('Retries', 1, 'Count', dimensions)
    
    def put_recovery_metric(self, recovery_type: str, success: bool) -> bool:
        """
        Put recovery metrics to CloudWatch.
        
        Args:
            recovery_type: Type of recovery performed
            success: Whether the recovery was successful
            
        Returns:
            True if metrics were sent successfully, False otherwise
        """
        dimensions = {
            'RecoveryType': recovery_type,
            'Success': str(success)
        }
        
        return self.put_metric('Recovery', 1, 'Count', dimensions)


class RetryHandler:
    """Handles retry logic with exponential backoff and jitter."""
    
    def __init__(self, config: RetryConfig, metrics: Optional[CloudWatchMetrics] = None):
        """
        Initialize retry handler.
        
        Args:
            config: Retry configuration
            metrics: Optional CloudWatch metrics client
        """
        self.config = config
        self.metrics = metrics
        self.logger = logging.getLogger(__name__)
    
    def calculate_delay(self, attempt: int) -> float:
        """
        Calculate delay for the given attempt number.
        
        Args:
            attempt: Current attempt number (1-based)
            
        Returns:
            Delay in seconds
        """
        if attempt <= 1:
            return 0
        
        # Exponential backoff
        delay = self.config.base_delay * (self.config.exponential_base ** (attempt - 2))
        delay *= self.config.backoff_multiplier
        
        # Apply maximum delay limit
        delay = min(delay, self.config.max_delay)
        
        # Add jitter to prevent thundering herd
        if self.config.jitter:
            import random
            jitter_range = delay * 0.1  # 10% jitter
            delay += random.uniform(-jitter_range, jitter_range)
        
        return max(0, delay)
    
    def should_retry(self, error: Exception, attempt: int) -> bool:
        """
        Determine if an operation should be retried based on error type and attempt count.
        
        Args:
            error: Exception that occurred
            attempt: Current attempt number (1-based)
            
        Returns:
            True if operation should be retried, False otherwise
        """
        if attempt >= self.config.max_attempts:
            return False
        
        # Determine if error is retryable
        if isinstance(error, (ConnectionError, TimeoutError)):
            return True
        
        if isinstance(error, ClientError):
            error_code = error.response.get('Error', {}).get('Code', '')
            # Retry on throttling and temporary service errors
            retryable_codes = [
                'Throttling', 'ThrottlingException', 'RequestLimitExceeded',
                'ServiceUnavailable', 'InternalError', 'SlowDown'
            ]
            return error_code in retryable_codes
        
        # Don't retry validation errors or authentication errors
        if isinstance(error, (ValueError, KeyError, PermissionError)):
            return False
        
        # Retry other exceptions by default
        return True
    
    def retry_sync(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute a function with retry logic (synchronous).
        
        Args:
            func: Function to execute
            *args: Function arguments
            **kwargs: Function keyword arguments
            
        Returns:
            Function result
            
        Raises:
            Last exception if all retries failed
        """
        last_exception = None
        operation_name = getattr(func, '__name__', 'unknown_operation')
        
        for attempt in range(1, self.config.max_attempts + 1):
            try:
                self.logger.debug(f"Executing {operation_name} (attempt {attempt}/{self.config.max_attempts})")
                
                result = func(*args, **kwargs)
                
                # Send success metric if this was a retry
                if attempt > 1 and self.metrics:
                    self.metrics.put_retry_metric(operation_name, attempt, True)
                
                return result
                
            except Exception as e:
                last_exception = e
                
                # Send retry metric
                if self.metrics:
                    self.metrics.put_retry_metric(operation_name, attempt, False)
                
                if not self.should_retry(e, attempt):
                    self.logger.error(f"{operation_name} failed on attempt {attempt} (not retryable): {e}")
                    break
                
                if attempt < self.config.max_attempts:
                    delay = self.calculate_delay(attempt)
                    self.logger.warning(f"{operation_name} failed on attempt {attempt}, retrying in {delay:.1f}s: {e}")
                    time.sleep(delay)
                else:
                    self.logger.error(f"{operation_name} failed on final attempt {attempt}: {e}")
        
        # All retries failed
        raise last_exception
    
    async def retry_async(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute an async function with retry logic.
        
        Args:
            func: Async function to execute
            *args: Function arguments
            **kwargs: Function keyword arguments
            
        Returns:
            Function result
            
        Raises:
            Last exception if all retries failed
        """
        last_exception = None
        operation_name = getattr(func, '__name__', 'unknown_operation')
        
        for attempt in range(1, self.config.max_attempts + 1):
            try:
                self.logger.debug(f"Executing {operation_name} (attempt {attempt}/{self.config.max_attempts})")
                
                result = await func(*args, **kwargs)
                
                # Send success metric if this was a retry
                if attempt > 1 and self.metrics:
                    self.metrics.put_retry_metric(operation_name, attempt, True)
                
                return result
                
            except Exception as e:
                last_exception = e
                
                # Send retry metric
                if self.metrics:
                    self.metrics.put_retry_metric(operation_name, attempt, False)
                
                if not self.should_retry(e, attempt):
                    self.logger.error(f"{operation_name} failed on attempt {attempt} (not retryable): {e}")
                    break
                
                if attempt < self.config.max_attempts:
                    delay = self.calculate_delay(attempt)
                    self.logger.warning(f"{operation_name} failed on attempt {attempt}, retrying in {delay:.1f}s: {e}")
                    await asyncio.sleep(delay)
                else:
                    self.logger.error(f"{operation_name} failed on final attempt {attempt}: {e}")
        
        # All retries failed
        raise last_exception


class ErrorClassifier:
    """Classifies errors and determines appropriate recovery actions."""
    
    def __init__(self):
        """Initialize error classifier."""
        self.logger = logging.getLogger(__name__)
    
    def classify_error(self, error: Exception, operation: str) -> ErrorContext:
        """
        Classify an error and create error context.
        
        Args:
            error: Exception that occurred
            operation: Operation that failed
            
        Returns:
            ErrorContext with classified error information
        """
        error_type = self._determine_error_type(error)
        
        return ErrorContext(
            error_type=error_type,
            error_message=str(error),
            operation=operation,
            stack_trace=traceback.format_exc(),
            metadata={
                'exception_type': type(error).__name__,
                'exception_module': type(error).__module__
            }
        )
    
    def _determine_error_type(self, error: Exception) -> ErrorType:
        """
        Determine the error type based on the exception.
        
        Args:
            error: Exception to classify
            
        Returns:
            ErrorType enum value
        """
        if isinstance(error, (ConnectionError, TimeoutError)):
            return ErrorType.NETWORK_ERROR
        
        if isinstance(error, ClientError):
            error_code = error.response.get('Error', {}).get('Code', '')
            
            if error_code in ['NoSuchBucket', 'NoSuchKey', 'AccessDenied']:
                return ErrorType.S3_ERROR
            elif error_code in ['InvalidRequest', 'MalformedPolicy']:
                return ErrorType.VALIDATION_ERROR
            elif error_code in ['Throttling', 'RequestLimitExceeded']:
                return ErrorType.RESOURCE_EXHAUSTION
            elif error_code in ['SignatureDoesNotMatch', 'InvalidAccessKeyId']:
                return ErrorType.AUTHENTICATION_ERROR
            else:
                return ErrorType.S3_ERROR
        
        if isinstance(error, (ValueError, KeyError)):
            return ErrorType.VALIDATION_ERROR
        
        if isinstance(error, PermissionError):
            return ErrorType.AUTHENTICATION_ERROR
        
        if "timeout" in str(error).lower():
            return ErrorType.TIMEOUT_ERROR
        
        if "hash" in str(error).lower() or "corruption" in str(error).lower():
            return ErrorType.HASH_CORRUPTION
        
        return ErrorType.UNKNOWN_ERROR
    
    def determine_recovery_action(self, error_context: ErrorContext) -> RecoveryAction:
        """
        Determine the appropriate recovery action for an error.
        
        Args:
            error_context: Error context information
            
        Returns:
            RecoveryAction enum value
        """
        error_type = error_context.error_type
        attempt = error_context.attempt_number
        
        # Network errors: retry with backoff
        if error_type == ErrorType.NETWORK_ERROR:
            return RecoveryAction.RETRY if attempt < 5 else RecoveryAction.SKIP
        
        # S3 errors: retry for temporary issues, skip for permanent ones
        if error_type == ErrorType.S3_ERROR:
            if "NoSuchKey" in error_context.error_message:
                return RecoveryAction.SKIP
            return RecoveryAction.RETRY if attempt < 3 else RecoveryAction.SKIP
        
        # Hash corruption: rebuild hash file
        if error_type == ErrorType.HASH_CORRUPTION:
            return RecoveryAction.REBUILD
        
        # Resource exhaustion: retry with longer delays
        if error_type == ErrorType.RESOURCE_EXHAUSTION:
            return RecoveryAction.RETRY if attempt < 10 else RecoveryAction.ABORT
        
        # Validation errors: skip (not recoverable)
        if error_type == ErrorType.VALIDATION_ERROR:
            return RecoveryAction.SKIP
        
        # Authentication errors: abort (need manual intervention)
        if error_type == ErrorType.AUTHENTICATION_ERROR:
            return RecoveryAction.ABORT
        
        # Timeout errors: retry with exponential backoff
        if error_type == ErrorType.TIMEOUT_ERROR:
            return RecoveryAction.RETRY if attempt < 3 else RecoveryAction.SKIP
        
        # Unknown errors: retry once, then skip
        return RecoveryAction.RETRY if attempt < 2 else RecoveryAction.SKIP


class PartialSyncRecovery:
    """Handles partial sync recovery to resume from last successful bottle."""
    
    RECOVERY_STATE_KEY = "sync_recovery_state.json"
    
    def __init__(self, s3_service, metrics: Optional[CloudWatchMetrics] = None):
        """
        Initialize partial sync recovery handler.
        
        Args:
            s3_service: S3 service for storing recovery state
            metrics: Optional CloudWatch metrics client
        """
        self.s3_service = s3_service
        self.metrics = metrics
        self.logger = logging.getLogger(__name__)
    
    def save_recovery_state(self, state: RecoveryState) -> bool:
        """
        Save recovery state to S3.
        
        Args:
            state: Recovery state to save
            
        Returns:
            True if saved successfully, False otherwise
        """
        try:
            success = self.s3_service.upload_json(
                state.to_dict(),
                self.RECOVERY_STATE_KEY,
                metadata={'sync_id': state.sync_id}
            )
            
            if success:
                self.logger.info(f"Saved recovery state for sync {state.sync_id}")
            else:
                self.logger.error(f"Failed to save recovery state for sync {state.sync_id}")
            
            return success
            
        except Exception as e:
            self.logger.error(f"Error saving recovery state: {e}")
            return False
    
    def load_recovery_state(self, sync_id: Optional[str] = None) -> Optional[RecoveryState]:
        """
        Load recovery state from S3.
        
        Args:
            sync_id: Optional sync ID to validate against
            
        Returns:
            RecoveryState if found and valid, None otherwise
        """
        try:
            data = self.s3_service.download_json(self.RECOVERY_STATE_KEY)
            if not data:
                return None
            
            state = RecoveryState.from_dict(data)
            
            # Validate sync ID if provided
            if sync_id and state.sync_id != sync_id:
                self.logger.warning(f"Recovery state sync ID mismatch: expected {sync_id}, got {state.sync_id}")
                return None
            
            self.logger.info(f"Loaded recovery state for sync {state.sync_id}")
            return state
            
        except Exception as e:
            self.logger.error(f"Error loading recovery state: {e}")
            return None
    
    def clear_recovery_state(self) -> bool:
        """
        Clear recovery state from S3.
        
        Returns:
            True if cleared successfully, False otherwise
        """
        try:
            success = self.s3_service.delete_object(self.RECOVERY_STATE_KEY)
            if success:
                self.logger.info("Cleared recovery state")
            return success
            
        except Exception as e:
            self.logger.error(f"Error clearing recovery state: {e}")
            return False
    
    def should_resume_sync(self, current_sync_id: str) -> Tuple[bool, Optional[RecoveryState]]:
        """
        Determine if a sync should be resumed from a previous state.
        
        Args:
            current_sync_id: Current sync ID
            
        Returns:
            Tuple of (should_resume, recovery_state)
        """
        recovery_state = self.load_recovery_state()
        
        if not recovery_state:
            return False, None
        
        # Check if this is the same sync
        if recovery_state.sync_id == current_sync_id:
            return True, recovery_state
        
        # Check if previous sync is recent (within 24 hours)
        try:
            start_time = datetime.fromisoformat(recovery_state.start_time.replace('Z', '+00:00'))
            time_diff = datetime.now(timezone.utc) - start_time
            
            if time_diff.total_seconds() < 24 * 3600:  # 24 hours
                self.logger.info(f"Found recent incomplete sync {recovery_state.sync_id}, considering resume")
                return True, recovery_state
            else:
                self.logger.info(f"Found old incomplete sync {recovery_state.sync_id}, starting fresh")
                self.clear_recovery_state()
                return False, None
                
        except Exception as e:
            self.logger.warning(f"Error parsing recovery state timestamp: {e}")
            return False, None
    
    def update_progress(self, state: RecoveryState, bottle_id: str, status: str) -> None:
        """
        Update progress in recovery state.
        
        Args:
            state: Recovery state to update
            bottle_id: Bottle identifier
            status: Status ('completed', 'failed', 'skipped')
        """
        if status == 'completed':
            if bottle_id not in state.completed_bottles:
                state.completed_bottles.append(bottle_id)
            state.last_successful_bottle = bottle_id
        elif status == 'failed':
            if bottle_id not in state.failed_bottles:
                state.failed_bottles.append(bottle_id)
        elif status == 'skipped':
            if bottle_id not in state.skipped_bottles:
                state.skipped_bottles.append(bottle_id)
        
        # Update checkpoint every 10 bottles
        if len(state.completed_bottles) % 10 == 0:
            state.recovery_checkpoint = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
            self.save_recovery_state(state)


def create_structured_logger(name: str, level: str = "INFO") -> logging.Logger:
    """
    Create a structured logger with JSON formatting for CloudWatch.
    
    Args:
        name: Logger name
        level: Log level
        
    Returns:
        Configured logger
    """
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level.upper()))
    
    # Remove existing handlers
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # Create console handler with JSON formatter
    handler = logging.StreamHandler()
    
    class JSONFormatter(logging.Formatter):
        """JSON formatter for structured logging."""
        
        def format(self, record):
            log_entry = {
                'timestamp': datetime.fromtimestamp(record.created, timezone.utc).isoformat().replace('+00:00', 'Z'),
                'level': record.levelname,
                'logger': record.name,
                'message': record.getMessage(),
                'module': record.module,
                'function': record.funcName,
                'line': record.lineno
            }
            
            # Add exception info if present
            if record.exc_info:
                log_entry['exception'] = self.formatException(record.exc_info)
            
            # Add extra fields
            for key, value in record.__dict__.items():
                if key not in ['name', 'msg', 'args', 'levelname', 'levelno', 'pathname', 
                              'filename', 'module', 'lineno', 'funcName', 'created', 
                              'msecs', 'relativeCreated', 'thread', 'threadName', 
                              'processName', 'process', 'getMessage', 'exc_info', 'exc_text', 'stack_info']:
                    log_entry[key] = value
            
            return json.dumps(log_entry)
    
    handler.setFormatter(JSONFormatter())
    logger.addHandler(handler)
    
    return logger