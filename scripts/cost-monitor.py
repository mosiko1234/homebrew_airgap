#!/usr/bin/env python3
"""
Cost monitoring and optimization system for AWS infrastructure.
Tracks deployment costs, provides optimization recommendations, and manages resource lifecycle.
"""

import argparse
import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
import boto3
from botocore.exceptions import ClientError, NoCredentialsError

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.notification_config import NotificationConfig
from scripts.notify_deployment import NotificationManager


class CostMonitor:
    """AWS cost monitoring and optimization system"""
    
    def __init__(self, environment: str, aws_region: str = None):
        self.environment = environment
        self.aws_region = aws_region or os.getenv('AWS_DEFAULT_REGION', 'us-east-1')
        
        # Initialize AWS clients
        try:
            self.session = boto3.Session(region_name=self.aws_region)
            self.ce_client = self.session.client('ce')  # Cost Explorer
            self.cloudwatch_client = self.session.client('cloudwatch')
            self.lambda_client = self.session.client('lambda')
            self.ecs_client = self.session.client('ecs')
            self.s3_client = self.session.client('s3')
            self.ec2_client = self.session.client('ec2')
        except (ClientError, NoCredentialsError) as e:
            print(f"Warning: AWS client initialization failed: {e}")
            self.ce_client = None
            self.cloudwatch_client = None
            self.lambda_client = None
            self.ecs_client = None
            self.s3_client = None
            self.ec2_client = None
        
        # Initialize notification components
        self.notification_config = NotificationConfig()
        self.notification_manager = NotificationManager()
        
        # Cost tracking configuration
        self.cost_allocation_tags = [
            f"Environment:{environment}",
            f"Project:homebrew-bottles-sync"
        ]
    
    def get_current_month_costs(self) -> Dict[str, Any]:
        """Get current month costs for the environment"""
        
        if not self.ce_client:
            return {"error": "Cost Explorer client not available"}
        
        # Calculate date range for current month
        now = datetime.utcnow()
        start_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        end_of_month = (start_of_month + timedelta(days=32)).replace(day=1) - timedelta(days=1)
        
        try:
            response = self.ce_client.get_cost_and_usage(
                TimePeriod={
                    'Start': start_of_month.strftime('%Y-%m-%d'),
                    'End': end_of_month.strftime('%Y-%m-%d')
                },
                Granularity='MONTHLY',
                Metrics=['BlendedCost', 'UsageQuantity'],
                GroupBy=[
                    {
                        'Type': 'DIMENSION',
                        'Key': 'SERVICE'
                    }
                ],
                Filter={
                    'Tags': {
                        'Key': 'Environment',
                        'Values': [self.environment]
                    }
                }
            )
            
            # Process results
            total_cost = 0.0
            service_costs = {}
            
            for result in response.get('ResultsByTime', []):
                for group in result.get('Groups', []):
                    service_name = group['Keys'][0]
                    cost = float(group['Metrics']['BlendedCost']['Amount'])
                    service_costs[service_name] = cost
                    total_cost += cost
            
            return {
                "period": "current_month",
                "start_date": start_of_month.strftime('%Y-%m-%d'),
                "end_date": end_of_month.strftime('%Y-%m-%d'),
                "total_cost": round(total_cost, 2),
                "service_breakdown": service_costs,
                "currency": "USD"
            }
            
        except ClientError as e:
            return {"error": f"Failed to get cost data: {e}"}
    
    def get_daily_costs(self, days: int = 30) -> Dict[str, Any]:
        """Get daily costs for the specified number of days"""
        
        if not self.ce_client:
            return {"error": "Cost Explorer client not available"}
        
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)
        
        try:
            response = self.ce_client.get_cost_and_usage(
                TimePeriod={
                    'Start': start_date.strftime('%Y-%m-%d'),
                    'End': end_date.strftime('%Y-%m-%d')
                },
                Granularity='DAILY',
                Metrics=['BlendedCost'],
                Filter={
                    'Tags': {
                        'Key': 'Environment',
                        'Values': [self.environment]
                    }
                }
            )
            
            # Process daily costs
            daily_costs = []
            total_cost = 0.0
            
            for result in response.get('ResultsByTime', []):
                date = result['TimePeriod']['Start']
                cost = float(result['Total']['BlendedCost']['Amount'])
                daily_costs.append({
                    "date": date,
                    "cost": round(cost, 2)
                })
                total_cost += cost
            
            # Calculate average daily cost
            avg_daily_cost = total_cost / len(daily_costs) if daily_costs else 0
            
            return {
                "period_days": days,
                "total_cost": round(total_cost, 2),
                "average_daily_cost": round(avg_daily_cost, 2),
                "daily_breakdown": daily_costs,
                "currency": "USD"
            }
            
        except ClientError as e:
            return {"error": f"Failed to get daily cost data: {e}"}
    
    def estimate_monthly_cost(self) -> Dict[str, Any]:
        """Estimate monthly cost based on current usage"""
        
        # Get last 7 days of costs for estimation
        daily_costs = self.get_daily_costs(7)
        
        if "error" in daily_costs:
            return daily_costs
        
        avg_daily_cost = daily_costs.get("average_daily_cost", 0)
        
        # Estimate monthly cost (30 days)
        estimated_monthly = avg_daily_cost * 30
        
        # Get threshold for this environment
        threshold = self.notification_config.get_cost_threshold(self.environment)
        
        return {
            "estimated_monthly_cost": round(estimated_monthly, 2),
            "threshold": threshold,
            "percentage_of_threshold": round((estimated_monthly / threshold) * 100, 1) if threshold > 0 else 0,
            "days_until_threshold": round(threshold / avg_daily_cost, 1) if avg_daily_cost > 0 else float('inf'),
            "currency": "USD"
        }
    
    def get_resource_costs(self) -> Dict[str, Any]:
        """Get detailed resource costs breakdown"""
        
        if not self.ce_client:
            return {"error": "Cost Explorer client not available"}
        
        # Get current month costs by resource
        now = datetime.utcnow()
        start_of_month = now.replace(day=1)
        
        try:
            # Get costs by service
            service_response = self.ce_client.get_cost_and_usage(
                TimePeriod={
                    'Start': start_of_month.strftime('%Y-%m-%d'),
                    'End': now.strftime('%Y-%m-%d')
                },
                Granularity='MONTHLY',
                Metrics=['BlendedCost'],
                GroupBy=[
                    {
                        'Type': 'DIMENSION',
                        'Key': 'SERVICE'
                    }
                ],
                Filter={
                    'Tags': {
                        'Key': 'Environment',
                        'Values': [self.environment]
                    }
                }
            )
            
            # Get costs by usage type
            usage_response = self.ce_client.get_cost_and_usage(
                TimePeriod={
                    'Start': start_of_month.strftime('%Y-%m-%d'),
                    'End': now.strftime('%Y-%m-%d')
                },
                Granularity='MONTHLY',
                Metrics=['BlendedCost'],
                GroupBy=[
                    {
                        'Type': 'DIMENSION',
                        'Key': 'USAGE_TYPE'
                    }
                ],
                Filter={
                    'Tags': {
                        'Key': 'Environment',
                        'Values': [self.environment]
                    }
                }
            )
            
            # Process service costs
            service_costs = {}
            for result in service_response.get('ResultsByTime', []):
                for group in result.get('Groups', []):
                    service = group['Keys'][0]
                    cost = float(group['Metrics']['BlendedCost']['Amount'])
                    service_costs[service] = round(cost, 2)
            
            # Process usage type costs
            usage_costs = {}
            for result in usage_response.get('ResultsByTime', []):
                for group in result.get('Groups', []):
                    usage_type = group['Keys'][0]
                    cost = float(group['Metrics']['BlendedCost']['Amount'])
                    if cost > 0.01:  # Only include costs > $0.01
                        usage_costs[usage_type] = round(cost, 2)
            
            return {
                "service_breakdown": service_costs,
                "usage_type_breakdown": dict(sorted(usage_costs.items(), key=lambda x: x[1], reverse=True)[:10]),
                "period": "current_month_to_date"
            }
            
        except ClientError as e:
            return {"error": f"Failed to get resource costs: {e}"}
    
    def check_cost_thresholds(self) -> Dict[str, Any]:
        """Check if costs exceed configured thresholds"""
        
        # Get current costs
        current_costs = self.get_current_month_costs()
        if "error" in current_costs:
            return current_costs
        
        # Get estimated monthly cost
        monthly_estimate = self.estimate_monthly_cost()
        if "error" in monthly_estimate:
            return monthly_estimate
        
        # Get threshold configuration
        threshold = self.notification_config.get_cost_threshold(self.environment)
        thresholds_config = self.notification_config.get_thresholds()
        warning_percentage = thresholds_config.get("costs", {}).get("warning_percentage", 80)
        critical_percentage = thresholds_config.get("costs", {}).get("critical_percentage", 100)
        
        current_cost = current_costs.get("total_cost", 0)
        estimated_cost = monthly_estimate.get("estimated_monthly_cost", 0)
        
        # Calculate percentages
        current_percentage = (current_cost / threshold) * 100 if threshold > 0 else 0
        estimated_percentage = (estimated_cost / threshold) * 100 if threshold > 0 else 0
        
        # Determine alert level
        alert_level = "ok"
        if estimated_percentage >= critical_percentage:
            alert_level = "critical"
        elif estimated_percentage >= warning_percentage:
            alert_level = "warning"
        elif current_percentage >= warning_percentage:
            alert_level = "warning"
        
        return {
            "threshold": threshold,
            "current_cost": current_cost,
            "estimated_monthly_cost": estimated_cost,
            "current_percentage": round(current_percentage, 1),
            "estimated_percentage": round(estimated_percentage, 1),
            "alert_level": alert_level,
            "warning_threshold": warning_percentage,
            "critical_threshold": critical_percentage,
            "days_remaining_in_month": (datetime.utcnow().replace(month=datetime.utcnow().month+1, day=1) - datetime.utcnow()).days
        }
    
    def get_optimization_recommendations(self) -> List[Dict[str, Any]]:
        """Generate cost optimization recommendations"""
        
        recommendations = []
        
        # Get resource costs for analysis
        resource_costs = self.get_resource_costs()
        if "error" in resource_costs:
            return [{"type": "error", "message": resource_costs["error"]}]
        
        service_costs = resource_costs.get("service_breakdown", {})
        
        # Lambda optimization recommendations
        if "AWS Lambda" in service_costs and service_costs["AWS Lambda"] > 10:
            recommendations.append({
                "type": "lambda_optimization",
                "priority": "medium",
                "potential_savings": "10-30%",
                "description": "Lambda costs are significant. Consider optimizing memory allocation and execution time.",
                "actions": [
                    "Review Lambda function memory settings",
                    "Optimize code for faster execution",
                    "Consider using ARM-based Graviton2 processors",
                    "Implement function warming for frequently used functions"
                ]
            })
        
        # S3 optimization recommendations
        if "Amazon Simple Storage Service" in service_costs and service_costs["Amazon Simple Storage Service"] > 5:
            recommendations.append({
                "type": "s3_optimization",
                "priority": "low",
                "potential_savings": "20-50%",
                "description": "S3 storage costs can be optimized with lifecycle policies.",
                "actions": [
                    "Implement S3 lifecycle policies to transition old objects to cheaper storage classes",
                    "Enable S3 Intelligent Tiering",
                    "Review and delete unnecessary objects",
                    "Use S3 compression for large files"
                ]
            })
        
        # ECS optimization recommendations
        if "Amazon Elastic Container Service" in service_costs and service_costs["Amazon Elastic Container Service"] > 20:
            recommendations.append({
                "type": "ecs_optimization",
                "priority": "high",
                "potential_savings": "30-60%",
                "description": "ECS costs are high. Consider right-sizing and Spot instances.",
                "actions": [
                    "Use Fargate Spot for non-critical workloads",
                    "Right-size ECS tasks based on actual usage",
                    "Implement auto-scaling policies",
                    "Consider scheduled scaling for predictable workloads"
                ]
            })
        
        # Environment-specific recommendations
        if self.environment == "dev":
            recommendations.append({
                "type": "dev_environment_optimization",
                "priority": "high",
                "potential_savings": "50-80%",
                "description": "Development environment can be optimized with scheduled shutdown.",
                "actions": [
                    "Implement automatic shutdown during non-business hours",
                    "Use smaller instance sizes for development",
                    "Share resources across development teams",
                    "Use spot instances where possible"
                ]
            })
        
        # General recommendations
        total_cost = sum(service_costs.values())
        if total_cost > 100:
            recommendations.append({
                "type": "general_optimization",
                "priority": "medium",
                "potential_savings": "10-25%",
                "description": "General cost optimization opportunities identified.",
                "actions": [
                    "Review and optimize resource tagging for better cost allocation",
                    "Implement cost budgets and alerts",
                    "Regular cost reviews and optimization sessions",
                    "Consider Reserved Instances for predictable workloads"
                ]
            })
        
        return recommendations
    
    def implement_dev_environment_shutdown(self) -> Dict[str, Any]:
        """Implement automatic shutdown for development environment resources"""
        
        if self.environment != "dev":
            return {"error": "Automatic shutdown only available for dev environment"}
        
        results = {
            "shutdown_actions": [],
            "errors": []
        }
        
        try:
            # Stop ECS services
            if self.ecs_client:
                cluster_name = f"homebrew-bottles-sync-{self.environment}"
                try:
                    services_response = self.ecs_client.list_services(cluster=cluster_name)
                    for service_arn in services_response.get('serviceArns', []):
                        self.ecs_client.update_service(
                            cluster=cluster_name,
                            service=service_arn,
                            desiredCount=0
                        )
                        results["shutdown_actions"].append(f"Stopped ECS service: {service_arn}")
                except ClientError as e:
                    results["errors"].append(f"ECS shutdown error: {e}")
            
            # Note: Lambda functions don't need to be "stopped" as they're serverless
            # S3 buckets should remain active for data persistence
            
            results["shutdown_actions"].append("Development environment resources scaled down")
            
        except Exception as e:
            results["errors"].append(f"Shutdown error: {e}")
        
        return results
    
    def implement_dev_environment_startup(self) -> Dict[str, Any]:
        """Start up development environment resources"""
        
        if self.environment != "dev":
            return {"error": "Automatic startup only available for dev environment"}
        
        results = {
            "startup_actions": [],
            "errors": []
        }
        
        try:
            # Start ECS services
            if self.ecs_client:
                cluster_name = f"homebrew-bottles-sync-{self.environment}"
                try:
                    services_response = self.ecs_client.list_services(cluster=cluster_name)
                    for service_arn in services_response.get('serviceArns', []):
                        self.ecs_client.update_service(
                            cluster=cluster_name,
                            service=service_arn,
                            desiredCount=1  # Start with 1 instance
                        )
                        results["startup_actions"].append(f"Started ECS service: {service_arn}")
                except ClientError as e:
                    results["errors"].append(f"ECS startup error: {e}")
            
            results["startup_actions"].append("Development environment resources started")
            
        except Exception as e:
            results["errors"].append(f"Startup error: {e}")
        
        return results
    
    def send_cost_alert(self, threshold_check: Dict[str, Any]) -> bool:
        """Send cost threshold alert notification"""
        
        if threshold_check.get("alert_level") == "ok":
            return True  # No alert needed
        
        severity = "critical" if threshold_check.get("alert_level") == "critical" else "medium"
        
        cost_data = {
            "current_cost": f"{threshold_check.get('current_cost', 0):.2f}",
            "threshold": f"{threshold_check.get('threshold', 0):.2f}",
            "period": "monthly",
            "overage": f"{max(0, threshold_check.get('estimated_monthly_cost', 0) - threshold_check.get('threshold', 0)):.2f}"
        }
        
        results = self.notification_manager.send_cost_alert(
            self.environment,
            cost_data,
            severity
        )
        
        return any(results.values())
    
    def generate_cost_report(self, days: int = 30) -> Dict[str, Any]:
        """Generate comprehensive cost report"""
        
        print(f"📊 Generating cost report for {self.environment} ({days} days)")
        
        report = {
            "environment": self.environment,
            "report_period_days": days,
            "generated_at": datetime.utcnow().isoformat() + "Z",
            "currency": "USD"
        }
        
        # Get current month costs
        current_costs = self.get_current_month_costs()
        report["current_month"] = current_costs
        
        # Get daily costs trend
        daily_costs = self.get_daily_costs(days)
        report["daily_trend"] = daily_costs
        
        # Get monthly estimate
        monthly_estimate = self.estimate_monthly_cost()
        report["monthly_estimate"] = monthly_estimate
        
        # Get resource breakdown
        resource_costs = self.get_resource_costs()
        report["resource_breakdown"] = resource_costs
        
        # Check thresholds
        threshold_check = self.check_cost_thresholds()
        report["threshold_analysis"] = threshold_check
        
        # Get optimization recommendations
        recommendations = self.get_optimization_recommendations()
        report["optimization_recommendations"] = recommendations
        
        return report


