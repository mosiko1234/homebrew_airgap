"""
ECS Sync Worker for Homebrew Bottles Sync System.

This module implements the containerized Python application for ECS Fargate tasks
that handles large-scale bottle downloads with progress tracking, batch processing,
and graceful handling of network interruptions.
"""

import os
import sys
import json
import time
import logging
import hashlib
import tempfile
import asyncio
import aiohttp
import aiofiles
from pathlib import Path
from datetime import datetime, timezone
from typing import List, Dict, Optional, Tuple, Set
from dataclasses import dataclass, field
from concurrent.futures import ThreadPoolExecutor
import signal

# Add shared modules to path
sys.path.append('/app/shared')

from models import Formula, BottleInfo, SyncConfig, HashFileManager
from s3_service import S3Service
from homebrew_api import HomebrewAPIClient
from notification_service import NotificationService, NotificationData, NotificationType
from monitoring import create_monitoring_manager, SyncPhase


@dataclass
class DownloadProgress:
    """Tracks download progress for a single bottle."""
    formula_name: str
    platform: str
    url: str
    local_path: str
    expected_sha256: str
    expected_size: int
    downloaded_size: int = 0
    status: str = "pending"  # pending, downloading, completed, failed, skipped
    error_message: Optional[str] = None
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    
    @property
    def duration(self) -> Optional[float]:
        """Get download duration in seconds."""
        if self.start_time and self.end_time:
            return self.end_time - self.start_time
        return None
    
    @property
    def progress_percentage(self) -> float:
        """Get download progress as percentage."""
        if self.expected_size > 0:
            return min(100.0, (self.downloaded_size / self.expected_size) * 100)
        return 0.0


@dataclass
class SyncStats:
    """Overall sync statistics."""
    total_bottles: int = 0
    completed_bottles: int = 0
    failed_bottles: int = 0
    skipped_bottles: int = 0
    total_downloaded_size: int = 0
    start_time: Optional[float] = None
    last_progress_report: Optional[float] = None
    
    @property
    def success_rate(self) -> float:
        """Get success rate as percentage."""
        if self.total_bottles > 0:
            return (self.completed_bottles / self.total_bottles) * 100
        return 0.0
    
    @property
    def duration(self) -> Optional[float]:
        """Get total sync duration in seconds."""
        if self.start_time:
            return time.time() - self.start_time
        return None


