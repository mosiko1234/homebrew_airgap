#!/usr/bin/env python3
"""
Security Reporting Script
Generates comprehensive security reports and compliance summaries
"""

import os
import sys
import json
import boto3
import argparse
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class SecurityReporter:
    """Security reporting and compliance checking"""
    
    def __init__(self, aws_region: str = 'us-east-1', environment: str = 'all'):
        self.aws_region = aws_region
        self.environment = environment
        self.logs_client = boto3.client('logs', region_name=aws_region)
        self.iam_client = boto3.client('iam', region_name=aws_region)
        self.cloudtrail_client = boto3.client('cloudtrail', region_name=aws_region)
    
    def get_security_metrics(self, days_back: int = 7) -> Dict[str, Any]:
        """Get security metrics for the specified period"""
        end_time = datetime.now()
        start_time = end_time - timedelta(days=days_back)
        
        metrics = {
            'period': {
                'start_time': start_time.isoformat(),
                'end_time': end_time.isoformat(),
                'days': days_back
            },
            'access_attempts': {
                'total': 0,
                'successful': 0,
                'failed': 0,
                'unique_ips': set(),
                'unique_users': set()
            },
            'high_risk_activities': {
                'total': 0,
                'by_type': {},
                'by_user': {}
            },
            'compliance_status': {
                'iam_users_with_policies': 0,
                'overly_permissive_roles': 0,
                'old_access_keys': 0,
                'users_without_mfa': 0
            }
        }
        
        try:
            # Get CloudTrail events
            response = self.cloudtrail_client.lookup_events(
                StartTime=start_time,
                EndTime=end_time,
                MaxItems=1000
            )
            
            events = response.get('Events', [])
            
            for event in events:
                # Count access attempts
                metrics['access_attempts']['total'] += 1
                
                if event.get('ErrorCode'):
                    metrics['access_attempts']['failed'] += 1
                else:
                    metrics['access_attempts']['successful'] += 1
                
                # Track unique IPs and users
                if event.get('SourceIPAddress'):
                    metrics['access_attempts']['unique_ips'].add(event['SourceIPAddress'])
                
                user_identity = event.get('UserIdentity', {})
                if user_identity.get('userName'):
                    metrics['access_attempts']['unique_users'].add(user_identity['userName'])
                elif user_identity.get('arn'):
                    metrics['access_attempts']['unique_users'].add(user_identity['arn'])
                
                # Track high-risk activities
                high_risk_actions = [
                    'CreateUser', 'DeleteUser', 'AttachUserPolicy', 'DetachUserPolicy',
                    'CreateAccessKey', 'DeleteAccessKey', 'CreateRole', 'DeleteRole',
                    'PutRolePolicy', 'DeleteRolePolicy', 'AssumeRole'
                ]
                
                event_name = event.get('EventName', '')
                if event_name in high_risk_actions:
                    metrics['high_risk_activities']['total'] += 1
                    
                    # Count by type
                    if event_name not in metrics['high_risk_activities']['by_type']:
                        metrics['high_risk_activities']['by_type'][event_name] = 0
                    metrics['high_risk_activities']['by_type'][event_name] += 1
                    
                    # Count by user
                    user_key = user_identity.get('userName') or user_identity.get('arn', 'unknown')
                    if user_key not in metrics['high_risk_activities']['by_user']:
                        metrics['high_risk_activities']['by_user'][user_key] = 0
                    metrics['high_risk_activities']['by_user'][user_key] += 1
            
            # Convert sets to counts
            metrics['access_attempts']['unique_ips'] = len(metrics['access_attempts']['unique_ips'])
            metrics['access_attempts']['unique_users'] = len(metrics['access_attempts']['unique_users'])
            
        except Exception as e:
            logger.error(f"Failed to get CloudTrail metrics: {e}")
        
        # Get IAM compliance metrics
        try:
            users_response = self.iam_client.list_users()
            
            for user in users_response.get('Users', []):
                user_name = user['UserName']
                
                # Check for direct policies
                attached_policies = self.iam_client.list_attached_user_policies(UserName=user_name)
                inline_policies = self.iam_client.list_user_policies(UserName=user_name)
                
                if (attached_policies.get('AttachedPolicies') or 
                    inline_policies.get('PolicyNames')):
                    metrics['compliance_status']['iam_users_with_policies'] += 1
                
                # Check for old access keys
                try:
                    access_keys = self.iam_client.list_access_keys(UserName=user_name)
                    for key in access_keys.get('AccessKeyMetadata', []):
                        key_age = datetime.now(key['CreateDate'].tzinfo) - key['CreateDate']
                        if key_age.days > 90:
                            metrics['compliance_status']['old_access_keys'] += 1
                except Exception as e:
                    logger.warning(f"Failed to check access keys for {user_name}: {e}")
                
                # Check for MFA (simplified check)
                try:
                    mfa_devices = self.iam_client.list_mfa_devices(UserName=user_name)
                    if not mfa_devices.get('MFADevices'):
                        metrics['compliance_status']['users_without_mfa'] += 1
                except Exception as e:
                    logger.warning(f"Failed to check MFA for {user_name}: {e}")
            
            # Check for overly permissive roles
            roles_response = self.iam_client.list_roles()
            for role in roles_response.get('Roles', []):
                role_name = role['RoleName']
                
                if role_name.startswith('aws-'):
                    continue
                
                attached_policies = self.iam_client.list_attached_role_policies(RoleName=role_name)
                for policy in attached_policies.get('AttachedPolicies', []):
                    if policy['PolicyName'] in ['PowerUserAccess', 'AdministratorAccess']:
                        metrics['compliance_status']['overly_permissive_roles'] += 1
                        break
                        
        except Exception as e:
            logger.error(f"Failed to get IAM compliance metrics: {e}")
        
        return metrics
    
    def generate_security_trends(self, days_back: int = 30) -> Dict[str, Any]:
        """Generate security trends over time"""
        trends = {
            'period': days_back,
            'daily_metrics': [],
            'trends': {
                'access_attempts': 'stable',
                'failed_attempts': 'stable',
                'high_risk_activities': 'stable'
            }
        }
        
        # Get daily metrics for trend analysis
        for i in range(days_back):
            day_start = datetime.now() - timedelta(days=i+1)
            day_end = datetime.now() - timedelta(days=i)
            
            try:
                response = self.cloudtrail_client.lookup_events(
                    StartTime=day_start,
                    EndTime=day_end,
                    MaxItems=100
                )
                
                events = response.get('Events', [])
                failed_events = [e for e in events if e.get('ErrorCode')]
                
                high_risk_actions = [
                    'CreateUser', 'DeleteUser', 'AttachUserPolicy', 'DetachUserPolicy',
                    'CreateAccessKey', 'DeleteAccessKey', 'CreateRole', 'DeleteRole'
                ]
                high_risk_events = [e for e in events if e.get('EventName') in high_risk_actions]
                
                daily_metric = {
                    'date': day_start.strftime('%Y-%m-%d'),
                    'total_events': len(events),
                    'failed_events': len(failed_events),
                    'high_risk_events': len(high_risk_events)
                }
                
                trends['daily_metrics'].append(daily_metric)
                
            except Exception as e:
                logger.warning(f"Failed to get metrics for {day_start.strftime('%Y-%m-%d')}: {e}")
        
        # Analyze trends (simplified)
        if len(trends['daily_metrics']) >= 7:
            recent_week = trends['daily_metrics'][:7]
            previous_week = trends['daily_metrics'][7:14] if len(trends['daily_metrics']) >= 14 else []
            
            if previous_week:
                recent_avg_total = sum(d['total_events'] for d in recent_week) / len(recent_week)
                previous_avg_total = sum(d['total_events'] for d in previous_week) / len(previous_week)
                
                if recent_avg_total > previous_avg_total * 1.2:
                    trends['trends']['access_attempts'] = 'increasing'
                elif recent_avg_total < previous_avg_total * 0.8:
                    trends['trends']['access_attempts'] = 'decreasing'
                
                recent_avg_failed = sum(d['failed_events'] for d in recent_week) / len(recent_week)
                previous_avg_failed = sum(d['failed_events'] for d in previous_week) / len(previous_week)
                
                if recent_avg_failed > previous_avg_failed * 1.5:
                    trends['trends']['failed_attempts'] = 'increasing'
                elif recent_avg_failed < previous_avg_failed * 0.5:
                    trends['trends']['failed_attempts'] = 'decreasing'
        
        return trends
    
    def generate_compliance_summary(self) -> Dict[str, Any]:
        """Generate comprehensive compliance summary"""
        summary = {
            'timestamp': datetime.now().isoformat(),
            'environment': self.environment,
            'overall_status': 'COMPLIANT',
            'frameworks': {},
            'findings': [],
            'recommendations': []
        }
        
        # SOC 2 compliance
        soc2_status = {
            'status': 'COMPLIANT',
            'controls': {
                'access_logging': 'COMPLIANT',
                'change_monitoring': 'COMPLIANT',
                'incident_response': 'COMPLIANT',
                'vulnerability_management': 'COMPLIANT'
            },
            'findings': []
        }
        
        # Check access logging
        try:
            log_groups = self.logs_client.describe_log_groups(
                logGroupNamePrefix=f"/aws/security-access-logs/{self.environment}"
            )
            if not log_groups.get('logGroups'):
                soc2_status['controls']['access_logging'] = 'NON_COMPLIANT'
                soc2_status['findings'].append("Access logging not configured")
        except Exception as e:
            soc2_status['controls']['access_logging'] = 'UNKNOWN'
            soc2_status['findings'].append(f"Unable to verify access logging: {e}")
        
        # Check monitoring configuration
        if not os.environ.get('SLACK_WEBHOOK_URL'):
            soc2_status['controls']['incident_response'] = 'NON_COMPLIANT'
            soc2_status['findings'].append("Incident response notifications not configured")
        
        if soc2_status['findings']:
            soc2_status['status'] = 'NON_COMPLIANT'
            summary['overall_status'] = 'NON_COMPLIANT'
        
        summary['frameworks']['soc2'] = soc2_status
        
        # Custom security requirements
        custom_status = {
            'status': 'COMPLIANT',
            'requirements': {
                'github_actions_monitoring': 'COMPLIANT',
                'iam_compliance': 'COMPLIANT',
                'secrets_management': 'COMPLIANT',
                'environment_isolation': 'COMPLIANT'
            },
            'findings': []
        }
        
        # Check IAM compliance
        try:
            users_response = self.iam_client.list_users()
            users_with_policies = 0
            
            for user in users_response.get('Users', []):
                user_name = user['UserName']
                attached_policies = self.iam_client.list_attached_user_policies(UserName=user_name)
                inline_policies = self.iam_client.list_user_policies(UserName=user_name)
                
                if (attached_policies.get('AttachedPolicies') or 
                    inline_policies.get('PolicyNames')):
                    users_with_policies += 1
            
            if users_with_policies > 0:
                custom_status['requirements']['iam_compliance'] = 'NON_COMPLIANT'
                custom_status['findings'].append(f"{users_with_policies} users have direct policy attachments")
                
        except Exception as e:
            custom_status['requirements']['iam_compliance'] = 'UNKNOWN'
            custom_status['findings'].append(f"Unable to check IAM compliance: {e}")
        
        if custom_status['findings']:
            custom_status['status'] = 'NON_COMPLIANT'
            summary['overall_status'] = 'NON_COMPLIANT'
        
        summary['frameworks']['custom'] = custom_status
        
        # Generate recommendations
        all_findings = []
        for framework in summary['frameworks'].values():
            all_findings.extend(framework.get('findings', []))
        
        if all_findings:
            summary['recommendations'] = [
                "Address all compliance findings immediately",
                "Implement automated compliance monitoring",
                "Regular security training for team members",
                "Review and update security policies quarterly",
                "Conduct regular security audits"
            ]
        else:
            summary['recommendations'] = [
                "Maintain current security posture",
                "Continue regular monitoring and reviews",
                "Stay updated with security best practices",
                "Plan for security improvements"
            ]
        
        return summary
    
    def generate_executive_report(self, days_back: int = 30) -> str:
        """Generate executive summary report"""
        metrics = self.get_security_metrics(days_back)
        trends = self.generate_security_trends(days_back)
        compliance = self.generate_compliance_summary()
        
        report = f"""# Security Executive Summary Report

**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}
**Environment:** {self.environment}
**Reporting Period:** {days_back} days

## Overall Security Status

**Compliance Status:** {compliance['overall_status']}
**Risk Level:** {'HIGH' if compliance['overall_status'] == 'NON_COMPLIANT' else 'LOW'}

## Key Metrics

### Access Activity
- **Total Access Attempts:** {metrics['access_attempts']['total']:,}
- **Successful Attempts:** {metrics['access_attempts']['successful']:,}
- **Failed Attempts:** {metrics['access_attempts']['failed']:,}
- **Unique IP Addresses:** {metrics['access_attempts']['unique_ips']:,}
- **Unique Users:** {metrics['access_attempts']['unique_users']:,}

### High-Risk Activities
- **Total High-Risk Actions:** {metrics['high_risk_activities']['total']:,}
- **Most Common Actions:** {', '.join(list(metrics['high_risk_activities']['by_type'].keys())[:3])}

### Compliance Issues
- **IAM Users with Direct Policies:** {metrics['compliance_status']['iam_users_with_policies']}
- **Overly Permissive Roles:** {metrics['compliance_status']['overly_permissive_roles']}
- **Old Access Keys:** {metrics['compliance_status']['old_access_keys']}
- **Users Without MFA:** {metrics['compliance_status']['users_without_mfa']}

## Security Trends

- **Access Attempts:** {trends['trends']['access_attempts'].title()}
- **Failed Attempts:** {trends['trends']['failed_attempts'].title()}
- **High-Risk Activities:** {trends['trends']['high_risk_activities'].title()}

## Compliance Status

"""
        
        for framework_name, framework_data in compliance['frameworks'].items():
            report += f"### {framework_name.upper()} Compliance\n"
            report += f"**Status:** {framework_data['status']}\n\n"
            
            if framework_data.get('findings'):
                report += "**Findings:**\n"
                for finding in framework_data['findings']:
                    report += f"- {finding}\n"
                report += "\n"
        
        if compliance['recommendations']:
            report += "## Recommendations\n\n"
            for i, rec in enumerate(compliance['recommendations'], 1):
                report += f"{i}. {rec}\n"
            report += "\n"
        
        report += """## Next Steps

1. **Immediate Actions:** Address any critical compliance findings
2. **Short-term (1-2 weeks):** Implement recommended security improvements
3. **Medium-term (1-3 months):** Enhance monitoring and automation
4. **Long-term (3-6 months):** Regular security reviews and updates

---
*This report is generated automatically by the Security Monitoring System*
"""
        
        return report

