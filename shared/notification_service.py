"""
Notification service for Slack integration.

This module provides the NotificationService class for sending formatted
notifications to Slack via webhooks, with AWS Secrets Manager integration
for secure webhook URL storage.
"""

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, List, Optional, Union
from enum import Enum

import boto3
import requests
from botocore.exceptions import ClientError


class NotificationType(Enum):
    """Types of notifications that can be sent."""
    START = "start"
    PROGRESS = "progress"
    SUCCESS = "success"
    FAILURE = "failure"


@dataclass
class NotificationData:
    """Data structure for notification content."""
    message_type: NotificationType
    title: str
    details: Optional[str] = None
    stats: Optional[Dict[str, Union[str, int]]] = None
    error_details: Optional[str] = None
    timestamp: Optional[str] = None
    
    def __post_init__(self):
        """Set timestamp if not provided."""
        if self.timestamp is None:
            self.timestamp = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')


class NotificationService:
    """Service for sending Slack notifications with Secrets Manager integration."""
    
    def __init__(self, 
                 webhook_secret_name: Optional[str] = None,
                 webhook_url: Optional[str] = None,
                 aws_region: str = 'us-east-1'):
        """
        Initialize the notification service.
        
        Args:
            webhook_secret_name: Name of the secret in AWS Secrets Manager containing webhook URL
            webhook_url: Direct webhook URL (for testing or non-secret scenarios)
            aws_region: AWS region for Secrets Manager
        """
        self.webhook_secret_name = webhook_secret_name
        self.webhook_url = webhook_url
        self.aws_region = aws_region
        self._secrets_client = None
        self._cached_webhook_url = None
        
        # Configure logging
        self.logger = logging.getLogger(__name__)
    
    @property
    def secrets_client(self):
        """Lazy initialization of Secrets Manager client."""
        if self._secrets_client is None:
            self._secrets_client = boto3.client('secretsmanager', region_name=self.aws_region)
        return self._secrets_client
    
    def get_webhook_url(self) -> Optional[str]:
        """
        Get the Slack webhook URL from Secrets Manager or direct configuration.
        
        Returns:
            Webhook URL if available, None otherwise
        """
        # Return cached URL if available
        if self._cached_webhook_url:
            return self._cached_webhook_url
        
        # Use direct URL if provided
        if self.webhook_url:
            self._cached_webhook_url = self.webhook_url
            return self._cached_webhook_url
        
        # Fetch from Secrets Manager
        if self.webhook_secret_name:
            try:
                response = self.secrets_client.get_secret_value(SecretId=self.webhook_secret_name)
                secret_data = json.loads(response['SecretString'])
                
                # Support both direct URL and nested structure
                if isinstance(secret_data, str):
                    webhook_url = secret_data
                elif isinstance(secret_data, dict):
                    webhook_url = secret_data.get('webhook_url') or secret_data.get('url')
                else:
                    self.logger.error(f"Invalid secret format for {self.webhook_secret_name}")
                    return None
                
                if webhook_url and webhook_url.startswith('https://hooks.slack.com/'):
                    self._cached_webhook_url = webhook_url
                    return webhook_url
                else:
                    self.logger.error(f"Invalid webhook URL format in secret {self.webhook_secret_name}")
                    return None
                    
            except ClientError as e:
                self.logger.error(f"Failed to retrieve webhook URL from Secrets Manager: {e}")
                return None
            except json.JSONDecodeError as e:
                self.logger.error(f"Failed to parse secret JSON for {self.webhook_secret_name}: {e}")
                return None
        
        return None
    
    def format_start_message(self, data: NotificationData) -> Dict:
        """
        Format a sync start notification message.
        
        Args:
            data: Notification data
            
        Returns:
            Formatted Slack message payload
        """
        return {
            "text": f"🚀 {data.title}",
            "blocks": [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": f"🚀 {data.title}"
                    }
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": data.details or "Homebrew bottles sync has started."
                    }
                },
                {
                    "type": "context",
                    "elements": [
                        {
                            "type": "mrkdwn",
                            "text": f"*Started:* {data.timestamp}"
                        }
                    ]
                }
            ]
        }
    
    def format_progress_message(self, data: NotificationData) -> Dict:
        """
        Format a sync progress notification message.
        
        Args:
            data: Notification data
            
        Returns:
            Formatted Slack message payload
        """
        stats = data.stats or {}
        progress_text = data.details or "Sync in progress..."
        
        # Build stats section if available
        stats_fields = []
        if 'downloaded' in stats and 'total' in stats:
            stats_fields.append({
                "type": "mrkdwn",
                "text": f"*Progress:* {stats['downloaded']}/{stats['total']} bottles"
            })
        
        if 'size_downloaded' in stats:
            stats_fields.append({
                "type": "mrkdwn", 
                "text": f"*Downloaded:* {stats['size_downloaded']}"
            })
        
        if 'estimated_remaining' in stats:
            stats_fields.append({
                "type": "mrkdwn",
                "text": f"*Remaining:* {stats['estimated_remaining']}"
            })
        
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"⏳ {data.title}"
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": progress_text
                }
            }
        ]
        
        if stats_fields:
            blocks.append({
                "type": "section",
                "fields": stats_fields
            })
        
        blocks.append({
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": f"*Updated:* {data.timestamp}"
                }
            ]
        })
        
        return {
            "text": f"⏳ {data.title}",
            "blocks": blocks
        }
    
    def format_success_message(self, data: NotificationData) -> Dict:
        """
        Format a sync success notification message.
        
        Args:
            data: Notification data
            
        Returns:
            Formatted Slack message payload
        """
        stats = data.stats or {}
        success_text = data.details or "Homebrew bottles sync completed successfully!"
        
        # Build stats section
        stats_fields = []
        if 'new_bottles' in stats:
            stats_fields.append({
                "type": "mrkdwn",
                "text": f"*New Bottles:* {stats['new_bottles']}"
            })
        
        if 'total_size' in stats:
            stats_fields.append({
                "type": "mrkdwn",
                "text": f"*Total Size:* {stats['total_size']}"
            })
        
        if 'duration' in stats:
            stats_fields.append({
                "type": "mrkdwn",
                "text": f"*Duration:* {stats['duration']}"
            })
        
        if 'skipped_bottles' in stats:
            stats_fields.append({
                "type": "mrkdwn",
                "text": f"*Skipped:* {stats['skipped_bottles']} (already downloaded)"
            })
        
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"✅ {data.title}"
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": success_text
                }
            }
        ]
        
        if stats_fields:
            blocks.append({
                "type": "section",
                "fields": stats_fields
            })
        
        blocks.append({
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": f"*Completed:* {data.timestamp}"
                }
            ]
        })
        
        return {
            "text": f"✅ {data.title}",
            "blocks": blocks
        }
    
    def format_failure_message(self, data: NotificationData) -> Dict:
        """
        Format a sync failure notification message.
        
        Args:
            data: Notification data
            
        Returns:
            Formatted Slack message payload
        """
        failure_text = data.details or "Homebrew bottles sync failed."
        error_details = data.error_details or "No additional error details available."
        
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"❌ {data.title}"
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": failure_text
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Error Details:*\n```{error_details}```"
                }
            }
        ]
        
        # Add stats if available (partial completion info)
        stats = data.stats or {}
        if stats:
            stats_fields = []
            if 'completed_bottles' in stats:
                stats_fields.append({
                    "type": "mrkdwn",
                    "text": f"*Completed:* {stats['completed_bottles']} bottles"
                })
            
            if 'failed_bottles' in stats:
                stats_fields.append({
                    "type": "mrkdwn",
                    "text": f"*Failed:* {stats['failed_bottles']} bottles"
                })
            
            if stats_fields:
                blocks.append({
                    "type": "section",
                    "fields": stats_fields
                })
        
        blocks.append({
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": f"*Failed:* {data.timestamp}"
                }
            ]
        })
        
        return {
            "text": f"❌ {data.title}",
            "blocks": blocks
        }
    
    def format_message(self, data: NotificationData) -> Dict:
        """
        Format a notification message based on its type.
        
        Args:
            data: Notification data
            
        Returns:
            Formatted Slack message payload
        """
        formatters = {
            NotificationType.START: self.format_start_message,
            NotificationType.PROGRESS: self.format_progress_message,
            NotificationType.SUCCESS: self.format_success_message,
            NotificationType.FAILURE: self.format_failure_message
        }
        
        formatter = formatters.get(data.message_type)
        if not formatter:
            raise ValueError(f"Unknown notification type: {data.message_type}")
        
        return formatter(data)
    
    def send_notification(self, data: NotificationData) -> bool:
        """
        Send a notification to Slack.
        
        Args:
            data: Notification data to send
            
        Returns:
            True if notification sent successfully, False otherwise
        """
        webhook_url = self.get_webhook_url()
        if not webhook_url:
            self.logger.error("No webhook URL available for sending notification")
            return False
        
        try:
            # Format the message
            message_payload = self.format_message(data)
            
            # Send to Slack
            response = requests.post(
                webhook_url,
                json=message_payload,
                headers={'Content-Type': 'application/json'},
                timeout=30
            )
            
            if response.status_code == 200:
                self.logger.info(f"Successfully sent {data.message_type.value} notification")
                return True
            else:
                self.logger.error(f"Failed to send notification. Status: {response.status_code}, Response: {response.text}")
                return False
                
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Network error sending notification: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Unexpected error sending notification: {e}")
            return False
    
    def send_sync_start(self, date: str, estimated_bottles: int = 0, estimated_size: str = "") -> bool:
        """
        Send a sync start notification.
        
        Args:
            date: Date of the sync (YYYY-MM-DD format)
            estimated_bottles: Estimated number of bottles to download
            estimated_size: Estimated total download size
            
        Returns:
            True if notification sent successfully, False otherwise
        """
        details = f"Starting sync for {date}"
        if estimated_bottles > 0:
            details += f" - Processing {estimated_bottles} formulas"
        if estimated_size:
            details += f" - Estimated size: {estimated_size}"
        
        data = NotificationData(
            message_type=NotificationType.START,
            title=f"Homebrew Sync Started - {date}",
            details=details
        )
        
        return self.send_notification(data)
    
    def send_sync_progress(self, 
                          downloaded: int, 
                          total: int, 
                          size_downloaded: str,
                          estimated_remaining: str = "") -> bool:
        """
        Send a sync progress notification.
        
        Args:
            downloaded: Number of bottles downloaded so far
            total: Total number of bottles to download
            size_downloaded: Size downloaded so far (formatted string)
            estimated_remaining: Estimated remaining time/size
            
        Returns:
            True if notification sent successfully, False otherwise
        """
        percentage = int((downloaded / total) * 100) if total > 0 else 0
        
        data = NotificationData(
            message_type=NotificationType.PROGRESS,
            title="Homebrew Sync Progress",
            details=f"Download progress: {percentage}% complete",
            stats={
                'downloaded': downloaded,
                'total': total,
                'size_downloaded': size_downloaded,
                'estimated_remaining': estimated_remaining
            }
        )
        
        return self.send_notification(data)
    
    def send_sync_success(self, 
                         new_bottles: int, 
                         total_size: str,
                         duration: str,
                         skipped_bottles: int = 0) -> bool:
        """
        Send a sync success notification.
        
        Args:
            new_bottles: Number of new bottles downloaded
            total_size: Total size downloaded (formatted string)
            duration: Duration of the sync process
            skipped_bottles: Number of bottles skipped (already downloaded)
            
        Returns:
            True if notification sent successfully, False otherwise
        """
        data = NotificationData(
            message_type=NotificationType.SUCCESS,
            title="Homebrew Sync Complete",
            details="Homebrew bottles sync completed successfully!",
            stats={
                'new_bottles': new_bottles,
                'total_size': total_size,
                'duration': duration,
                'skipped_bottles': skipped_bottles
            }
        )
        
        return self.send_notification(data)
    
    def send_sync_failure(self, 
                         error_message: str,
                         error_details: str = "",
                         completed_bottles: int = 0,
                         failed_bottles: int = 0) -> bool:
        """
        Send a sync failure notification.
        
        Args:
            error_message: Main error message
            error_details: Detailed error information
            completed_bottles: Number of bottles completed before failure
            failed_bottles: Number of bottles that failed
            
        Returns:
            True if notification sent successfully, False otherwise
        """
        stats = {}
        if completed_bottles > 0:
            stats['completed_bottles'] = completed_bottles
        if failed_bottles > 0:
            stats['failed_bottles'] = failed_bottles
        
        data = NotificationData(
            message_type=NotificationType.FAILURE,
            title="Homebrew Sync Failed",
            details=error_message,
            error_details=error_details,
            stats=stats if stats else None
        )
        
        return self.send_notification(data)
    
    def test_connection(self) -> bool:
        """
        Test the Slack webhook connection by sending a test message.
        
        Returns:
            True if test message sent successfully, False otherwise
        """
        data = NotificationData(
            message_type=NotificationType.START,
            title="Homebrew Sync Test",
            details="This is a test notification to verify Slack integration is working."
        )
        
        return self.send_notification(data)