class ECSBottleDownloader:
    """Main ECS bottle downloader with progress tracking and error handling."""
    
    def __init__(self, config: SyncConfig):
        """
        Initialize the ECS bottle downloader.
        
        Args:
            config: Sync configuration
        """
        self.config = config
        
        # Initialize monitoring
        self.monitoring = create_monitoring_manager("ecs_sync_worker")
        
        # Initialize services
        self.s3_service = S3Service(config.s3_bucket_name)
        self.homebrew_client = HomebrewAPIClient()
        self.notification_service = NotificationService(
            webhook_secret_name=os.getenv('SLACK_WEBHOOK_SECRET_NAME'),
            webhook_url=config.slack_webhook_url
        )
        
        # Initialize hash file manager
        self.hash_manager = HashFileManager(self.s3_service)
        
        # Download tracking
        self.download_progress: Dict[str, DownloadProgress] = {}
        self.sync_stats = SyncStats()
        self.shutdown_requested = False
        
        # Working directory for temporary files
        self.work_dir = Path(os.getenv('WORK_DIR', '/tmp/homebrew-sync'))
        self.work_dir.mkdir(parents=True, exist_ok=True)
        
        # Progress reporting interval (seconds)
        self.progress_report_interval = int(os.getenv('PROGRESS_REPORT_INTERVAL', '300'))  # 5 minutes
        
        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully."""
        self.monitoring.logger.info(f"Received signal {signum}, initiating graceful shutdown...",
                                   signal=signum, shutdown_requested=True)
        self.shutdown_requested = True
    
    async def run_sync(self) -> bool:
        """
        Run the complete sync process.
        
        Returns:
            True if sync completed successfully, False otherwise
        """
        try:
            self.sync_stats.start_time = time.time()
            sync_date = datetime.now(timezone.utc).strftime('%Y-%m-%d')
            
            with self.monitoring.track_operation("ecs_sync_initialization"):
                self.monitoring.logger.info("Starting ECS bottle sync process", sync_date=sync_date)
                
                # Load existing hash file with external support
                with self.monitoring.track_operation("hash_file_loading"):
                    self.monitoring.logger.info("Loading existing hash file...")
                    
                    # Try external hash file first if configured
                    external_loaded = False
                    if self.config.external_hash_file_url or self.config.external_hash_file_s3_key:
                        self.monitoring.logger.info("Attempting to load external hash file")
                        if self.hash_manager.load_external_hash_file(self.config):
                            external_loaded = True
                            self.monitoring.logger.info(f"Loaded external hash file with {len(self.hash_manager.bottles)} bottles")
                        else:
                            self.monitoring.logger.warning("Failed to load external hash file, will try default hash file")
                    
                    # Fall back to default hash file if external not loaded
                    if not external_loaded:
                        hash_loaded = self.hash_manager.load_from_s3()
                        if hash_loaded:
                            self.monitoring.logger.info(f"Loaded default hash file with {len(self.hash_manager.bottles)} existing bottles",
                                                       existing_bottles=len(self.hash_manager.bottles))
                        else:
                            self.monitoring.logger.info("No existing hash file found, starting fresh sync")
                    
                    self.monitoring.record_sync_progress(0, 0, 0, SyncPhase.HASH_LOADING)
                
                # Fetch and process formulas
                with self.monitoring.track_operation("formula_fetch"):
                    self.monitoring.logger.info("Fetching formulas from Homebrew API...")
                    formulas, download_estimate = self.homebrew_client.fetch_and_process_formulas(self.config)
                    
                    self.monitoring.logger.info(f"Processing {len(formulas)} formulas with {download_estimate.total_bottles} bottles "
                                              f"({download_estimate.total_size_gb:.2f} GB)",
                                              formula_count=len(formulas),
                                              total_bottles=download_estimate.total_bottles,
                                              estimated_size_gb=download_estimate.total_size_gb)
                    
                    self.monitoring.record_sync_progress(0, download_estimate.total_bottles, 0, SyncPhase.FORMULA_FETCH)
            
            # Send start notification
            await self._send_start_notification(sync_date, download_estimate)
            
            # Plan downloads (filter out already downloaded bottles)
            download_plan = self._plan_downloads(formulas, sync_date)
            self.sync_stats.total_bottles = len(download_plan)
            
            if not download_plan:
                self.monitoring.logger.info("No new bottles to download", 
                                           skipped_bottles=self.sync_stats.skipped_bottles)
                await self._send_success_notification(0, "0 MB", "0s", len(formulas))
                return True
            
            self.monitoring.logger.info(f"Planned {len(download_plan)} bottle downloads",
                                      planned_downloads=len(download_plan),
                                      skipped_bottles=self.sync_stats.skipped_bottles)
            
            # Execute downloads in batches
            success = await self._execute_downloads(download_plan)
            
            if success and not self.shutdown_requested:
                # Update hash file
                await self._update_hash_file(sync_date)
                
                # Send success notification
                await self._send_success_notification(
                    self.sync_stats.completed_bottles,
                    self._format_size(self.sync_stats.total_downloaded_size),
                    self._format_duration(self.sync_stats.duration or 0),
                    self.sync_stats.skipped_bottles
                )
                
                self.monitoring.logger.info(f"Sync completed successfully: {self.sync_stats.completed_bottles} bottles downloaded",
                                           completed_bottles=self.sync_stats.completed_bottles,
                                           success=True)
                
                # Flush metrics
                self.monitoring.flush_metrics()
                return True
            else:
                # Send failure notification
                error_msg = "Sync interrupted by shutdown signal" if self.shutdown_requested else "Download failures occurred"
                await self._send_failure_notification(error_msg)
                
                # Flush metrics
                self.monitoring.flush_metrics()
                return False
                
        except Exception as e:
            self.monitoring.logger.error(f"Sync process failed: {e}",
                                       error=str(e), error_type=type(e).__name__, exc_info=True)
            await self._send_failure_notification(f"Sync process failed: {str(e)}")
            
            # Flush metrics
            self.monitoring.flush_metrics()
            return False
    
    def _plan_downloads(self, formulas: List[Formula], sync_date: str) -> List[DownloadProgress]:
        """
        Plan downloads by filtering out already downloaded bottles.
        
        Args:
            formulas: List of formulas to process
            sync_date: Current sync date
            
        Returns:
            List of DownloadProgress objects for bottles to download
        """
        download_plan = []
        skipped_count = 0
        
        for formula in formulas:
            for platform, bottle in formula.bottles.items():
                # Check if bottle already exists in hash file
                if self.hash_manager.has_bottle(formula, platform, bottle):
                    skipped_count += 1
                    continue
                
                # Create download progress tracker
                filename = f"{formula.name}-{formula.version}.{platform}.bottle.tar.gz"
                local_path = self.work_dir / filename
                
                progress = DownloadProgress(
                    formula_name=formula.name,
                    platform=platform,
                    url=bottle.url,
                    local_path=str(local_path),
                    expected_sha256=bottle.sha256,
                    expected_size=bottle.size
                )
                
                download_plan.append(progress)
        
        self.sync_stats.skipped_bottles = skipped_count
        self.monitoring.logger.info(f"Skipped {skipped_count} already downloaded bottles",
                                   skipped_count=skipped_count)
        
        return download_plan
    
    async def _execute_downloads(self, download_plan: List[DownloadProgress]) -> bool:
        """
        Execute downloads in batches with progress tracking.
        
        Args:
            download_plan: List of downloads to execute
            
        Returns:
            True if all downloads completed successfully, False otherwise
        """
        # Create download batches
        batch_size = self.config.max_concurrent_downloads
        batches = [download_plan[i:i + batch_size] for i in range(0, len(download_plan), batch_size)]
        
        with self.monitoring.track_operation("execute_downloads", {"batch_count": len(batches), "total_downloads": len(download_plan)}):
            self.monitoring.logger.info(f"Executing downloads in {len(batches)} batches of {batch_size}",
                                       batch_count=len(batches), batch_size=batch_size)
            
            # Start progress reporting task
            progress_task = asyncio.create_task(self._progress_reporter())
            
            try:
                # Process batches
                for batch_idx, batch in enumerate(batches):
                    if self.shutdown_requested:
                        self.monitoring.logger.info("Shutdown requested, stopping downloads",
                                                   shutdown_requested=True)
                        break
                    
                    self.monitoring.logger.info(f"Processing batch {batch_idx + 1}/{len(batches)} ({len(batch)} bottles)",
                                              batch_index=batch_idx + 1, batch_total=len(batches), batch_size=len(batch))
                    
                    # Execute batch downloads concurrently
                    with self.monitoring.track_operation("download_batch", {"batch_index": batch_idx + 1}):
                        tasks = [self._download_bottle(progress) for progress in batch]
                        await asyncio.gather(*tasks, return_exceptions=True)
                    
                    # Upload completed bottles to S3
                    with self.monitoring.track_operation("upload_batch", {"batch_index": batch_idx + 1}):
                        await self._upload_batch_to_s3(batch)
                    
                    # Clean up local files
                    self._cleanup_batch_files(batch)
                    
                    # Update progress metrics
                    self.monitoring.record_sync_progress(
                        self.sync_stats.completed_bottles,
                        self.sync_stats.total_bottles,
                        self.sync_stats.failed_bottles,
                        SyncPhase.BOTTLE_DOWNLOAD
                    )
                
                # Cancel progress reporting
                progress_task.cancel()
                
                # Final progress report
                await self._send_progress_notification()
                
                # Check if all downloads were successful
                success = self.sync_stats.failed_bottles == 0 and not self.shutdown_requested
                
                self.monitoring.logger.info(f"Download execution completed: {self.sync_stats.completed_bottles} successful, "
                                          f"{self.sync_stats.failed_bottles} failed",
                                          completed_bottles=self.sync_stats.completed_bottles,
                                          failed_bottles=self.sync_stats.failed_bottles,
                                          success=success)
                
                return success
                
            except Exception as e:
                progress_task.cancel()
                self.monitoring.logger.error(f"Error during download execution: {e}",
                                           error=str(e), error_type=type(e).__name__, exc_info=True)
                return False
    
    async def _download_bottle(self, progress: DownloadProgress) -> None:
        """
        Download a single bottle with retry logic and progress tracking.
        
        Args:
            progress: Download progress tracker
        """
        progress.start_time = time.time()
        progress.status = "downloading"
        
        for attempt in range(self.config.retry_attempts + 1):
            if self.shutdown_requested:
                progress.status = "failed"
                progress.error_message = "Shutdown requested"
                return
            
            try:
                self.monitoring.logger.debug(f"Downloading {progress.formula_name} ({progress.platform}) - attempt {attempt + 1}",
                                            formula_name=progress.formula_name, platform=progress.platform, attempt=attempt + 1)
                
                async with aiohttp.ClientSession() as session:
                    async with session.get(progress.url) as response:
                        if response.status != 200:
                            raise aiohttp.ClientError(f"HTTP {response.status}: {response.reason}")
                        
                        # Verify content length if available
                        content_length = response.headers.get('content-length')
                        if content_length and int(content_length) != progress.expected_size:
                            self.monitoring.logger.warning(f"Content length mismatch for {progress.formula_name}: "
                                                          f"expected {progress.expected_size}, got {content_length}",
                                                          formula_name=progress.formula_name,
                                                          expected_size=progress.expected_size,
                                                          actual_size=content_length)
                        
                        # Download with progress tracking
                        await self._download_with_progress(response, progress)
                
                # Verify download
                if await self._verify_download(progress):
                    progress.status = "completed"
                    progress.end_time = time.time()
                    self.sync_stats.completed_bottles += 1
                    self.sync_stats.total_downloaded_size += progress.downloaded_size
                    
                    # Record download metrics
                    self.monitoring.record_bottle_download(
                        f"{progress.formula_name}-{progress.platform}",
                        progress.downloaded_size,
                        progress.duration or 0,
                        True
                    )
                    
                    self.monitoring.logger.info(f"Successfully downloaded {progress.formula_name} ({progress.platform}) "
                                              f"in {progress.duration:.1f}s",
                                              formula_name=progress.formula_name,
                                              platform=progress.platform,
                                              duration=progress.duration,
                                              size_bytes=progress.downloaded_size)
                    return
                else:
                    raise ValueError("Download verification failed")
                    
            except Exception as e:
                error_msg = f"Attempt {attempt + 1} failed: {str(e)}"
                self.monitoring.logger.warning(f"Download failed for {progress.formula_name} ({progress.platform}): {error_msg}",
                                             formula_name=progress.formula_name,
                                             platform=progress.platform,
                                             attempt=attempt + 1,
                                             error=str(e))
                
                if attempt < self.config.retry_attempts:
                    # Exponential backoff
                    wait_time = 2 ** attempt
                    await asyncio.sleep(wait_time)
                else:
                    # All attempts failed
                    progress.status = "failed"
                    progress.error_message = error_msg
                    progress.end_time = time.time()
                    self.sync_stats.failed_bottles += 1
                    
                    # Record failed download metrics
                    self.monitoring.record_bottle_download(
                        f"{progress.formula_name}-{progress.platform}",
                        0,
                        progress.duration or 0,
                        False
                    )
                    
                    self.monitoring.logger.error(f"Failed to download {progress.formula_name} ({progress.platform}) "
                                               f"after {self.config.retry_attempts + 1} attempts",
                                               formula_name=progress.formula_name,
                                               platform=progress.platform,
                                               total_attempts=self.config.retry_attempts + 1,
                                               final_error=error_msg)
    
    async def _download_with_progress(self, response: aiohttp.ClientResponse, progress: DownloadProgress) -> None:
        """
        Download response content with progress tracking.
        
        Args:
            response: HTTP response object
            progress: Download progress tracker
        """
        chunk_size = 8192
        progress.downloaded_size = 0
        
        async with aiofiles.open(progress.local_path, 'wb') as f:
            async for chunk in response.content.iter_chunked(chunk_size):
                if self.shutdown_requested:
                    raise asyncio.CancelledError("Shutdown requested")
                
                await f.write(chunk)
                progress.downloaded_size += len(chunk)
    
    async def _verify_download(self, progress: DownloadProgress) -> bool:
        """
        Verify downloaded bottle integrity.
        
        Args:
            progress: Download progress tracker
            
        Returns:
            True if verification passed, False otherwise
        """
        try:
            # Check file size
            file_path = Path(progress.local_path)
            if not file_path.exists():
                self.monitoring.logger.error(f"Downloaded file does not exist: {progress.local_path}",
                                           formula_name=progress.formula_name, local_path=progress.local_path)
                return False
            
            actual_size = file_path.stat().st_size
            if actual_size != progress.expected_size:
                self.monitoring.logger.error(f"Size mismatch for {progress.formula_name}: "
                                           f"expected {progress.expected_size}, got {actual_size}",
                                           formula_name=progress.formula_name,
                                           expected_size=progress.expected_size,
                                           actual_size=actual_size)
                return False
            
            # Verify SHA256 hash
            sha256_hash = hashlib.sha256()
            async with aiofiles.open(progress.local_path, 'rb') as f:
                while chunk := await f.read(8192):
                    sha256_hash.update(chunk)
            
            actual_sha256 = sha256_hash.hexdigest()
            if actual_sha256 != progress.expected_sha256:
                self.monitoring.logger.error(f"SHA256 mismatch for {progress.formula_name}: "
                                           f"expected {progress.expected_sha256}, got {actual_sha256}",
                                           formula_name=progress.formula_name,
                                           expected_sha256=progress.expected_sha256,
                                           actual_sha256=actual_sha256)
                return False
            
            return True
            
        except Exception as e:
            self.monitoring.logger.error(f"Error verifying download for {progress.formula_name}: {e}",
                                       formula_name=progress.formula_name, error=str(e))
            return False
    
    async def _upload_batch_to_s3(self, batch: List[DownloadProgress]) -> None:
        """
        Upload completed bottles from a batch to S3.
        
        Args:
            batch: List of download progress objects
        """
        sync_date = datetime.now(timezone.utc).strftime('%Y-%m-%d')
        
        for progress in batch:
            if progress.status == "completed":
                try:
                    # S3 key with date-based folder structure
                    filename = Path(progress.local_path).name
                    s3_key = f"{sync_date}/{filename}"
                    
                    # Upload to S3
                    success = self.s3_service.upload_file(
                        progress.local_path,
                        s3_key,
                        metadata={
                            'formula_name': progress.formula_name,
                            'platform': progress.platform,
                            'sha256': progress.expected_sha256,
                            'sync_date': sync_date
                        }
                    )
                    
                    if success:
                        self.monitoring.logger.debug(f"Uploaded {filename} to S3",
                                                    filename=filename, s3_key=s3_key)
                    else:
                        self.monitoring.logger.error(f"Failed to upload {filename} to S3",
                                                   filename=filename, s3_key=s3_key)
                        progress.status = "failed"
                        progress.error_message = "S3 upload failed"
                        self.sync_stats.completed_bottles -= 1
                        self.sync_stats.failed_bottles += 1
                        
                except Exception as e:
                    self.monitoring.logger.error(f"Error uploading {progress.formula_name} to S3: {e}",
                                               formula_name=progress.formula_name, error=str(e))
                    progress.status = "failed"
                    progress.error_message = f"S3 upload error: {str(e)}"
                    self.sync_stats.completed_bottles -= 1
                    self.sync_stats.failed_bottles += 1
    
    def _cleanup_batch_files(self, batch: List[DownloadProgress]) -> None:
        """
        Clean up local files from a batch.
        
        Args:
            batch: List of download progress objects
        """
        for progress in batch:
            try:
                file_path = Path(progress.local_path)
                if file_path.exists():
                    file_path.unlink()
                    self.monitoring.logger.debug(f"Cleaned up local file: {progress.local_path}",
                                                local_path=progress.local_path)
            except Exception as e:
                self.monitoring.logger.warning(f"Failed to clean up {progress.local_path}: {e}",
                                             local_path=progress.local_path, error=str(e))
    
    async def _update_hash_file(self, sync_date: str) -> None:
        """
        Update the hash file with newly downloaded bottles.
        
        Args:
            sync_date: Current sync date
        """
        with self.monitoring.track_operation("hash_file_update"):
            try:
                self.monitoring.logger.info("Updating hash file...", sync_date=sync_date)
                
                # Add completed bottles to hash manager
                for progress in self.download_progress.values():
                    if progress.status == "completed":
                        # Create a temporary Formula and BottleInfo for hash manager
                        bottle_info = BottleInfo(
                            url=progress.url,
                            sha256=progress.expected_sha256,
                            size=progress.expected_size
                        )
                        
                        formula = Formula(
                            name=progress.formula_name,
                            version="",  # Version will be parsed from filename if needed
                            bottles={progress.platform: bottle_info}
                        )
                        
                        self.hash_manager.add_bottle(formula, progress.platform, bottle_info, sync_date)
                
                # Save hash file atomically
                success = self.hash_manager.save_to_s3_atomic()
                if success:
                    self.monitoring.logger.info(f"Successfully updated hash file with {self.sync_stats.completed_bottles} new bottles",
                                               completed_bottles=self.sync_stats.completed_bottles)
                    
                    # Record hash update metrics
                    self.monitoring.record_sync_progress(
                        self.sync_stats.completed_bottles,
                        self.sync_stats.total_bottles,
                        self.sync_stats.failed_bottles,
                        SyncPhase.HASH_UPDATE
                    )
                else:
                    self.monitoring.logger.error("Failed to update hash file")
                    
            except Exception as e:
                self.monitoring.logger.error(f"Error updating hash file: {e}",
                                           error=str(e), error_type=type(e).__name__, exc_info=True)
    
    async def _progress_reporter(self) -> None:
        """Background task for periodic progress reporting."""
        try:
            while not self.shutdown_requested:
                await asyncio.sleep(self.progress_report_interval)
                
                # Check if enough time has passed since last report
                current_time = time.time()
                if (self.sync_stats.last_progress_report is None or 
                    current_time - self.sync_stats.last_progress_report >= self.progress_report_interval):
                    
                    await self._send_progress_notification()
                    self.sync_stats.last_progress_report = current_time
                    
        except asyncio.CancelledError:
            self.logger.debug("Progress reporter cancelled")
    
    async def _send_start_notification(self, sync_date: str, download_estimate) -> None:
        """Send sync start notification."""
        try:
            await asyncio.get_event_loop().run_in_executor(
                None,
                self.notification_service.send_sync_start,
                sync_date,
                download_estimate.total_bottles,
                f"{download_estimate.total_size_gb:.1f} GB"
            )
        except Exception as e:
            self.logger.warning(f"Failed to send start notification: {e}")
    
    async def _send_progress_notification(self) -> None:
        """Send sync progress notification."""
        try:
            if self.sync_stats.total_bottles > 0:
                completed = self.sync_stats.completed_bottles + self.sync_stats.failed_bottles
                size_downloaded = self._format_size(self.sync_stats.total_downloaded_size)
                
                # Estimate remaining time
                remaining = ""
                if self.sync_stats.duration and completed > 0:
                    avg_time_per_bottle = self.sync_stats.duration / completed
                    remaining_bottles = self.sync_stats.total_bottles - completed
                    estimated_remaining_time = avg_time_per_bottle * remaining_bottles
                    remaining = self._format_duration(estimated_remaining_time)
                
                await asyncio.get_event_loop().run_in_executor(
                    None,
                    self.notification_service.send_sync_progress,
                    completed,
                    self.sync_stats.total_bottles,
                    size_downloaded,
                    remaining
                )
        except Exception as e:
            self.logger.warning(f"Failed to send progress notification: {e}")
    
    async def _send_success_notification(self, new_bottles: int, total_size: str, duration: str, skipped: int) -> None:
        """Send sync success notification."""
        try:
            await asyncio.get_event_loop().run_in_executor(
                None,
                self.notification_service.send_sync_success,
                new_bottles,
                total_size,
                duration,
                skipped
            )
        except Exception as e:
            self.logger.warning(f"Failed to send success notification: {e}")
    
    async def _send_failure_notification(self, error_message: str) -> None:
        """Send sync failure notification."""
        try:
            await asyncio.get_event_loop().run_in_executor(
                None,
                self.notification_service.send_sync_failure,
                error_message,
                f"Completed: {self.sync_stats.completed_bottles}, Failed: {self.sync_stats.failed_bottles}",
                self.sync_stats.completed_bottles,
                self.sync_stats.failed_bottles
            )
        except Exception as e:
            self.logger.warning(f"Failed to send failure notification: {e}")
    
    def _format_size(self, size_bytes: int) -> str:
        """Format size in bytes to human readable string."""
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 ** 2:
            return f"{size_bytes / 1024:.1f} KB"
        elif size_bytes < 1024 ** 3:
            return f"{size_bytes / (1024 ** 2):.1f} MB"
        else:
            return f"{size_bytes / (1024 ** 3):.1f} GB"
    
    def _format_duration(self, duration_seconds: float) -> str:
        """Format duration in seconds to human readable string."""
        if duration_seconds < 60:
            return f"{duration_seconds:.0f}s"
        elif duration_seconds < 3600:
            return f"{duration_seconds / 60:.1f}m"
        else:
            hours = int(duration_seconds // 3600)
            minutes = int((duration_seconds % 3600) // 60)
            return f"{hours}h {minutes}m"


def setup_logging():
    """Setup logging configuration."""
    log_level = os.getenv('LOG_LEVEL', 'INFO').upper()
    
    logging.basicConfig(
        level=getattr(logging, log_level),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    # Set specific log levels for noisy libraries
    logging.getLogger('boto3').setLevel(logging.WARNING)
    logging.getLogger('botocore').setLevel(logging.WARNING)
    logging.getLogger('urllib3').setLevel(logging.WARNING)


def load_config() -> SyncConfig:
    """Load configuration from environment variables."""
    return SyncConfig(
        target_platforms=os.getenv('TARGET_PLATFORMS', 'arm64_sonoma,arm64_ventura,monterey').split(','),
        size_threshold_gb=int(os.getenv('SIZE_THRESHOLD_GB', '20')),
        max_concurrent_downloads=int(os.getenv('MAX_CONCURRENT_DOWNLOADS', '10')),
        retry_attempts=int(os.getenv('RETRY_ATTEMPTS', '3')),
        slack_webhook_url=os.getenv('SLACK_WEBHOOK_URL'),
        s3_bucket_name=os.getenv('S3_BUCKET_NAME')
    )


async def main():
    """Main entry point for the ECS sync worker."""
    setup_logging()
    logger = logging.getLogger(__name__)
    
    try:
        logger.info("Starting ECS Homebrew Bottles Sync Worker")
        
        # Load configuration
        config = load_config()
        config.validate()
        
        logger.info(f"Configuration: {config.target_platforms} platforms, "
                   f"{config.max_concurrent_downloads} concurrent downloads, "
                   f"{config.retry_attempts} retry attempts")
        
        # Create and run downloader
        downloader = ECSBottleDownloader(config)
        success = await downloader.run_sync()
        
        if success:
            logger.info("ECS sync completed successfully")
            sys.exit(0)
        else:
            logger.error("ECS sync failed")
            sys.exit(1)
            
    except Exception as e:
        logger.error(f"Fatal error in ECS sync worker: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())