#!/usr/bin/env python3
"""
Comprehensive notification system for CI/CD pipeline.
Sends notifications to Slack and email with intelligent routing based on severity and environment.
"""

import argparse
import json
import os
import sys
import smtplib
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, List, Optional, Union
import requests


class NotificationTemplate:
    """Template system for different notification types"""
    
    # Slack message templates
    SLACK_TEMPLATES = {
        "deployment_success": {
            "color": "good",
            "emoji": "🚀",
            "title": "Deployment Successful",
            "fields": [
                {"title": "Environment", "key": "environment", "short": True},
                {"title": "Status", "key": "status", "short": True},
                {"title": "Commit", "key": "commit_short", "short": True},
                {"title": "Duration", "key": "duration_formatted", "short": True},
                {"title": "User", "key": "user", "short": True},
                {"title": "Time", "key": "timestamp_formatted", "short": True}
            ]
        },
        "deployment_failure": {
            "color": "danger",
            "emoji": "💥",
            "title": "Deployment Failed",
            "fields": [
                {"title": "Environment", "key": "environment", "short": True},
                {"title": "Status", "key": "status", "short": True},
                {"title": "Commit", "key": "commit_short", "short": True},
                {"title": "User", "key": "user", "short": True},
                {"title": "Time", "key": "timestamp_formatted", "short": True},
                {"title": "Error", "key": "error_summary", "short": False}
            ]
        },
        "health_check_failure": {
            "color": "warning",
            "emoji": "⚠️",
            "title": "Health Check Issues Detected",
            "fields": [
                {"title": "Environment", "key": "environment", "short": True},
                {"title": "Failed Checks", "key": "failed_count", "short": True},
                {"title": "Total Checks", "key": "total_count", "short": True},
                {"title": "Time", "key": "timestamp_formatted", "short": True}
            ]
        },
        "smoke_test_failure": {
            "color": "warning",
            "emoji": "🧪",
            "title": "Smoke Tests Failed",
            "fields": [
                {"title": "Environment", "key": "environment", "short": True},
                {"title": "Failed Tests", "key": "failed_count", "short": True},
                {"title": "Total Tests", "key": "total_count", "short": True},
                {"title": "Time", "key": "timestamp_formatted", "short": True}
            ]
        },
        "monitoring_alert": {
            "color": "warning",
            "emoji": "🔍",
            "title": "Monitoring Alert",
            "fields": [
                {"title": "Environment", "key": "environment", "short": True},
                {"title": "Alert Type", "key": "alert_type", "short": True},
                {"title": "Severity", "key": "severity", "short": True},
                {"title": "Time", "key": "timestamp_formatted", "short": True},
                {"title": "Details", "key": "alert_details", "short": False}
            ]
        },
        "cost_alert": {
            "color": "warning",
            "emoji": "💰",
            "title": "Cost Threshold Alert",
            "fields": [
                {"title": "Environment", "key": "environment", "short": True},
                {"title": "Current Cost", "key": "current_cost", "short": True},
                {"title": "Threshold", "key": "threshold", "short": True},
                {"title": "Period", "key": "period", "short": True},
                {"title": "Time", "key": "timestamp_formatted", "short": True}
            ]
        }
    }
    
    # Email templates
    EMAIL_TEMPLATES = {
        "deployment_success": {
            "subject": "✅ Deployment Successful - {environment}",
            "template": """
Deployment to {environment} completed successfully!

Details:
- Environment: {environment}
- Commit: {commit_sha}
- Duration: {duration_formatted}
- User: {user}
- Time: {timestamp_formatted}

{additional_details}

Dashboard: {dashboard_url}
            """.strip()
        },
        "deployment_failure": {
            "subject": "❌ Deployment Failed - {environment}",
            "template": """
URGENT: Deployment to {environment} has failed!

Details:
- Environment: {environment}
- Commit: {commit_sha}
- User: {user}
- Time: {timestamp_formatted}

Error Details:
{error_details}

Please investigate immediately.

Dashboard: {dashboard_url}
Logs: {logs_url}
            """.strip()
        },
        "health_check_failure": {
            "subject": "⚠️ Health Check Issues - {environment}",
            "template": """
Health check issues detected in {environment} environment.

Summary:
- Failed Checks: {failed_count}
- Total Checks: {total_count}
- Success Rate: {success_rate}%

Failed Checks:
{failed_checks_list}

Please review and address these issues.

Dashboard: {dashboard_url}
            """.strip()
        },
        "cost_alert": {
            "subject": "💰 Cost Alert - {environment}",
            "template": """
Cost threshold exceeded for {environment} environment.

Details:
- Current Cost: ${current_cost}
- Threshold: ${threshold}
- Period: {period}
- Overage: ${overage}

Please review resource usage and optimize if necessary.

Cost Dashboard: {cost_dashboard_url}
            """.strip()
        }
    }