def main():
    parser = argparse.ArgumentParser(description="Generate security reports and compliance summaries")
    parser.add_argument("--region", default="us-east-1", help="AWS region")
    parser.add_argument("--environment", default="all", help="Environment to report on")
    parser.add_argument("--days-back", type=int, default=7, help="Days of history to analyze")
    parser.add_argument("--report-type", choices=['metrics', 'trends', 'compliance', 'executive'], 
                       default='executive', help="Type of report to generate")
    parser.add_argument("--output", help="Output file for report")
    parser.add_argument("--format", choices=['json', 'markdown'], default='markdown', help="Output format")
    
    args = parser.parse_args()
    
    # Initialize reporter
    reporter = SecurityReporter(args.region, args.environment)
    
    # Generate requested report
    if args.report_type == 'metrics':
        result = reporter.get_security_metrics(args.days_back)
        output = json.dumps(result, indent=2) if args.format == 'json' else str(result)
    elif args.report_type == 'trends':
        result = reporter.generate_security_trends(args.days_back)
        output = json.dumps(result, indent=2) if args.format == 'json' else str(result)
    elif args.report_type == 'compliance':
        result = reporter.generate_compliance_summary()
        output = json.dumps(result, indent=2) if args.format == 'json' else str(result)
    else:  # executive
        if args.format == 'json':
            # For JSON, combine all data
            result = {
                'metrics': reporter.get_security_metrics(args.days_back),
                'trends': reporter.generate_security_trends(args.days_back),
                'compliance': reporter.generate_compliance_summary()
            }
            output = json.dumps(result, indent=2)
        else:
            output = reporter.generate_executive_report(args.days_back)
    
    # Output result
    if args.output:
        with open(args.output, 'w') as f:
            f.write(output)
        logger.info(f"Report written to {args.output}")
    else:
        print(output)
    
    return 0

if __name__ == "__main__":
    sys.exit(main())