def format_cost_report(report: Dict[str, Any]) -> str:
    """Format cost report into readable text"""
    
    lines = []
    lines.append("=" * 80)
    lines.append("AWS COST MONITORING REPORT")
    lines.append("=" * 80)
    lines.append(f"Environment: {report['environment'].upper()}")
    lines.append(f"Generated: {report['generated_at']}")
    lines.append(f"Currency: {report['currency']}")
    lines.append("")
    
    # Current month summary
    current_month = report.get("current_month", {})
    if "error" not in current_month:
        lines.append("📊 CURRENT MONTH COSTS:")
        lines.append(f"  Total Cost: ${current_month.get('total_cost', 0):.2f}")
        lines.append(f"  Period: {current_month.get('start_date')} to {current_month.get('end_date')}")
        
        # Top services
        services = current_month.get("service_breakdown", {})
        if services:
            lines.append("  Top Services:")
            sorted_services = sorted(services.items(), key=lambda x: x[1], reverse=True)[:5]
            for service, cost in sorted_services:
                lines.append(f"    • {service}: ${cost:.2f}")
        lines.append("")
    
    # Monthly estimate
    monthly_estimate = report.get("monthly_estimate", {})
    if "error" not in monthly_estimate:
        lines.append("📈 MONTHLY ESTIMATE:")
        lines.append(f"  Estimated Cost: ${monthly_estimate.get('estimated_monthly_cost', 0):.2f}")
        lines.append(f"  Threshold: ${monthly_estimate.get('threshold', 0):.2f}")
        lines.append(f"  Percentage of Threshold: {monthly_estimate.get('percentage_of_threshold', 0):.1f}%")
        lines.append("")
    
    # Threshold analysis
    threshold_analysis = report.get("threshold_analysis", {})
    if "error" not in threshold_analysis:
        alert_level = threshold_analysis.get("alert_level", "ok")
        alert_icon = {"ok": "✅", "warning": "⚠️", "critical": "🚨"}[alert_level]
        
        lines.append("🎯 THRESHOLD ANALYSIS:")
        lines.append(f"  Status: {alert_icon} {alert_level.upper()}")
        lines.append(f"  Current: ${threshold_analysis.get('current_cost', 0):.2f} ({threshold_analysis.get('current_percentage', 0):.1f}%)")
        lines.append(f"  Estimated: ${threshold_analysis.get('estimated_monthly_cost', 0):.2f} ({threshold_analysis.get('estimated_percentage', 0):.1f}%)")
        lines.append("")
    
    # Optimization recommendations
    recommendations = report.get("optimization_recommendations", [])
    if recommendations:
        lines.append("💡 OPTIMIZATION RECOMMENDATIONS:")
        for i, rec in enumerate(recommendations[:5], 1):  # Show top 5
            priority_icon = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(rec.get("priority", "medium"), "🟡")
            lines.append(f"  {i}. {priority_icon} {rec.get('description', 'No description')}")
            lines.append(f"     Potential Savings: {rec.get('potential_savings', 'Unknown')}")
            if rec.get("actions"):
                lines.append(f"     Actions: {len(rec['actions'])} recommended")
        lines.append("")
    
    lines.append("=" * 80)
    
    return "\n".join(lines)