class NotificationManager:
    """Manages deployment notifications to various channels with intelligent routing."""
    
    def __init__(self):
        # Slack configuration
        self.slack_webhook = os.getenv('SLACK_WEBHOOK_URL')
        self.slack_channel_overrides = {
            "prod": os.getenv('SLACK_PROD_CHANNEL'),
            "staging": os.getenv('SLACK_STAGING_CHANNEL'),
            "dev": os.getenv('SLACK_DEV_CHANNEL')
        }
        
        # Email configuration
        self.smtp_server = os.getenv('SMTP_SERVER', 'localhost')
        self.smtp_port = int(os.getenv('SMTP_PORT', '587'))
        self.smtp_username = os.getenv('SMTP_USERNAME')
        self.smtp_password = os.getenv('SMTP_PASSWORD')
        self.from_email = os.getenv('FROM_EMAIL', 'noreply@company.com')
        
        # Notification routing configuration
        self.notification_emails = {
            "dev": os.getenv('DEV_NOTIFICATION_EMAIL', '').split(','),
            "staging": os.getenv('STAGING_NOTIFICATION_EMAIL', '').split(','),
            "prod": os.getenv('PROD_NOTIFICATION_EMAIL', '').split(','),
            "critical": os.getenv('CRITICAL_NOTIFICATION_EMAIL', '').split(',')
        }
        
        # Clean up empty emails
        for env in self.notification_emails:
            self.notification_emails[env] = [email.strip() for email in self.notification_emails[env] if email.strip()]
        
        # Severity routing
        self.severity_routing = {
            "critical": ["slack", "email"],
            "high": ["slack", "email"],
            "medium": ["slack"],
            "low": ["slack"],
            "info": ["slack"]
        }
        
        self.template = NotificationTemplate()
    
    def send_notification(
        self,
        notification_type: str,
        environment: str,
        data: Dict,
        severity: str = "medium",
        channels: Optional[List[str]] = None
    ) -> Dict[str, bool]:
        """Send notification with intelligent routing based on type, environment, and severity."""
        
        results = {"slack": False, "email": False}
        
        # Determine channels to use
        if channels is None:
            channels = self.severity_routing.get(severity, ["slack"])
        
        # Prepare notification data
        notification_data = self._prepare_notification_data(environment, data)
        
        # Send to each channel
        if "slack" in channels and self.slack_webhook:
            results["slack"] = self._send_slack_notification(
                notification_type, environment, notification_data, severity
            )
        
        if "email" in channels:
            results["email"] = self._send_email_notification(
                notification_type, environment, notification_data, severity
            )
        
        # Always log the notification
        self._log_notification(notification_type, environment, notification_data, severity)
        
        return results
    
    def send_deployment_notification(
        self, 
        environment: str, 
        status: str, 
        commit: str,
        details: Optional[Dict] = None
    ) -> bool:
        """Send deployment notification (legacy method for backward compatibility)."""
        
        notification_type = f"deployment_{status}"
        severity = "critical" if status == "failure" else "medium"
        
        data = {
            "commit_sha": commit,
            "status": status,
            "user": os.getenv('USER', 'unknown'),
        }
        if details:
            data.update(details)
        
        results = self.send_notification(notification_type, environment, data, severity)
        return any(results.values())
    
    def _prepare_notification_data(self, environment: str, data: Dict) -> Dict:
        """Prepare and enrich notification data with common fields."""
        
        enriched_data = {
            "environment": environment.upper(),
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "timestamp_formatted": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"),
        }
        enriched_data.update(data)
        
        # Add formatted fields
        if "commit_sha" in enriched_data:
            enriched_data["commit_short"] = f"`{enriched_data['commit_sha'][:8]}`"
        
        if "duration" in enriched_data:
            duration = enriched_data["duration"]
            if duration < 60:
                enriched_data["duration_formatted"] = f"{duration}s"
            elif duration < 3600:
                enriched_data["duration_formatted"] = f"{duration//60}m {duration%60}s"
            else:
                enriched_data["duration_formatted"] = f"{duration//3600}h {(duration%3600)//60}m"
        
        # Add dashboard URLs
        base_url = os.getenv('DASHBOARD_BASE_URL', 'https://dashboard.company.com')
        enriched_data["dashboard_url"] = f"{base_url}/environments/{environment.lower()}"
        enriched_data["logs_url"] = f"{base_url}/logs/{environment.lower()}"
        enriched_data["cost_dashboard_url"] = f"{base_url}/costs/{environment.lower()}"
        
        return enriched_data
    
    def _send_slack_notification(
        self,
        notification_type: str,
        environment: str,
        data: Dict,
        severity: str
    ) -> bool:
        """Send notification to Slack using templates."""
        
        try:
            template = self.template.SLACK_TEMPLATES.get(notification_type)
            if not template:
                print(f"⚠️ No Slack template found for {notification_type}")
                return False
            
            # Build message
            message = {
                "text": f"{template['emoji']} {template['title']}",
                "attachments": [
                    {
                        "color": template["color"],
                        "fields": []
                    }
                ]
            }
            
            # Add fields from template
            for field_config in template["fields"]:
                field_value = data.get(field_config["key"], "N/A")
                
                # Special handling for certain fields
                if field_config["key"] == "error_summary" and "error" in data:
                    field_value = f"```{str(data['error'])[:500]}```"
                elif field_config["key"] == "failed_count" and "summary" in data:
                    field_value = str(data["summary"].get("failed", 0))
                elif field_config["key"] == "total_count" and "summary" in data:
                    field_value = str(data["summary"].get("total_checks", 0))
                
                message["attachments"][0]["fields"].append({
                    "title": field_config["title"],
                    "value": str(field_value),
                    "short": field_config["short"]
                })
            
            # Add severity indicator for high/critical alerts
            if severity in ["critical", "high"]:
                message["attachments"][0]["fields"].append({
                    "title": "Severity",
                    "value": f"🚨 {severity.upper()}",
                    "short": True
                })
            
            # Determine webhook URL (use environment-specific if available)
            webhook_url = self.slack_channel_overrides.get(environment.lower()) or self.slack_webhook
            
            # Send message
            response = requests.post(webhook_url, json=message, timeout=10)
            response.raise_for_status()
            
            print(f"✅ Slack notification sent successfully to {environment}")
            return True
            
        except Exception as e:
            print(f"❌ Failed to send Slack notification: {e}")
            return False
    
    def _send_email_notification(
        self,
        notification_type: str,
        environment: str,
        data: Dict,
        severity: str
    ) -> bool:
        """Send email notification using templates."""
        
        try:
            template = self.template.EMAIL_TEMPLATES.get(notification_type)
            if not template:
                print(f"⚠️ No email template found for {notification_type}")
                return False
            
            # Determine recipients
            recipients = []
            
            # Add environment-specific recipients
            env_recipients = self.notification_emails.get(environment.lower(), [])
            recipients.extend(env_recipients)
            
            # Add critical recipients for high/critical severity
            if severity in ["critical", "high"]:
                critical_recipients = self.notification_emails.get("critical", [])
                recipients.extend(critical_recipients)
            
            # Remove duplicates
            recipients = list(set(recipients))
            
            if not recipients:
                print(f"⚠️ No email recipients configured for {environment}/{severity}")
                return False
            
            # Prepare email content
            subject = template["subject"].format(**data)
            
            # Prepare additional details for email body
            email_data = data.copy()
            email_data.update({
                "additional_details": self._format_additional_details(data),
                "error_details": self._format_error_details(data),
                "failed_checks_list": self._format_failed_checks(data),
                "success_rate": self._calculate_success_rate(data)
            })
            
            body = template["template"].format(**email_data)
            
            # Create email message
            msg = MIMEMultipart()
            msg['From'] = self.from_email
            msg['To'] = ', '.join(recipients)
            msg['Subject'] = subject
            
            msg.attach(MIMEText(body, 'plain'))
            
            # Send email
            if self.smtp_username and self.smtp_password:
                with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                    server.starttls()
                    server.login(self.smtp_username, self.smtp_password)
                    server.send_message(msg)
            else:
                # Send without authentication (for local SMTP)
                with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                    server.send_message(msg)
            
            print(f"✅ Email notification sent to {len(recipients)} recipients")
            return True
            
        except Exception as e:
            print(f"❌ Failed to send email notification: {e}")
            return False
    
    def _format_additional_details(self, data: Dict) -> str:
        """Format additional details for email body."""
        details = []
        
        if "health_checks" in data:
            hc = data["health_checks"]
            if "summary" in hc:
                details.append(f"Health Checks: {hc['summary'].get('passed', 0)} passed, {hc['summary'].get('failed', 0)} failed")
        
        if "smoke_tests" in data:
            st = data["smoke_tests"]
            if "summary" in st:
                details.append(f"Smoke Tests: {st['summary'].get('passed', 0)} passed, {st['summary'].get('failed', 0)} failed")
        
        if "deployment_metrics" in data:
            dm = data["deployment_metrics"]
            details.append(f"Success Rate: {dm.get('success_rate', 0)}%")
            details.append(f"Recent Deployments: {dm.get('total_deployments', 0)}")
        
        return "\n".join(details) if details else "No additional details available."
    
    def _format_error_details(self, data: Dict) -> str:
        """Format error details for email body."""
        if "error" in data:
            return str(data["error"])
        elif "reason" in data and "details" in data:
            return f"{data['reason']}\n\nDetails: {json.dumps(data['details'], indent=2)}"
        else:
            return "No error details available."
    
    def _format_failed_checks(self, data: Dict) -> str:
        """Format failed checks list for email body."""
        failed_checks = []
        
        if "results" in data:
            for result in data["results"]:
                if result.get("status") == "fail":
                    failed_checks.append(f"- {result.get('service', 'Unknown')}: {result.get('message', 'No message')}")
        
        return "\n".join(failed_checks) if failed_checks else "No failed checks details available."
    
    def _calculate_success_rate(self, data: Dict) -> str:
        """Calculate success rate from data."""
        if "summary" in data:
            summary = data["summary"]
            total = summary.get("total_checks", 0) or summary.get("total_tests", 0)
            passed = summary.get("passed", 0)
            
            if total > 0:
                return f"{(passed / total) * 100:.1f}"
        
        return "N/A"
    
    def send_health_check_alert(self, environment: str, health_results: Dict, severity: str = "high") -> Dict[str, bool]:
        """Send health check failure alert."""
        return self.send_notification("health_check_failure", environment, health_results, severity)
    
    def send_smoke_test_alert(self, environment: str, smoke_results: Dict, severity: str = "high") -> Dict[str, bool]:
        """Send smoke test failure alert."""
        return self.send_notification("smoke_test_failure", environment, smoke_results, severity)
    
    def send_monitoring_alert(self, environment: str, alert_data: Dict, severity: str = "medium") -> Dict[str, bool]:
        """Send general monitoring alert."""
        return self.send_notification("monitoring_alert", environment, alert_data, severity)
    
    def send_cost_alert(self, environment: str, cost_data: Dict, severity: str = "medium") -> Dict[str, bool]:
        """Send cost threshold alert."""
        return self.send_notification("cost_alert", environment, cost_data, severity)
    
    def _log_notification(
        self,
        notification_type: str,
        environment: str,
        data: Dict,
        severity: str
    ):
        """Log notification details."""
        timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
        
        print(f"\n📢 NOTIFICATION SENT")
        print(f"Type: {notification_type}")
        print(f"Environment: {environment.upper()}")
        print(f"Severity: {severity.upper()}")
        print(f"Timestamp: {timestamp}")
        
        # Log key details
        key_fields = ["commit_sha", "status", "user", "duration", "error", "failed_count", "total_count"]
        for field in key_fields:
            if field in data:
                print(f"{field.replace('_', ' ').title()}: {data[field]}")
        
        print()


