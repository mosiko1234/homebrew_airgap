"""
Lambda sync worker for downloading bottles under 20GB threshold.

This module implements the Lambda function that handles small to medium-sized
bottle downloads with SHA validation, S3 upload, and hash file updates.
"""

import json
import logging
import os
import tempfile
import hashlib
import requests
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple
from dataclasses import asdict

# Import shared modules
from shared.models import Formula, BottleInfo, SyncConfig, HashFileManager
from shared.s3_service import S3Service
from shared.homebrew_api import HomebrewAPIClient
from shared.notification_service import NotificationService, NotificationData, NotificationType
from shared.monitoring import create_monitoring_manager, SyncPhase


# Initialize monitoring
monitoring = create_monitoring_manager("lambda_sync_worker")


class LambdaSyncWorker:
    """Lambda sync worker for downloading bottles under size threshold."""
    
    def __init__(self):
        """Initialize the sync worker with AWS services."""
        self.s3_bucket = os.environ.get('S3_BUCKET_NAME')
        self.webhook_secret_name = os.environ.get('SLACK_WEBHOOK_SECRET_NAME')
        self.aws_region = os.environ.get('AWS_REGION', 'us-east-1')
        
        if not self.s3_bucket:
            raise ValueError("S3_BUCKET_NAME environment variable is required")
        
        # Initialize services
        self.s3_service = S3Service(self.s3_bucket, self.aws_region)
        self.notification_service = NotificationService(
            webhook_secret_name=self.webhook_secret_name,
            aws_region=self.aws_region
        )
        self.hash_manager = HashFileManager(self.s3_service)
        
        # Sync statistics
        self.stats = {
            'bottles_downloaded': 0,
            'bottles_skipped': 0,
            'total_size_downloaded': 0,
            'failed_downloads': 0,
            'start_time': None,
            'end_time': None
        }
    
    def download_bottle(self, bottle_url: str, local_path: str, expected_sha256: str, bottle_name: str = "") -> Tuple[bool, int, float]:
        """
        Download a bottle file and validate its SHA256.
        
        Args:
            bottle_url: URL to download the bottle from
            local_path: Local path to save the bottle
            expected_sha256: Expected SHA256 hash for validation
            bottle_name: Name of the bottle for metrics
            
        Returns:
            Tuple of (success, size_bytes, duration_seconds)
        """
        start_time = time.time()
        
        with monitoring.track_operation("bottle_download", {"bottle_name": bottle_name, "url": bottle_url}):
            try:
                monitoring.logger.info(f"Downloading bottle from {bottle_url}",
                                     bottle_name=bottle_name, url=bottle_url)
                
                # Download with streaming to handle large files
                response = requests.get(bottle_url, stream=True, timeout=300)
                response.raise_for_status()
                
                # Calculate SHA256 while downloading
                sha256_hash = hashlib.sha256()
                total_size = 0
                
                with open(local_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                            sha256_hash.update(chunk)
                            total_size += len(chunk)
                
                # Validate SHA256
                calculated_sha256 = sha256_hash.hexdigest()
                if calculated_sha256 != expected_sha256:
                    monitoring.logger.error(f"SHA256 mismatch for {bottle_url}",
                                          bottle_name=bottle_name,
                                          expected_sha256=expected_sha256,
                                          calculated_sha256=calculated_sha256)
                    return False, total_size, time.time() - start_time
                
                duration = time.time() - start_time
                monitoring.logger.info(f"Successfully downloaded and validated bottle ({total_size} bytes)",
                                     bottle_name=bottle_name, size_bytes=total_size, duration=duration)
                
                # Record download metrics
                monitoring.record_bottle_download(bottle_name, total_size, duration, True)
                
                return True, total_size, duration
                
            except requests.exceptions.RequestException as e:
                duration = time.time() - start_time
                monitoring.logger.error(f"Failed to download bottle from {bottle_url}",
                                      bottle_name=bottle_name, error=str(e), error_type="network_error")
                monitoring.record_bottle_download(bottle_name, 0, duration, False)
                return False, 0, duration
            except Exception as e:
                duration = time.time() - start_time
                monitoring.logger.error(f"Unexpected error downloading bottle",
                                      bottle_name=bottle_name, error=str(e), error_type="unknown_error")
                monitoring.record_bottle_download(bottle_name, 0, duration, False)
                return False, 0, duration
    
    def upload_bottle_to_s3(self, local_path: str, formula: Formula, platform: str, date_folder: str) -> bool:
        """
        Upload a bottle file to S3 with date-based folder structure.
        
        Args:
            local_path: Local path of the bottle file
            formula: Formula object
            platform: Platform name (e.g., arm64_sonoma)
            date_folder: Date folder name (YYYY-MM-DD)
            
        Returns:
            True if upload successful, False otherwise
        """
        try:
            # Generate S3 key with date-based structure
            filename = f"{formula.name}-{formula.version}.{platform}.bottle.tar.gz"
            s3_key = f"{date_folder}/{filename}"
            
            # Upload with metadata
            metadata = {
                'formula-name': formula.name,
                'formula-version': formula.version,
                'platform': platform,
                'download-date': date_folder
            }
            
            success = self.s3_service.upload_file(local_path, s3_key, metadata)
            if success:
                monitoring.logger.info(f"Successfully uploaded bottle to s3://{self.s3_bucket}/{s3_key}",
                                     s3_key=s3_key, s3_bucket=self.s3_bucket)
            
            return success
            
        except Exception as e:
            monitoring.logger.error(f"Failed to upload bottle to S3: {e}", error=str(e))
            return False
    
    def process_formula(self, formula: Formula, target_platforms: List[str], date_folder: str) -> Dict[str, bool]:
        """
        Process a single formula by downloading its bottles for target platforms.
        
        Args:
            formula: Formula object to process
            target_platforms: List of target platform names
            date_folder: Date folder name (YYYY-MM-DD)
            
        Returns:
            Dictionary mapping platform names to success status
        """
        results = {}
        
        with monitoring.track_operation("process_formula", {"formula_name": formula.name, "version": formula.version}):
            for platform in target_platforms:
                if platform not in formula.bottles:
                    monitoring.logger.debug(f"Formula {formula.name} has no bottle for platform {platform}",
                                          formula_name=formula.name, platform=platform)
                    continue
                
                bottle = formula.bottles[platform]
                bottle_name = f"{formula.name}-{formula.version}-{platform}"
                
                # Check if bottle already exists in hash file
                if self.hash_manager.has_bottle(formula, platform, bottle):
                    monitoring.logger.info(f"Skipping {formula.name}-{formula.version} for {platform} (already downloaded)",
                                         formula_name=formula.name, platform=platform, status="skipped")
                    self.stats['bottles_skipped'] += 1
                    results[platform] = True
                    continue
                
                # Download bottle to temporary file
                with tempfile.NamedTemporaryFile(delete=False, suffix='.bottle.tar.gz') as temp_file:
                    temp_path = temp_file.name
                
                try:
                    # Download and validate
                    success, size_bytes, duration = self.download_bottle(bottle.url, temp_path, bottle.sha256, bottle_name)
                    if not success:
                        monitoring.logger.error(f"Failed to download bottle for {formula.name}-{formula.version} ({platform})",
                                              formula_name=formula.name, platform=platform, status="download_failed")
                        self.stats['failed_downloads'] += 1
                        results[platform] = False
                        continue
                    
                    # Upload to S3
                    with monitoring.track_operation("s3_upload", {"bottle_name": bottle_name}):
                        if not self.upload_bottle_to_s3(temp_path, formula, platform, date_folder):
                            monitoring.logger.error(f"Failed to upload bottle for {formula.name}-{formula.version} ({platform})",
                                                  formula_name=formula.name, platform=platform, status="upload_failed")
                            self.stats['failed_downloads'] += 1
                            results[platform] = False
                            continue
                    
                    # Add to hash file
                    with monitoring.track_operation("hash_update", {"bottle_name": bottle_name}):
                        self.hash_manager.add_bottle(formula, platform, bottle, date_folder)
                    
                    # Update statistics
                    self.stats['bottles_downloaded'] += 1
                    self.stats['total_size_downloaded'] += bottle.size
                    results[platform] = True
                    
                    monitoring.logger.info(f"Successfully processed {formula.name}-{formula.version} for {platform}",
                                         formula_name=formula.name, platform=platform, status="completed",
                                         size_bytes=size_bytes, duration=duration)
                    
                finally:
                    # Clean up temporary file
                    try:
                        os.unlink(temp_path)
                    except OSError:
                        pass
        
        return results
    
    def sync_formulas(self, formulas: List[Formula], config: SyncConfig) -> bool:
        """
        Sync all formulas by downloading their bottles.
        
        Args:
            formulas: List of Formula objects to sync
            config: Sync configuration
            
        Returns:
            True if sync completed successfully, False if there were failures
        """
        with monitoring.track_operation("sync_formulas", {"formula_count": len(formulas)}):
            self.stats['start_time'] = datetime.now(timezone.utc)
            date_folder = self.stats['start_time'].strftime('%Y-%m-%d')
            
            monitoring.logger.info(f"Starting sync of {len(formulas)} formulas for date {date_folder}",
                                 formula_count=len(formulas), date_folder=date_folder)
            
            # Add X-Ray annotations
            monitoring.tracer.add_annotation("formula_count", len(formulas))
            monitoring.tracer.add_annotation("sync_date", date_folder)
            
            # Load existing hash file with external support
            with monitoring.track_operation("hash_file_loading"):
                # Try external hash file first if configured
                external_loaded = False
                if config.external_hash_file_url or config.external_hash_file_s3_key:
                    monitoring.logger.info("Attempting to load external hash file")
                    if self.hash_manager.load_external_hash_file(config):
                        external_loaded = True
                        monitoring.logger.info(f"Loaded external hash file with {len(self.hash_manager.bottles)} bottles")
                    else:
                        monitoring.logger.warning("Failed to load external hash file, will try default hash file")
                
                # Fall back to default hash file if external not loaded
                if not external_loaded:
                    hash_loaded = self.hash_manager.load_from_s3()
                    if hash_loaded:
                        monitoring.logger.info("Loaded existing hash file from S3", hash_file_loaded=True)
                    else:
                        monitoring.logger.info("No existing hash file found, starting fresh", hash_file_loaded=False)
                
                monitoring.record_sync_progress(0, len(formulas), 0, SyncPhase.HASH_LOADING)
            
            # Process each formula
            total_formulas = len(formulas)
            processed_formulas = 0
            
            for formula in formulas:
                try:
                    monitoring.logger.info(f"Processing formula {formula.name}-{formula.version} "
                                         f"({processed_formulas + 1}/{total_formulas})",
                                         formula_name=formula.name, formula_version=formula.version,
                                         progress=f"{processed_formulas + 1}/{total_formulas}")
                    
                    results = self.process_formula(formula, config.target_platforms, date_folder)
                    processed_formulas += 1
                    
                    # Update progress metrics
                    monitoring.record_sync_progress(
                        self.stats['bottles_downloaded'], 
                        total_formulas * len(config.target_platforms),  # Approximate total bottles
                        self.stats['failed_downloads'],
                        SyncPhase.BOTTLE_DOWNLOAD
                    )
                    
                    # Log results for this formula
                    successful_platforms = [p for p, success in results.items() if success]
                    if successful_platforms:
                        monitoring.logger.info(f"Successfully processed {formula.name} for platforms: {successful_platforms}",
                                             formula_name=formula.name, successful_platforms=successful_platforms)
                    
                except Exception as e:
                    monitoring.logger.error(f"Unexpected error processing formula {formula.name}",
                                          formula_name=formula.name, error=str(e), error_type=type(e).__name__)
                    self.stats['failed_downloads'] += 1
                    continue
            
            # Save updated hash file
            with monitoring.track_operation("hash_file_saving"):
                if not self.hash_manager.save_to_s3_atomic():
                    monitoring.logger.error("Failed to save updated hash file to S3")
                    return False
                
                monitoring.record_sync_progress(
                    self.stats['bottles_downloaded'], 
                    self.stats['bottles_downloaded'] + self.stats['failed_downloads'],
                    self.stats['failed_downloads'],
                    SyncPhase.HASH_UPDATE
                )
            
            self.stats['end_time'] = datetime.now(timezone.utc)
            duration = (self.stats['end_time'] - self.stats['start_time']).total_seconds()
            
            # Final metrics
            monitoring.tracer.add_metadata("sync_results", {
                "bottles_downloaded": self.stats['bottles_downloaded'],
                "bottles_skipped": self.stats['bottles_skipped'],
                "failed_downloads": self.stats['failed_downloads'],
                "total_size_downloaded": self.stats['total_size_downloaded'],
                "duration_seconds": duration
            })
            
            success = self.stats['failed_downloads'] == 0
            monitoring.logger.info("Sync completed", 
                                 success=success,
                                 bottles_downloaded=self.stats['bottles_downloaded'],
                                 bottles_skipped=self.stats['bottles_skipped'],
                                 failed_downloads=self.stats['failed_downloads'],
                                 duration_seconds=duration)
            
            return success
    
    def format_size(self, size_bytes: int) -> str:
        """Format size in bytes to human-readable string."""
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        elif size_bytes < 1024 * 1024 * 1024:
            return f"{size_bytes / (1024 * 1024):.1f} MB"
        else:
            return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"
    
    def format_duration(self, start_time: datetime, end_time: datetime) -> str:
        """Format duration between two timestamps."""
        duration = end_time - start_time
        total_seconds = int(duration.total_seconds())
        
        if total_seconds < 60:
            return f"{total_seconds}s"
        elif total_seconds < 3600:
            minutes = total_seconds // 60
            seconds = total_seconds % 60
            return f"{minutes}m {seconds}s"
        else:
            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60
            return f"{hours}h {minutes}m"
    
    def send_completion_notification(self, success: bool) -> None:
        """
        Send completion notification to Slack.
        
        Args:
            success: Whether the sync completed successfully
        """
        try:
            if success:
                duration = self.format_duration(self.stats['start_time'], self.stats['end_time'])
                total_size = self.format_size(self.stats['total_size_downloaded'])
                
                self.notification_service.send_sync_success(
                    new_bottles=self.stats['bottles_downloaded'],
                    total_size=total_size,
                    duration=duration,
                    skipped_bottles=self.stats['bottles_skipped']
                )
            else:
                error_details = f"Downloaded: {self.stats['bottles_downloaded']} bottles, " \
                              f"Failed: {self.stats['failed_downloads']} bottles"
                
                self.notification_service.send_sync_failure(
                    error_message="Lambda sync worker encountered errors during execution",
                    error_details=error_details,
                    completed_bottles=self.stats['bottles_downloaded'],
                    failed_bottles=self.stats['failed_downloads']
                )
        except Exception as e:
            monitoring.logger.error(f"Failed to send completion notification: {e}", error=str(e))


def lambda_handler(event: Dict, context) -> Dict:
    """
    Lambda function handler for sync worker.
    
    Args:
        event: Lambda event containing formulas to sync
        context: Lambda context object
        
    Returns:
        Response dictionary with sync results
    """
    # Add AWS request ID to monitoring context
    if hasattr(context, 'aws_request_id'):
        monitoring.tracer.add_annotation("aws_request_id", context.aws_request_id)
    
    with monitoring.track_operation("lambda_handler", {"event_type": "sync_worker"}):
        try:
            monitoring.logger.info(f"Lambda sync worker started",
                                 event_size=len(json.dumps(event, default=str)),
                                 aws_request_id=getattr(context, 'aws_request_id', 'unknown'))
            
            # Parse event data
            formulas_data = event.get('formulas', [])
            config_data = event.get('config', {})
            
            if not formulas_data:
                raise ValueError("No formulas provided in event")
            
            # Parse formulas from event data
            formulas = []
            for formula_data in formulas_data:
                try:
                    # Convert bottle data to BottleInfo objects
                    bottles = {}
                    for platform, bottle_data in formula_data.get('bottles', {}).items():
                        bottles[platform] = BottleInfo(
                            url=bottle_data['url'],
                            sha256=bottle_data['sha256'],
                            size=bottle_data['size']
                        )
                    
                    formula = Formula(
                        name=formula_data['name'],
                        version=formula_data['version'],
                        bottles=bottles
                    )
                    formula.validate()
                    formulas.append(formula)
                    
                except (KeyError, ValueError) as e:
                    monitoring.logger.error(f"Invalid formula data: {e}",
                                          formula_name=formula_data.get('name', 'unknown'),
                                          error=str(e))
                    continue
            
            if not formulas:
                raise ValueError("No valid formulas found in event data")
            
            # Parse sync configuration
            config = SyncConfig.from_dict(config_data)
            config.validate()
            
            monitoring.logger.info(f"Processing {len(formulas)} formulas",
                                 formula_count=len(formulas),
                                 target_platforms=config.target_platforms)
            
            # Add trace metadata
            monitoring.tracer.add_metadata("lambda_config", {
                "formula_count": len(formulas),
                "target_platforms": config.target_platforms,
                "s3_bucket": config.s3_bucket_name
            })
            
            # Initialize sync worker and execute
            worker = LambdaSyncWorker()
            success = worker.sync_formulas(formulas, config)
            
            # Send completion notification
            worker.send_completion_notification(success)
            
            # Flush any remaining metrics
            monitoring.flush_metrics()
            
            # Prepare response
            response = {
                'statusCode': 200 if success else 500,
                'success': success,
                'stats': {
                    'bottles_downloaded': worker.stats['bottles_downloaded'],
                    'bottles_skipped': worker.stats['bottles_skipped'],
                    'total_size_downloaded': worker.stats['total_size_downloaded'],
                    'failed_downloads': worker.stats['failed_downloads'],
                    'duration_seconds': (
                        worker.stats['end_time'] - worker.stats['start_time']
                    ).total_seconds() if worker.stats['end_time'] else 0
                }
            }
            
            monitoring.logger.info(f"Lambda sync worker completed",
                                 success=success,
                                 bottles_downloaded=worker.stats['bottles_downloaded'],
                                 bottles_skipped=worker.stats['bottles_skipped'],
                                 failed_downloads=worker.stats['failed_downloads'])
            
            return response
            
        except Exception as e:
            monitoring.logger.error(f"Lambda sync worker failed: {e}",
                                  error=str(e), error_type=type(e).__name__, exc_info=True)
            
            # Try to send failure notification
            try:
                notification_service = NotificationService(
                    webhook_secret_name=os.environ.get('SLACK_WEBHOOK_SECRET_NAME'),
                    aws_region=os.environ.get('AWS_REGION', 'us-east-1')
                )
                notification_service.send_sync_failure(
                    error_message="Lambda sync worker failed to start",
                    error_details=str(e)
                )
            except Exception as notification_error:
                monitoring.logger.error(f"Failed to send failure notification: {notification_error}",
                                      notification_error=str(notification_error))
            
            return {
                'statusCode': 500,
                'success': False,
                'error': str(e)
            }