def main():
    """Main CLI interface for cost monitoring"""
    
    parser = argparse.ArgumentParser(description="AWS cost monitoring and optimization")
    parser.add_argument("--environment", required=True,
                       choices=["dev", "staging", "prod"],
                       help="Environment to monitor")
    parser.add_argument("--aws-region", help="AWS region (default: from environment)")
    
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Current costs command
    subparsers.add_parser("current", help="Get current month costs")
    
    # Daily costs command
    daily_parser = subparsers.add_parser("daily", help="Get daily costs")
    daily_parser.add_argument("--days", type=int, default=30, help="Number of days (default: 30)")
    
    # Estimate command
    subparsers.add_parser("estimate", help="Get monthly cost estimate")
    
    # Check thresholds command
    subparsers.add_parser("check-thresholds", help="Check cost thresholds")
    
    # Recommendations command
    subparsers.add_parser("recommendations", help="Get optimization recommendations")
    
    # Report command
    report_parser = subparsers.add_parser("report", help="Generate comprehensive cost report")
    report_parser.add_argument("--days", type=int, default=30, help="Report period in days")
    report_parser.add_argument("--output-format", choices=["text", "json"], default="text")
    
    # Dev environment management
    dev_parser = subparsers.add_parser("dev-shutdown", help="Shutdown dev environment resources")
    dev_parser = subparsers.add_parser("dev-startup", help="Start dev environment resources")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    # Initialize cost monitor
    monitor = CostMonitor(args.environment, args.aws_region)
    
    try:
        if args.command == "current":
            result = monitor.get_current_month_costs()
            print(json.dumps(result, indent=2))
        
        elif args.command == "daily":
            result = monitor.get_daily_costs(args.days)
            print(json.dumps(result, indent=2))
        
        elif args.command == "estimate":
            result = monitor.estimate_monthly_cost()
            print(json.dumps(result, indent=2))
        
        elif args.command == "check-thresholds":
            result = monitor.check_cost_thresholds()
            print(json.dumps(result, indent=2))
            
            # Send alert if needed
            if result.get("alert_level") != "ok":
                print("\n📢 Sending cost threshold alert...")
                alert_sent = monitor.send_cost_alert(result)
                print(f"Alert sent: {'✅' if alert_sent else '❌'}")
        
        elif args.command == "recommendations":
            result = monitor.get_optimization_recommendations()
            print(json.dumps(result, indent=2))
        
        elif args.command == "report":
            result = monitor.generate_cost_report(args.days)
            
            if args.output_format == "json":
                print(json.dumps(result, indent=2))
            else:
                print(format_cost_report(result))
        
        elif args.command == "dev-shutdown":
            result = monitor.implement_dev_environment_shutdown()
            print(json.dumps(result, indent=2))
        
        elif args.command == "dev-startup":
            result = monitor.implement_dev_environment_startup()
            print(json.dumps(result, indent=2))
    
    except KeyboardInterrupt:
        print("\n🛑 Cost monitoring interrupted")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Cost monitoring failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()