def main():
    """Main function to handle command line arguments and send notifications."""
    parser = argparse.ArgumentParser(description='Send comprehensive notifications')
    
    # Common arguments
    parser.add_argument('--environment', required=True, 
                       choices=['dev', 'staging', 'prod'],
                       help='Environment')
    parser.add_argument('--severity', choices=['info', 'low', 'medium', 'high', 'critical'],
                       default='medium', help='Notification severity')
    parser.add_argument('--channels', nargs='+', choices=['slack', 'email'],
                       help='Notification channels (default: based on severity)')
    
    # Notification type subcommands
    subparsers = parser.add_subparsers(dest='notification_type', help='Notification type')
    
    # Deployment notification
    deploy_parser = subparsers.add_parser('deployment', help='Deployment notification')
    deploy_parser.add_argument('--status', required=True, choices=['success', 'failure'])
    deploy_parser.add_argument('--commit', required=True, help='Git commit hash')
    deploy_parser.add_argument('--duration', type=int, help='Duration in seconds')
    deploy_parser.add_argument('--error', help='Error message for failures')
    deploy_parser.add_argument('--user', help='User who triggered deployment')
    
    # Health check notification
    health_parser = subparsers.add_parser('health-check', help='Health check notification')
    health_parser.add_argument('--failed-count', type=int, required=True)
    health_parser.add_argument('--total-count', type=int, required=True)
    health_parser.add_argument('--details', help='JSON string with detailed results')
    
    # Smoke test notification
    smoke_parser = subparsers.add_parser('smoke-test', help='Smoke test notification')
    smoke_parser.add_argument('--failed-count', type=int, required=True)
    smoke_parser.add_argument('--total-count', type=int, required=True)
    smoke_parser.add_argument('--details', help='JSON string with detailed results')
    
    # Cost alert notification
    cost_parser = subparsers.add_parser('cost-alert', help='Cost alert notification')
    cost_parser.add_argument('--current-cost', type=float, required=True)
    cost_parser.add_argument('--threshold', type=float, required=True)
    cost_parser.add_argument('--period', required=True, help='Cost period (e.g., "monthly")')
    
    # General monitoring alert
    monitor_parser = subparsers.add_parser('monitoring-alert', help='General monitoring alert')
    monitor_parser.add_argument('--alert-type', required=True, help='Type of alert')
    monitor_parser.add_argument('--message', required=True, help='Alert message')
    monitor_parser.add_argument('--details', help='JSON string with additional details')
    
    args = parser.parse_args()
    
    if not args.notification_type:
        parser.print_help()
        return
    
    # Initialize notification manager
    notifier = NotificationManager()
    
    try:
        # Prepare notification data based on type
        if args.notification_type == 'deployment':
            notification_type = f"deployment_{args.status}"
            data = {
                "commit_sha": args.commit,
                "status": args.status,
                "user": args.user or os.getenv('USER', 'unknown')
            }
            if args.duration:
                data["duration"] = args.duration
            if args.error:
                data["error"] = args.error
        
        elif args.notification_type == 'health-check':
            notification_type = "health_check_failure"
            data = {
                "failed_count": args.failed_count,
                "total_count": args.total_count,
                "summary": {
                    "failed": args.failed_count,
                    "total_checks": args.total_count,
                    "passed": args.total_count - args.failed_count
                }
            }
            if args.details:
                try:
                    data.update(json.loads(args.details))
                except json.JSONDecodeError:
                    print("⚠️ Invalid JSON in details, ignoring")
        
        elif args.notification_type == 'smoke-test':
            notification_type = "smoke_test_failure"
            data = {
                "failed_count": args.failed_count,
                "total_count": args.total_count,
                "summary": {
                    "failed": args.failed_count,
                    "total_tests": args.total_count,
                    "passed": args.total_count - args.failed_count
                }
            }
            if args.details:
                try:
                    data.update(json.loads(args.details))
                except json.JSONDecodeError:
                    print("⚠️ Invalid JSON in details, ignoring")
        
        elif args.notification_type == 'cost-alert':
            notification_type = "cost_alert"
            data = {
                "current_cost": f"{args.current_cost:.2f}",
                "threshold": f"{args.threshold:.2f}",
                "period": args.period,
                "overage": f"{args.current_cost - args.threshold:.2f}"
            }
        
        elif args.notification_type == 'monitoring-alert':
            notification_type = "monitoring_alert"
            data = {
                "alert_type": args.alert_type,
                "alert_details": args.message
            }
            if args.details:
                try:
                    data.update(json.loads(args.details))
                except json.JSONDecodeError:
                    print("⚠️ Invalid JSON in details, ignoring")
        
        # Send notification
        results = notifier.send_notification(
            notification_type,
            args.environment,
            data,
            args.severity,
            args.channels
        )
        
        # Check results
        success_count = sum(1 for success in results.values() if success)
        total_channels = len(results)
        
        if success_count == 0:
            print("❌ All notifications failed to send")
            sys.exit(1)
        elif success_count < total_channels:
            print(f"⚠️ {success_count}/{total_channels} notifications sent successfully")
            sys.exit(1)
        else:
            print(f"✅ All {total_channels} notifications sent successfully")
    
    except Exception as e:
        print(f"❌ Notification failed: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()