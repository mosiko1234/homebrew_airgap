#!/usr/bin/env python3
"""
Security Monitoring Script
This script monitors AWS CloudTrail logs and GitHub Actions for suspicious activities
"""

import os
import sys
import json
import boto3
import argparse
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
import requests
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@dataclass
class SecurityEvent:
    """Represents a security event"""
    timestamp: str
    event_type: str
    severity: str  # LOW, MEDIUM, HIGH, CRITICAL
    source: str
    user_identity: str
    event_name: str
    source_ip: str
    user_agent: str
    details: Dict[str, Any]
    risk_score: int  # 1-100

@dataclass
class SecurityAlert:
    """Represents a security alert"""
    alert_id: str
    timestamp: str
    severity: str
    title: str
    description: str
    events: List[SecurityEvent]
    recommended_actions: List[str]

class SecurityMonitor:
    """Main security monitoring class"""
    
    def __init__(self, aws_region: str = 'us-east-1', environment: str = 'all', config_file: str = 'config/security-config.yaml'):
        self.aws_region = aws_region
        self.environment = environment
        self.cloudtrail_client = boto3.client('cloudtrail', region_name=aws_region)
        self.iam_client = boto3.client('iam', region_name=aws_region)
        self.logs_client = boto3.client('logs', region_name=aws_region)
        
        # Load configuration
        self.config = self._load_config(config_file)
        
        # Security rules configuration
        self.security_rules = self.config.get('thresholds', {})
        
        # Suspicious patterns from config
        self.suspicious_patterns = self.config.get('patterns', {})
    
    def _load_config(self, config_file: str) -> Dict[str, Any]:
        """Load security monitoring configuration"""
        try:
            import yaml
            with open(config_file, 'r') as f:
                return yaml.safe_load(f)
        except Exception as e:
            logger.warning(f"Failed to load config file {config_file}: {e}")
            # Return default configuration
            return {
                'thresholds': {
                    'failed_login_attempts': 5,
                    'unusual_location_threshold': 3,
                    'high_privilege_action_threshold': 10,
                    'time_window_minutes': 60,
                    'api_calls_per_minute_threshold': 100,
                    'suspicious_ip_threshold': 3
                },
                'patterns': {
                    'high_risk_actions': [
                        'CreateUser', 'DeleteUser', 'AttachUserPolicy', 'DetachUserPolicy',
                        'CreateAccessKey', 'DeleteAccessKey', 'CreateRole', 'DeleteRole',
                        'PutRolePolicy', 'DeleteRolePolicy'
                    ],
                    'suspicious_user_agents': ['curl', 'wget', 'python-requests', 'boto3'],
                    'unusual_times': {'start_hour': 22, 'end_hour': 6}
                }
            }
    
    def get_cloudtrail_events(self, start_time: datetime, end_time: datetime) -> List[Dict]:
        """Retrieve CloudTrail events for the specified time range"""
        try:
            response = self.cloudtrail_client.lookup_events(
                LookupAttributes=[
                    {
                        'AttributeKey': 'EventName',
                        'AttributeValue': 'AssumeRoleWithWebIdentity'
                    }
                ],
                StartTime=start_time,
                EndTime=end_time,
                MaxItems=1000
            )
            
            events = response.get('Events', [])
            
            # Get additional high-risk events
            high_risk_events = []
            for action in self.suspicious_patterns['high_risk_actions']:
                try:
                    response = self.cloudtrail_client.lookup_events(
                        LookupAttributes=[
                            {
                                'AttributeKey': 'EventName',
                                'AttributeValue': action
                            }
                        ],
                        StartTime=start_time,
                        EndTime=end_time,
                        MaxItems=100
                    )
                    high_risk_events.extend(response.get('Events', []))
                except Exception as e:
                    logger.warning(f"Failed to get events for {action}: {e}")
            
            events.extend(high_risk_events)
            return events
            
        except Exception as e:
            logger.error(f"Failed to retrieve CloudTrail events: {e}")
            return []
    
    def analyze_event(self, event: Dict) -> Optional[SecurityEvent]:
        """Analyze a single CloudTrail event for security issues"""
        try:
            event_time = event.get('EventTime', datetime.now())
            event_name = event.get('EventName', '')
            source_ip = event.get('SourceIPAddress', '')
            user_agent = event.get('UserAgent', '')
            user_identity = event.get('UserIdentity', {})
            
            # Calculate risk score
            risk_score = self._calculate_risk_score(event)
            
            # Determine severity
            severity = self._determine_severity(risk_score)
            
            # Skip low-risk events unless they're part of a pattern
            if risk_score < 30 and severity == 'LOW':
                return None
            
            return SecurityEvent(
                timestamp=event_time.isoformat() if isinstance(event_time, datetime) else str(event_time),
                event_type='aws_api_call',
                severity=severity,
                source='cloudtrail',
                user_identity=json.dumps(user_identity),
                event_name=event_name,
                source_ip=source_ip,
                user_agent=user_agent,
                details=event,
                risk_score=risk_score
            )
            
        except Exception as e:
            logger.error(f"Failed to analyze event: {e}")
            return None
    
    def _calculate_risk_score(self, event: Dict) -> int:
        """Calculate risk score for an event (1-100)"""
        score = 0
        
        event_name = event.get('EventName', '')
        source_ip = event.get('SourceIPAddress', '')
        user_agent = event.get('UserAgent', '')
        event_time = event.get('EventTime', datetime.now())
        user_identity = event.get('UserIdentity', {})
        
        # High-risk actions
        if event_name in self.suspicious_patterns.get('high_risk_actions', []):
            score += self.config.get('risk_scoring', {}).get('high_risk_actions_score', 40)
        
        # Suspicious user agents
        for suspicious_ua in self.suspicious_patterns['suspicious_user_agents']:
            if suspicious_ua.lower() in user_agent.lower():
                score += 20
                break
        
        # Unusual times (outside business hours)
        if isinstance(event_time, datetime):
            hour = event_time.hour
            if (hour >= self.suspicious_patterns['unusual_times']['start_hour'] or 
                hour <= self.suspicious_patterns['unusual_times']['end_hour']):
                score += 15
        
        # Failed events
        error_code = event.get('ErrorCode')
        if error_code:
            score += 25
        
        # Root user activity
        if user_identity.get('type') == 'Root':
            score += 30
        
        # Multiple rapid calls (if we can detect this pattern)
        # This would require additional logic to track call frequency
        
        # Geographic anomalies (placeholder - would need IP geolocation)
        # if self._is_unusual_location(source_ip):
        #     score += 20
        
        return min(score, 100)
    
    def _determine_severity(self, risk_score: int) -> str:
        """Determine severity based on risk score"""
        if risk_score >= 80:
            return 'CRITICAL'
        elif risk_score >= 60:
            return 'HIGH'
        elif risk_score >= 40:
            return 'MEDIUM'
        else:
            return 'LOW'
    
    def detect_patterns(self, events: List[SecurityEvent]) -> List[SecurityAlert]:
        """Detect suspicious patterns in security events"""
        alerts = []
        
        # Group events by various criteria
        events_by_ip = {}
        events_by_user = {}
        events_by_user_agent = {}
        failed_events = []
        
        for event in events:
            # Group by IP
            ip = event.source_ip
            if ip not in events_by_ip:
                events_by_ip[ip] = []
            events_by_ip[ip].append(event)
            
            # Group by user
            user = event.user_identity
            if user not in events_by_user:
                events_by_user[user] = []
            events_by_user[user].append(event)
            
            # Group by user agent
            ua = event.user_agent
            if ua not in events_by_user_agent:
                events_by_user_agent[ua] = []
            events_by_user_agent[ua].append(event)
            
            # Collect failed events
            if 'error' in event.details.get('ErrorCode', '').lower():
                failed_events.append(event)
        
        # Detect multiple failed attempts from same IP
        for ip, ip_events in events_by_ip.items():
            failed_from_ip = [e for e in ip_events if 'error' in e.details.get('ErrorCode', '').lower()]
            if len(failed_from_ip) >= self.security_rules.get('failed_login_attempts', 5):
                alerts.append(SecurityAlert(
                    alert_id=f"failed_attempts_{ip}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                    timestamp=datetime.now().isoformat(),
                    severity='HIGH',
                    title=f"Multiple Failed Attempts from {ip}",
                    description=f"Detected {len(failed_from_ip)} failed attempts from IP {ip}",
                    events=failed_from_ip,
                    recommended_actions=[
                        f"Block IP address {ip} if not legitimate",
                        "Review access logs for this IP",
                        "Check if this is a legitimate user having issues",
                        "Consider implementing rate limiting"
                    ]
                ))
        
        # Detect unusual high-privilege activity
        high_priv_events = [e for e in events if e.event_name in self.suspicious_patterns.get('high_risk_actions', [])]
        if len(high_priv_events) >= self.security_rules.get('high_privilege_action_threshold', 10):
            alerts.append(SecurityAlert(
                alert_id=f"high_priv_activity_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                timestamp=datetime.now().isoformat(),
                severity='CRITICAL',
                title="Unusual High-Privilege Activity Detected",
                description=f"Detected {len(high_priv_events)} high-privilege actions in monitoring window",
                events=high_priv_events,
                recommended_actions=[
                    "Review all high-privilege actions for legitimacy",
                    "Verify user identities and authorization",
                    "Check for compromised credentials",
                    "Consider temporary access restrictions"
                ]
            ))
        
        # Detect rapid API calls (potential automation/attack)
        for user, user_events in events_by_user.items():
            if len(user_events) >= self.security_rules.get('api_calls_per_minute_threshold', 100):
                alerts.append(SecurityAlert(
                    alert_id=f"rapid_calls_{user.replace('/', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                    timestamp=datetime.now().isoformat(),
                    severity='MEDIUM',
                    title=f"Rapid API Calls from {user}",
                    description=f"User {user} made {len(user_events)} API calls in monitoring window",
                    events=user_events,
                    recommended_actions=[
                        "Verify if this is legitimate automation",
                        "Check for compromised credentials",
                        "Review API call patterns",
                        "Consider implementing rate limiting"
                    ]
                ))
        
        # Detect suspicious user agents
        for ua, ua_events in events_by_user_agent.items():
            suspicious_ua_events = [e for e in ua_events if any(sus_ua in ua.lower() for sus_ua in self.suspicious_patterns.get('suspicious_user_agents', []))]
            if len(suspicious_ua_events) >= self.security_rules.get('suspicious_ip_threshold', 3):
                alerts.append(SecurityAlert(
                    alert_id=f"suspicious_ua_{ua.replace('/', '_').replace(' ', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                    timestamp=datetime.now().isoformat(),
                    severity='MEDIUM',
                    title=f"Suspicious User Agent Activity",
                    description=f"Detected {len(suspicious_ua_events)} events from suspicious user agent: {ua}",
                    events=suspicious_ua_events,
                    recommended_actions=[
                        "Investigate the source of these requests",
                        "Verify if this is legitimate automation",
                        "Check for unauthorized access attempts",
                        "Consider blocking suspicious user agents"
                    ]
                ))
        
        # Detect unauthorized access patterns
        unauthorized_events = []
        for event in events:
            # Check for access from unusual locations (placeholder - would need IP geolocation)
            # Check for access outside business hours
            event_time = datetime.fromisoformat(event.timestamp.replace('Z', '+00:00'))
            hour = event_time.hour
            unusual_times = self.suspicious_patterns.get('unusual_times', {})
            if (hour >= unusual_times.get('start_hour', 22) or 
                hour <= unusual_times.get('end_hour', 6)):
                unauthorized_events.append(event)
        
        if len(unauthorized_events) >= self.security_rules.get('unusual_location_threshold', 3):
            alerts.append(SecurityAlert(
                alert_id=f"unauthorized_access_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                timestamp=datetime.now().isoformat(),
                severity='HIGH',
                title="Potential Unauthorized Access Detected",
                description=f"Detected {len(unauthorized_events)} access attempts outside normal business hours",
                events=unauthorized_events,
                recommended_actions=[
                    "Review all after-hours access attempts",
                    "Verify user identities and authorization",
                    "Check for compromised credentials",
                    "Implement time-based access controls if needed"
                ]
            ))
        
        return alerts
    
    def check_iam_compliance(self) -> List[SecurityAlert]:
        """Check IAM configuration for compliance issues"""
        alerts = []
        
        try:
            # Check for users with direct policies (should use roles)
            users_response = self.iam_client.list_users()
            users_with_policies = []
            users_with_old_keys = []
            users_with_multiple_keys = []
            
            for user in users_response.get('Users', []):
                user_name = user['UserName']
                
                # Check for attached policies
                attached_policies = self.iam_client.list_attached_user_policies(UserName=user_name)
                inline_policies = self.iam_client.list_user_policies(UserName=user_name)
                
                if (attached_policies.get('AttachedPolicies') or 
                    inline_policies.get('PolicyNames')):
                    users_with_policies.append(user_name)
                
                # Check access keys
                try:
                    access_keys = self.iam_client.list_access_keys(UserName=user_name)
                    keys = access_keys.get('AccessKeyMetadata', [])
                    
                    if len(keys) > 1:
                        users_with_multiple_keys.append(user_name)
                    
                    # Check key age
                    for key in keys:
                        key_age = datetime.now(key['CreateDate'].tzinfo) - key['CreateDate']
                        if key_age.days > self.config.get('iam_compliance', {}).get('access_key_rotation_days', 90):
                            users_with_old_keys.append(f"{user_name} ({key_age.days} days)")
                            
                except Exception as e:
                    logger.warning(f"Failed to check access keys for user {user_name}: {e}")
            
            if users_with_policies:
                alerts.append(SecurityAlert(
                    alert_id=f"iam_compliance_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                    timestamp=datetime.now().isoformat(),
                    severity='MEDIUM',
                    title="IAM Users with Direct Policies Detected",
                    description=f"Found {len(users_with_policies)} users with direct policy attachments",
                    events=[],
                    recommended_actions=[
                        "Review users with direct policies",
                        "Consider using roles instead of user policies",
                        "Implement principle of least privilege",
                        f"Users to review: {', '.join(users_with_policies)}"
                    ]
                ))
            
            if users_with_multiple_keys:
                alerts.append(SecurityAlert(
                    alert_id=f"multiple_keys_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                    timestamp=datetime.now().isoformat(),
                    severity='MEDIUM',
                    title="Users with Multiple Access Keys",
                    description=f"Found {len(users_with_multiple_keys)} users with multiple access keys",
                    events=[],
                    recommended_actions=[
                        "Review users with multiple access keys",
                        "Remove unused access keys",
                        "Implement key rotation policies",
                        f"Users to review: {', '.join(users_with_multiple_keys)}"
                    ]
                ))
            
            if users_with_old_keys:
                alerts.append(SecurityAlert(
                    alert_id=f"old_keys_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                    timestamp=datetime.now().isoformat(),
                    severity='HIGH',
                    title="Old Access Keys Detected",
                    description=f"Found {len(users_with_old_keys)} users with old access keys",
                    events=[],
                    recommended_actions=[
                        "Rotate old access keys immediately",
                        "Implement automated key rotation",
                        "Review key usage patterns",
                        f"Keys to rotate: {', '.join(users_with_old_keys)}"
                    ]
                ))
            
            # Check for overly permissive roles
            roles_response = self.iam_client.list_roles()
            overly_permissive_roles = []
            roles_without_boundaries = []
            
            for role in roles_response.get('Roles', []):
                role_name = role['RoleName']
                
                # Skip AWS service roles
                if role_name.startswith('aws-'):
                    continue
                
                # Check for permission boundaries
                if not role.get('PermissionsBoundary') and self.config.get('github_actions', {}).get('require_permission_boundary', False):
                    roles_without_boundaries.append(role_name)
                
                # Check attached policies
                attached_policies = self.iam_client.list_attached_role_policies(RoleName=role_name)
                
                prohibited_policies = self.config.get('iam_compliance', {}).get('prohibited_policies', [])
                for policy in attached_policies.get('AttachedPolicies', []):
                    if (policy['PolicyName'] in ['PowerUserAccess', 'AdministratorAccess'] or
                        policy['PolicyArn'] in prohibited_policies):
                        overly_permissive_roles.append(role_name)
                        break
            
            if overly_permissive_roles:
                alerts.append(SecurityAlert(
                    alert_id=f"permissive_roles_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                    timestamp=datetime.now().isoformat(),
                    severity='HIGH',
                    title="Overly Permissive IAM Roles Detected",
                    description=f"Found {len(overly_permissive_roles)} roles with broad permissions",
                    events=[],
                    recommended_actions=[
                        "Review roles with broad permissions",
                        "Implement principle of least privilege",
                        "Create specific policies for each role's needs",
                        f"Roles to review: {', '.join(overly_permissive_roles)}"
                    ]
                ))
            
            if roles_without_boundaries:
                alerts.append(SecurityAlert(
                    alert_id=f"no_boundaries_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                    timestamp=datetime.now().isoformat(),
                    severity='MEDIUM',
                    title="Roles Without Permission Boundaries",
                    description=f"Found {len(roles_without_boundaries)} roles without permission boundaries",
                    events=[],
                    recommended_actions=[
                        "Add permission boundaries to roles",
                        "Review role trust policies",
                        "Implement defense in depth",
                        f"Roles to update: {', '.join(roles_without_boundaries)}"
                    ]
                ))
                
        except Exception as e:
            logger.error(f"Failed to check IAM compliance: {e}")
        
        return alerts
    
    def send_alert(self, alert: SecurityAlert) -> bool:
        """Send security alert via configured channels"""
        try:
            # Send to Slack
            slack_success = self._send_slack_alert(alert)
            
            # Send email for high/critical alerts
            email_success = True
            if alert.severity in ['HIGH', 'CRITICAL']:
                email_success = self._send_email_alert(alert)
            
            # Log to CloudWatch (if configured)
            cloudwatch_success = self._log_to_cloudwatch(alert)
            
            return slack_success and email_success and cloudwatch_success
            
        except Exception as e:
            logger.error(f"Failed to send alert: {e}")
            return False
    
    def _send_slack_alert(self, alert: SecurityAlert) -> bool:
        """Send alert to Slack"""
        webhook_url = os.environ.get('SLACK_WEBHOOK_URL')
        if not webhook_url:
            logger.warning("No Slack webhook URL configured")
            return True  # Not a failure if not configured
        
        try:
            # Determine color based on severity
            color_map = {
                'LOW': '#36a64f',      # Green
                'MEDIUM': '#ff9500',   # Orange
                'HIGH': '#ff0000',     # Red
                'CRITICAL': '#8B0000'  # Dark Red
            }
            
            color = color_map.get(alert.severity, '#36a64f')
            
            # Create Slack message
            message = {
                "text": f"🚨 Security Alert: {alert.title}",
                "attachments": [
                    {
                        "color": color,
                        "title": alert.title,
                        "text": alert.description,
                        "fields": [
                            {
                                "title": "Severity",
                                "value": alert.severity,
                                "short": True
                            },
                            {
                                "title": "Alert ID",
                                "value": alert.alert_id,
                                "short": True
                            },
                            {
                                "title": "Events Count",
                                "value": str(len(alert.events)),
                                "short": True
                            },
                            {
                                "title": "Environment",
                                "value": self.environment,
                                "short": True
                            }
                        ],
                        "footer": "Security Monitor",
                        "ts": int(datetime.now().timestamp())
                    }
                ]
            }
            
            # Add recommended actions
            if alert.recommended_actions:
                actions_text = "\n".join([f"• {action}" for action in alert.recommended_actions])
                message["attachments"][0]["fields"].append({
                    "title": "Recommended Actions",
                    "value": actions_text,
                    "short": False
                })
            
            response = requests.post(webhook_url, json=message, timeout=10)
            return response.status_code == 200
            
        except Exception as e:
            logger.error(f"Failed to send Slack alert: {e}")
            return False
    
    def _send_email_alert(self, alert: SecurityAlert) -> bool:
        """Send alert via email (placeholder implementation)"""
        email = os.environ.get('NOTIFICATION_EMAIL')
        if not email:
            logger.warning("No notification email configured")
            return True
        
        # In a real implementation, you would integrate with SES or another email service
        logger.info(f"Would send email alert to {email}: {alert.title}")
        return True
    
    def _log_to_cloudwatch(self, alert: SecurityAlert) -> bool:
        """Log alert to CloudWatch"""
        try:
            log_group = f"/aws/security-monitor/{self.environment}"
            log_stream = datetime.now().strftime("%Y/%m/%d")
            
            # Create log group if it doesn't exist
            try:
                self.logs_client.create_log_group(logGroupName=log_group)
            except self.logs_client.exceptions.ResourceAlreadyExistsException:
                pass
            
            # Create log stream if it doesn't exist
            try:
                self.logs_client.create_log_stream(
                    logGroupName=log_group,
                    logStreamName=log_stream
                )
            except self.logs_client.exceptions.ResourceAlreadyExistsException:
                pass
            
            # Send log event
            log_event = {
                'timestamp': int(datetime.now().timestamp() * 1000),
                'message': json.dumps(asdict(alert))
            }
            
            self.logs_client.put_log_events(
                logGroupName=log_group,
                logStreamName=log_stream,
                logEvents=[log_event]
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to log to CloudWatch: {e}")
            return False
    
    def log_access_attempt(self, event: Dict, risk_level: str = 'INFO') -> bool:
        """Log access attempts with detailed information for audit trail"""
        try:
            access_log = {
                'timestamp': datetime.now().isoformat(),
                'event_time': event.get('EventTime', '').isoformat() if isinstance(event.get('EventTime'), datetime) else str(event.get('EventTime', '')),
                'event_name': event.get('EventName', ''),
                'source_ip': event.get('SourceIPAddress', ''),
                'user_agent': event.get('UserAgent', ''),
                'user_identity': event.get('UserIdentity', {}),
                'aws_region': event.get('AwsRegion', ''),
                'error_code': event.get('ErrorCode', ''),
                'error_message': event.get('ErrorMessage', ''),
                'risk_level': risk_level,
                'environment': self.environment,
                'request_parameters': event.get('RequestParameters', {}),
                'response_elements': event.get('ResponseElements', {}),
                'resources': event.get('Resources', [])
            }
            
            # Log to CloudWatch for audit trail
            log_group = f"/aws/security-access-logs/{self.environment}"
            log_stream = datetime.now().strftime("%Y/%m/%d")
            
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
                'message': json.dumps(access_log)
            }
            
            self.logs_client.put_log_events(
                logGroupName=log_group,
                logStreamName=log_stream,
                logEvents=[log_event]
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to log access attempt: {e}")
            return False
    
    def detect_suspicious_activity(self, events: List[SecurityEvent]) -> List[SecurityAlert]:
        """Advanced suspicious activity detection"""
        alerts = []
        
        # Analyze GitHub Actions specific patterns
        github_events = [e for e in events if 'github' in e.user_identity.lower() or 'AssumeRoleWithWebIdentity' in e.event_name]
        
        if github_events:
            # Check for unauthorized repositories
            allowed_repos = self.config.get('github_actions', {}).get('allowed_repositories', [])
            unauthorized_repo_events = []
            
            for event in github_events:
                try:
                    request_params = event.details.get('RequestParameters', {})
                    web_identity_token = request_params.get('WebIdentityToken', '')
                    
                    # In a real implementation, you would decode the JWT token to get repository info
                    # For now, we'll check based on user identity patterns
                    user_identity = json.loads(event.user_identity) if isinstance(event.user_identity, str) else event.user_identity
                    
                    # Check if this looks like an unauthorized repository access
                    if user_identity.get('type') == 'WebIdentityUser':
                        # This is a simplified check - in production you'd decode the JWT
                        unauthorized_repo_events.append(event)
                        
                except Exception as e:
                    logger.warning(f"Failed to analyze GitHub event: {e}")
            
            if unauthorized_repo_events:
                alerts.append(SecurityAlert(
                    alert_id=f"unauthorized_github_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                    timestamp=datetime.now().isoformat(),
                    severity='CRITICAL',
                    title="Potential Unauthorized GitHub Actions Access",
                    description=f"Detected {len(unauthorized_repo_events)} potentially unauthorized GitHub Actions access attempts",
                    events=unauthorized_repo_events,
                    recommended_actions=[
                        "Review GitHub Actions OIDC trust policies",
                        "Verify repository access permissions",
                        "Check for compromised GitHub tokens",
                        "Review allowed repository list in configuration"
                    ]
                ))
        
        # Detect privilege escalation attempts
        escalation_events = []
        for event in events:
            if event.event_name in ['AttachUserPolicy', 'AttachRolePolicy', 'PutUserPolicy', 'PutRolePolicy']:
                # Check if this is adding high-privilege policies
                try:
                    request_params = event.details.get('RequestParameters', {})
                    policy_arn = request_params.get('PolicyArn', '')
                    policy_name = request_params.get('PolicyName', '')
                    
                    if ('Admin' in policy_arn or 'Admin' in policy_name or 
                        'PowerUser' in policy_arn or 'PowerUser' in policy_name):
                        escalation_events.append(event)
                        
                except Exception as e:
                    logger.warning(f"Failed to analyze privilege escalation event: {e}")
        
        if escalation_events:
            alerts.append(SecurityAlert(
                alert_id=f"privilege_escalation_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                timestamp=datetime.now().isoformat(),
                severity='CRITICAL',
                title="Potential Privilege Escalation Detected",
                description=f"Detected {len(escalation_events)} potential privilege escalation attempts",
                events=escalation_events,
                recommended_actions=[
                    "Immediately review all privilege changes",
                    "Verify authorization for privilege escalations",
                    "Check for compromised credentials",
                    "Consider revoking elevated privileges temporarily"
                ]
            ))
        
        # Detect data exfiltration patterns
        exfiltration_events = []
        for event in events:
            if event.event_name in ['GetObject', 'ListBucket', 'GetBucketLocation']:
                # Check for unusual data access patterns
                if event.risk_score > 60:  # High risk data access
                    exfiltration_events.append(event)
        
        if len(exfiltration_events) >= 10:  # Threshold for potential data exfiltration
            alerts.append(SecurityAlert(
                alert_id=f"data_exfiltration_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                timestamp=datetime.now().isoformat(),
                severity='HIGH',
                title="Potential Data Exfiltration Activity",
                description=f"Detected {len(exfiltration_events)} high-risk data access events",
                events=exfiltration_events,
                recommended_actions=[
                    "Review all data access patterns",
                    "Check for unauthorized data downloads",
                    "Verify user authorization for data access",
                    "Consider implementing data loss prevention controls"
                ]
            ))
        
        return alerts
    
    def generate_compliance_report(self) -> Dict[str, Any]:
        """Generate comprehensive compliance report"""
        report = {
            'timestamp': datetime.now().isoformat(),
            'environment': self.environment,
            'compliance_frameworks': {},
            'findings': [],
            'recommendations': []
        }
        
        # SOC 2 compliance checks
        if self.config.get('compliance', {}).get('soc2', {}).get('enabled', False):
            soc2_findings = []
            
            # Check access logging
            try:
                log_groups = self.logs_client.describe_log_groups(
                    logGroupNamePrefix=f"/aws/security-access-logs/{self.environment}"
                )
                if not log_groups.get('logGroups'):
                    soc2_findings.append("Access logging not properly configured")
            except Exception as e:
                soc2_findings.append(f"Unable to verify access logging: {e}")
            
            report['compliance_frameworks']['soc2'] = {
                'status': 'COMPLIANT' if not soc2_findings else 'NON_COMPLIANT',
                'findings': soc2_findings
            }
        
        # Custom compliance checks
        if self.config.get('compliance', {}).get('custom', {}).get('enabled', False):
            custom_findings = []
            
            # Check GitHub Actions monitoring
            if not os.environ.get('SLACK_WEBHOOK_URL'):
                custom_findings.append("Slack notifications not configured for security alerts")
            
            # Check IAM compliance
            try:
                iam_alerts = self.check_iam_compliance()
                if iam_alerts:
                    custom_findings.extend([f"IAM Issue: {alert.title}" for alert in iam_alerts])
            except Exception as e:
                custom_findings.append(f"Unable to check IAM compliance: {e}")
            
            report['compliance_frameworks']['custom'] = {
                'status': 'COMPLIANT' if not custom_findings else 'NON_COMPLIANT',
                'findings': custom_findings
            }
        
        # Generate recommendations
        if report['compliance_frameworks']:
            all_findings = []
            for framework in report['compliance_frameworks'].values():
                all_findings.extend(framework.get('findings', []))
            
            if all_findings:
                report['recommendations'] = [
                    "Address all compliance findings immediately",
                    "Implement automated compliance monitoring",
                    "Regular security training for team members",
                    "Review and update security policies quarterly"
                ]
        
        return report
    
    def run_monitoring_cycle(self, hours_back: int = 1) -> Dict[str, Any]:
        """Run a complete monitoring cycle"""
        logger.info(f"Starting security monitoring cycle for last {hours_back} hours")
        
        # Calculate time range
        end_time = datetime.now()
        start_time = end_time - timedelta(hours=hours_back)
        
        # Get CloudTrail events
        logger.info("Retrieving CloudTrail events...")
        raw_events = self.get_cloudtrail_events(start_time, end_time)
        logger.info(f"Retrieved {len(raw_events)} raw events")
        
        # Log all access attempts for audit trail
        logger.info("Logging access attempts...")
        logged_events = 0
        for raw_event in raw_events:
            risk_level = 'HIGH' if raw_event.get('ErrorCode') else 'INFO'
            if self.log_access_attempt(raw_event, risk_level):
                logged_events += 1
        
        # Analyze events
        logger.info("Analyzing events for security issues...")
        security_events = []
        for raw_event in raw_events:
            analyzed_event = self.analyze_event(raw_event)
            if analyzed_event:
                security_events.append(analyzed_event)
        
        logger.info(f"Identified {len(security_events)} security events")
        
        # Detect patterns and generate alerts
        logger.info("Detecting suspicious patterns...")
        pattern_alerts = self.detect_patterns(security_events)
        
        # Advanced suspicious activity detection
        logger.info("Running advanced suspicious activity detection...")
        suspicious_alerts = self.detect_suspicious_activity(security_events)
        
        # Check IAM compliance
        logger.info("Checking IAM compliance...")
        compliance_alerts = self.check_iam_compliance()
        
        # Generate compliance report
        logger.info("Generating compliance report...")
        compliance_report = self.generate_compliance_report()
        
        all_alerts = pattern_alerts + suspicious_alerts + compliance_alerts
        logger.info(f"Generated {len(all_alerts)} security alerts")
        
        # Send alerts
        sent_alerts = 0
        for alert in all_alerts:
            if self.send_alert(alert):
                sent_alerts += 1
        
        logger.info(f"Successfully sent {sent_alerts}/{len(all_alerts)} alerts")
        
        # Return summary
        return {
            'monitoring_period': {
                'start_time': start_time.isoformat(),
                'end_time': end_time.isoformat(),
                'hours_back': hours_back
            },
            'events_analyzed': len(raw_events),
            'access_attempts_logged': logged_events,
            'security_events_identified': len(security_events),
            'alerts_generated': len(all_alerts),
            'alerts_sent': sent_alerts,
            'compliance_report': compliance_report,
            'alerts': [asdict(alert) for alert in all_alerts]
        }

def main():
    parser = argparse.ArgumentParser(description="Security monitoring for AWS and GitHub Actions")
    parser.add_argument("--region", default="us-east-1", help="AWS region")
    parser.add_argument("--environment", default="all", help="Environment to monitor")
    parser.add_argument("--hours-back", type=int, default=1, help="Hours of history to analyze")
    parser.add_argument("--output", help="Output file for results (JSON)")
    parser.add_argument("--verbose", action="store_true", help="Verbose logging")
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Initialize security monitor
    monitor = SecurityMonitor(args.region, args.environment)
    
    # Run monitoring cycle
    results = monitor.run_monitoring_cycle(args.hours_back)
    
    # Output results
    if args.output:
        with open(args.output, 'w') as f:
            json.dump(results, f, indent=2)
        logger.info(f"Results written to {args.output}")
    else:
        print(json.dumps(results, indent=2))
    
    # Exit with error code if critical alerts were generated
    critical_alerts = [a for a in results['alerts'] if a['severity'] == 'CRITICAL']
    if critical_alerts:
        logger.error(f"Generated {len(critical_alerts)} critical security alerts")
        sys.exit(1)
    
    logger.info("Security monitoring completed successfully")
    return 0

if __name__ == "__main__":
    sys.exit(main())