#!/usr/bin/env python3
"""
Security Alert Manager
Manages security alerts, automated responses, and incident tracking
"""

import os
import sys
import json
import boto3
import argparse
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import logging
import requests

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class SecurityAlertManager:
    """Manages security alerts and automated responses"""
    
    def __init__(self, aws_region: str = 'us-east-1', environment: str = 'all'):
        self.aws_region = aws_region
        self.environment = environment
        self.logs_client = boto3.client('logs', region_name=aws_region)
        self.iam_client = boto3.client('iam', region_name=aws_region)
        self.sns_client = boto3.client('sns', region_name=aws_region)
        
        # Load configuration
        self.config = self._load_config()
    
    def _load_config(self) -> Dict[str, Any]:
        """Load security configuration"""
        try:
            import yaml
            with open('config/security-config.yaml', 'r') as f:
                return yaml.safe_load(f)
        except Exception as e:
            logger.warning(f"Failed to load security config: {e}")
            return {}
    
    def create_security_incident(self, alert: Dict[str, Any]) -> str:
        """Create a security incident record"""
        incident_id = f"SEC-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{alert.get('severity', 'UNKNOWN')}"
        
        incident = {
            'incident_id': incident_id,
            'created_at': datetime.now().isoformat(),
            'alert_id': alert.get('alert_id', ''),
            'severity': alert.get('severity', 'UNKNOWN'),
            'title': alert.get('title', 'Security Incident'),
            'description': alert.get('description', ''),
            'environment': self.environment,
            'status': 'OPEN',
            'assigned_to': None,
            'events': alert.get('events', []),
            'recommended_actions': alert.get('recommended_actions', []),
            'actions_taken': [],
            'resolution': None,
            'closed_at': None
        }
        
        # Log incident to CloudWatch
        try:
            log_group = f"/aws/security-incidents/{self.environment}"
            log_stream = datetime.now().strftime("%Y/%m/%d")
            
            # Create log group and stream if they don't exist
            try:
                self.logs_client.create_log_group(logGroupName=log_group)
            except self.logs_client.exceptions.ResourceAlreadyExistsException:
                pass
            
            try:
                self.logs_client.create_log_stream(
                    logGroupName=log_group,
                    logStreamName=log_stream
                )
            except self.logs_client.exceptions.ResourceAlreadyExistsException:
                pass
            
            log_event = {
                'timestamp': int(datetime.now().timestamp() * 1000),
                'message': json.dumps(incident)
            }
            
            self.logs_client.put_log_events(
                logGroupName=log_group,
                logStreamName=log_stream,
                logEvents=[log_event]
            )
            
            logger.info(f"Created security incident: {incident_id}")
            
        except Exception as e:
            logger.error(f"Failed to log security incident: {e}")
        
        return incident_id
    
    def send_security_notification(self, alert: Dict[str, Any], incident_id: str = None) -> bool:
        """Send comprehensive security notification"""
        try:
            # Determine notification channels based on severity
            severity = alert.get('severity', 'UNKNOWN')
            
            # Send Slack notification
            slack_sent = self._send_slack_security_alert(alert, incident_id)
            
            # Send email for high/critical alerts
            email_sent = True
            if severity in ['HIGH', 'CRITICAL']:
                email_sent = self._send_email_security_alert(alert, incident_id)
            
            # Send SNS notification for critical alerts
            sns_sent = True
            if severity == 'CRITICAL':
                sns_sent = self._send_sns_alert(alert, incident_id)
            
            return slack_sent and email_sent and sns_sent
            
        except Exception as e:
            logger.error(f"Failed to send security notification: {e}")
            return False
    
    def _send_slack_security_alert(self, alert: Dict[str, Any], incident_id: str = None) -> bool:
        """Send enhanced Slack security alert"""
        webhook_url = os.environ.get('SLACK_WEBHOOK_URL')
        if not webhook_url:
            logger.warning("No Slack webhook URL configured")
            return True
        
        try:
            severity = alert.get('severity', 'UNKNOWN')
            
            # Determine color and emoji based on severity
            severity_config = {
                'CRITICAL': {'color': '#8B0000', 'emoji': '🚨', 'urgency': 'IMMEDIATE ACTION REQUIRED'},
                'HIGH': {'color': '#ff0000', 'emoji': '⚠️', 'urgency': 'ACTION REQUIRED'},
                'MEDIUM': {'color': '#ff9500', 'emoji': '⚡', 'urgency': 'REVIEW NEEDED'},
                'LOW': {'color': '#36a64f', 'emoji': 'ℹ️', 'urgency': 'INFORMATIONAL'}
            }
            
            config = severity_config.get(severity, severity_config['LOW'])
            
            # Create enhanced Slack message
            message = {
                "text": f"{config['emoji']} Security Alert: {alert.get('title', 'Unknown Alert')}",
                "attachments": [
                    {
                        "color": config['color'],
                        "title": f"{config['emoji']} {alert.get('title', 'Security Alert')}",
                        "text": alert.get('description', 'No description available'),
                        "fields": [
                            {
                                "title": "Severity",
                                "value": f"{severity} - {config['urgency']}",
                                "short": True
                            },
                            {
                                "title": "Environment",
                                "value": self.environment,
                                "short": True
                            },
                            {
                                "title": "Alert ID",
                                "value": alert.get('alert_id', 'N/A'),
                                "short": True
                            },
                            {
                                "title": "Events Count",
                                "value": str(len(alert.get('events', []))),
                                "short": True
                            }
                        ],
                        "footer": "Security Monitoring System",
                        "ts": int(datetime.now().timestamp())
                    }
                ]
            }
            
            # Add incident ID if available
            if incident_id:
                message["attachments"][0]["fields"].append({
                    "title": "Incident ID",
                    "value": incident_id,
                    "short": True
                })
            
            # Add recommended actions
            if alert.get('recommended_actions'):
                actions_text = "\n".join([f"• {action}" for action in alert['recommended_actions'][:5]])
                message["attachments"][0]["fields"].append({
                    "title": "Recommended Actions",
                    "value": actions_text,
                    "short": False
                })
            
            # Add event details for critical alerts
            if severity == 'CRITICAL' and alert.get('events'):
                event_details = []
                for event in alert['events'][:3]:  # Show first 3 events
                    if isinstance(event, dict):
                        event_summary = f"• {event.get('event_name', 'Unknown')} from {event.get('source_ip', 'Unknown IP')}"
                        if event.get('user_identity'):
                            event_summary += f" by {event.get('user_identity', 'Unknown User')}"
                        event_details.append(event_summary)
                
                if event_details:
                    message["attachments"][0]["fields"].append({
                        "title": "Event Details",
                        "value": "\n".join(event_details),
                        "short": False
                    })
            
            response = requests.post(webhook_url, json=message, timeout=10)
            return response.status_code == 200
            
        except Exception as e:
            logger.error(f"Failed to send Slack security alert: {e}")
            return False
    
    def _send_email_security_alert(self, alert: Dict[str, Any], incident_id: str = None) -> bool:
        """Send email security alert (placeholder for SES integration)"""
        email = os.environ.get('NOTIFICATION_EMAIL')
        if not email:
            logger.warning("No notification email configured")
            return True
        
        # In a real implementation, integrate with AWS SES
        logger.info(f"Would send email alert to {email}: {alert.get('title', 'Security Alert')}")
        if incident_id:
            logger.info(f"Email would include incident ID: {incident_id}")
        
        return True
    
    def _send_sns_alert(self, alert: Dict[str, Any], incident_id: str = None) -> bool:
        """Send SNS alert for critical security events"""
        try:
            # This would require SNS topic configuration
            topic_arn = os.environ.get('SECURITY_SNS_TOPIC_ARN')
            if not topic_arn:
                logger.warning("No SNS topic configured for security alerts")
                return True
            
            message = {
                'alert_id': alert.get('alert_id', ''),
                'severity': alert.get('severity', 'UNKNOWN'),
                'title': alert.get('title', 'Security Alert'),
                'description': alert.get('description', ''),
                'environment': self.environment,
                'incident_id': incident_id,
                'timestamp': datetime.now().isoformat()
            }
            
            self.sns_client.publish(
                TopicArn=topic_arn,
                Message=json.dumps(message),
                Subject=f"CRITICAL Security Alert: {alert.get('title', 'Unknown')}"
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to send SNS alert: {e}")
            return False
    
    def execute_automated_response(self, alert: Dict[str, Any]) -> List[str]:
        """Execute automated response actions based on alert severity"""
        actions_taken = []
        
        if not self.config.get('automated_response', {}).get('enabled', False):
            logger.info("Automated response is disabled")
            return actions_taken
        
        severity = alert.get('severity', 'UNKNOWN')
        configured_actions = self.config.get('automated_response', {}).get('actions', {}).get(severity.lower(), [])
        
        for action in configured_actions:
            try:
                if action == 'create_incident':
                    incident_id = self.create_security_incident(alert)
                    actions_taken.append(f"Created incident: {incident_id}")
                
                elif action == 'notify_security_team':
                    if self.send_security_notification(alert):
                        actions_taken.append("Notified security team")
                
                elif action == 'log_event':
                    # Already logged as part of normal processing
                    actions_taken.append("Logged security event")
                
                elif action == 'disable_suspicious_access':
                    # This would require careful implementation
                    logger.warning("Automated access disabling not implemented for safety")
                    actions_taken.append("Access disabling skipped (manual review required)")
                
                else:
                    logger.warning(f"Unknown automated action: {action}")
                    
            except Exception as e:
                logger.error(f"Failed to execute automated action {action}: {e}")
                actions_taken.append(f"Failed to execute {action}: {e}")
        
        return actions_taken
    
    def process_security_alert(self, alert: Dict[str, Any]) -> Dict[str, Any]:
        """Process a security alert with full workflow"""
        logger.info(f"Processing security alert: {alert.get('alert_id', 'Unknown')}")
        
        result = {
            'alert_id': alert.get('alert_id', ''),
            'processed_at': datetime.now().isoformat(),
            'incident_created': False,
            'notifications_sent': False,
            'automated_actions': [],
            'status': 'PROCESSED'
        }
        
        try:
            # Create incident for high/critical alerts
            incident_id = None
            if alert.get('severity') in ['HIGH', 'CRITICAL']:
                incident_id = self.create_security_incident(alert)
                result['incident_created'] = True
                result['incident_id'] = incident_id
            
            # Send notifications
            if self.send_security_notification(alert, incident_id):
                result['notifications_sent'] = True
            
            # Execute automated responses
            automated_actions = self.execute_automated_response(alert)
            result['automated_actions'] = automated_actions
            
            logger.info(f"Successfully processed alert: {alert.get('alert_id', 'Unknown')}")
            
        except Exception as e:
            logger.error(f"Failed to process security alert: {e}")
            result['status'] = 'FAILED'
            result['error'] = str(e)
        
        return result
    
    def get_active_incidents(self, days_back: int = 30) -> List[Dict[str, Any]]:
        """Get active security incidents"""
        incidents = []
        
        try:
            log_group = f"/aws/security-incidents/{self.environment}"
            end_time = datetime.now()
            start_time = end_time - timedelta(days=days_back)
            
            # Query CloudWatch Logs for incidents
            response = self.logs_client.filter_log_events(
                logGroupName=log_group,
                startTime=int(start_time.timestamp() * 1000),
                endTime=int(end_time.timestamp() * 1000)
            )
            
            for event in response.get('events', []):
                try:
                    incident = json.loads(event['message'])
                    if incident.get('status') == 'OPEN':
                        incidents.append(incident)
                except Exception as e:
                    logger.warning(f"Failed to parse incident log: {e}")
                    
        except Exception as e:
            logger.error(f"Failed to get active incidents: {e}")
        
        return incidents
    
    def generate_incident_report(self, days_back: int = 30) -> str:
        """Generate incident summary report"""
        incidents = self.get_active_incidents(days_back)
        
        report = f"""# Security Incident Report

**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}
**Environment:** {self.environment}
**Period:** Last {days_back} days

## Summary

**Total Active Incidents:** {len(incidents)}
**Critical Incidents:** {len([i for i in incidents if i.get('severity') == 'CRITICAL'])}
**High Priority Incidents:** {len([i for i in incidents if i.get('severity') == 'HIGH'])}

"""
        
        if incidents:
            report += "## Active Incidents\n\n"
            
            for incident in sorted(incidents, key=lambda x: x.get('created_at', ''), reverse=True):
                report += f"### {incident.get('incident_id', 'Unknown')}\n"
                report += f"**Severity:** {incident.get('severity', 'Unknown')}\n"
                report += f"**Created:** {incident.get('created_at', 'Unknown')}\n"
                report += f"**Title:** {incident.get('title', 'No title')}\n"
                report += f"**Description:** {incident.get('description', 'No description')}\n"
                
                if incident.get('recommended_actions'):
                    report += "**Recommended Actions:**\n"
                    for action in incident['recommended_actions']:
                        report += f"- {action}\n"
                
                report += "\n"
        else:
            report += "## ✅ No Active Incidents\n\nNo open security incidents found.\n\n"
        
        report += """## Next Steps

1. **Review all active incidents**
2. **Assign incidents to appropriate team members**
3. **Take recommended actions**
4. **Update incident status as actions are completed**
5. **Close incidents when resolved**

---
*This report shows active security incidents requiring attention*
"""
        
        return report

def main():
    parser = argparse.ArgumentParser(description="Manage security alerts and incidents")
    parser.add_argument("--region", default="us-east-1", help="AWS region")
    parser.add_argument("--environment", default="all", help="Environment")
    parser.add_argument("--action", choices=['process-alert', 'list-incidents', 'incident-report'], 
                       required=True, help="Action to perform")
    parser.add_argument("--alert-file", help="JSON file containing alert to process")
    parser.add_argument("--days-back", type=int, default=30, help="Days back for incident queries")
    parser.add_argument("--output", help="Output file")
    
    args = parser.parse_args()
    
    # Initialize alert manager
    manager = SecurityAlertManager(args.region, args.environment)
    
    if args.action == 'process-alert':
        if not args.alert_file:
            logger.error("--alert-file required for process-alert action")
            return 1
        
        try:
            with open(args.alert_file, 'r') as f:
                alert = json.load(f)
            
            result = manager.process_security_alert(alert)
            
            output = json.dumps(result, indent=2)
            
        except Exception as e:
            logger.error(f"Failed to process alert: {e}")
            return 1
    
    elif args.action == 'list-incidents':
        incidents = manager.get_active_incidents(args.days_back)
        output = json.dumps(incidents, indent=2)
    
    elif args.action == 'incident-report':
        output = manager.generate_incident_report(args.days_back)
    
    # Output result
    if args.output:
        with open(args.output, 'w') as f:
            f.write(output)
        logger.info(f"Output written to {args.output}")
    else:
        print(output)
    
    return 0

if __name__ == "__main__":
    sys.exit(main())