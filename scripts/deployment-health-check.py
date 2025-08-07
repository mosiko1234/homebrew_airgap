#!/usr/bin/env python3
"""
Post-deployment health check system for Homebrew Bottles Sync System.
Verifies that all services are functioning correctly after deployment.
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import boto3
from botocore.exceptions import ClientError, NoCredentialsError
import requests
from pathlib import Path


class HealthCheckResult:
    """Represents the result of a health check"""
    
    def __init__(self, service: str, check_type: str, status: str, 
                 message: str = "", duration_ms: int = 0, details: Dict = None):
        self.service = service
        self.check_type = check_type
        self.status = status  # "pass", "fail", "warn"
        self.message = message
        self.duration_ms = duration_ms
        self.timestamp = datetime.utcnow().isoformat() + "Z"
        self.details = details or {}
    
    def to_dict(self) -> Dict:
        return {
            "service": self.service,
            "check_type": self.check_type,
            "status": self.status,
            "message": self.message,
            "duration_ms": self.duration_ms,
            "timestamp": self.timestamp,
            "details": self.details
        }


class DeploymentHealthChecker:
    """Performs comprehensive health checks after deployment"""
    
    def __init__(self, environment: str, aws_region: str = None):
        self.environment = environment
        self.aws_region = aws_region or os.getenv('AWS_DEFAULT_REGION', 'us-east-1')
        
        # Initialize AWS clients
        try:
            self.session = boto3.Session(region_name=self.aws_region)
            self.lambda_client = self.session.client('lambda')
            self.ecs_client = self.session.client('ecs')
            self.s3_client = self.session.client('s3')
            self.cloudwatch_client = self.session.client('cloudwatch')
            self.ssm_client = self.session.client('ssm')
        except (ClientError, NoCredentialsError) as e:
            print(f"Warning: AWS client initialization failed: {e}")
            self.lambda_client = None
            self.ecs_client = None
            self.s3_client = None
            self.cloudwatch_client = None
            self.ssm_client = None
    
    def run_all_checks(self) -> Tuple[List[HealthCheckResult], bool]:
        """Run all health checks and return results with overall status"""
        results = []
        
        # Core service checks
        results.extend(self._check_lambda_functions())
        results.extend(self._check_ecs_services())
        results.extend(self._check_s3_buckets())
        results.extend(self._check_eventbridge_rules())
        
        # Integration checks
        results.extend(self._check_lambda_integration())
        results.extend(self._check_s3_permissions())
        
        # Performance checks
        results.extend(self._check_cloudwatch_metrics())
        
        # Configuration checks
        results.extend(self._check_ssm_parameters())
        
        # Determine overall health
        failed_checks = [r for r in results if r.status == "fail"]
        warning_checks = [r for r in results if r.status == "warn"]
        
        overall_healthy = len(failed_checks) == 0
        
        return results, overall_healthy
    
    def _check_lambda_functions(self) -> List[HealthCheckResult]:
        """Check Lambda function health"""
        results = []
        
        if not self.lambda_client:
            return [HealthCheckResult(
                "lambda", "availability", "fail", 
                "AWS Lambda client not available"
            )]
        
        function_names = [
            f"homebrew-bottles-sync-{self.environment}-orchestrator",
            f"homebrew-bottles-sync-{self.environment}-sync-worker"
        ]
        
        for function_name in function_names:
            start_time = time.time()
            
            try:
                # Check function configuration
                response = self.lambda_client.get_function(FunctionName=function_name)
                config = response['Configuration']
                
                duration_ms = int((time.time() - start_time) * 1000)
                
                # Check function state
                if config['State'] != 'Active':
                    results.append(HealthCheckResult(
                        function_name, "state", "fail",
                        f"Function state is {config['State']}, expected Active",
                        duration_ms
                    ))
                    continue
                
                # Check last update status
                if config.get('LastUpdateStatus') != 'Successful':
                    results.append(HealthCheckResult(
                        function_name, "update_status", "warn",
                        f"Last update status: {config.get('LastUpdateStatus')}",
                        duration_ms
                    ))
                
                # Function exists and is active
                results.append(HealthCheckResult(
                    function_name, "availability", "pass",
                    f"Function is active and ready",
                    duration_ms,
                    {
                        "runtime": config.get('Runtime'),
                        "memory": config.get('MemorySize'),
                        "timeout": config.get('Timeout'),
                        "last_modified": config.get('LastModified')
                    }
                ))
                
                # Test function invocation (orchestrator only for safety)
                if "orchestrator" in function_name:
                    results.append(self._test_lambda_invocation(function_name))
                
            except ClientError as e:
                duration_ms = int((time.time() - start_time) * 1000)
                error_code = e.response.get('Error', {}).get('Code', 'Unknown')
                
                if error_code == 'ResourceNotFoundException':
                    results.append(HealthCheckResult(
                        function_name, "availability", "fail",
                        "Function not found", duration_ms
                    ))
                else:
                    results.append(HealthCheckResult(
                        function_name, "availability", "fail",
                        f"Error checking function: {error_code}", duration_ms
                    ))
        
        return results
    
    def _test_lambda_invocation(self, function_name: str) -> HealthCheckResult:
        """Test Lambda function invocation with a dry-run payload"""
        start_time = time.time()
        
        try:
            # Create a test payload that won't trigger actual sync
            test_payload = {
                "test": True,
                "dry_run": True,
                "health_check": True
            }
            
            response = self.lambda_client.invoke(
                FunctionName=function_name,
                InvocationType='RequestResponse',
                Payload=json.dumps(test_payload)
            )
            
            duration_ms = int((time.time() - start_time) * 1000)
            
            # Check response
            if response['StatusCode'] == 200:
                payload = json.loads(response['Payload'].read())
                
                if 'errorMessage' in payload:
                    return HealthCheckResult(
                        function_name, "invocation", "warn",
                        f"Function returned error: {payload['errorMessage'][:100]}",
                        duration_ms
                    )
                
                return HealthCheckResult(
                    function_name, "invocation", "pass",
                    "Function invocation successful", duration_ms,
                    {"response_size": len(str(payload))}
                )
            else:
                return HealthCheckResult(
                    function_name, "invocation", "fail",
                    f"Invocation failed with status {response['StatusCode']}",
                    duration_ms
                )
                
        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            return HealthCheckResult(
                function_name, "invocation", "fail",
                f"Invocation test failed: {str(e)[:100]}", duration_ms
            )
    
    def _check_ecs_services(self) -> List[HealthCheckResult]:
        """Check ECS service health"""
        results = []
        
        if not self.ecs_client:
            return [HealthCheckResult(
                "ecs", "availability", "fail",
                "AWS ECS client not available"
            )]
        
        cluster_name = f"homebrew-bottles-sync-{self.environment}"
        service_name = f"homebrew-bottles-sync-{self.environment}-service"
        
        start_time = time.time()
        
        try:
            # Check cluster
            clusters_response = self.ecs_client.describe_clusters(
                clusters=[cluster_name]
            )
            
            if not clusters_response['clusters']:
                duration_ms = int((time.time() - start_time) * 1000)
                return [HealthCheckResult(
                    "ecs-cluster", "availability", "fail",
                    f"Cluster {cluster_name} not found", duration_ms
                )]
            
            cluster = clusters_response['clusters'][0]
            
            # Check cluster status
            if cluster['status'] != 'ACTIVE':
                duration_ms = int((time.time() - start_time) * 1000)
                results.append(HealthCheckResult(
                    "ecs-cluster", "status", "fail",
                    f"Cluster status is {cluster['status']}, expected ACTIVE",
                    duration_ms
                ))
            else:
                duration_ms = int((time.time() - start_time) * 1000)
                results.append(HealthCheckResult(
                    "ecs-cluster", "status", "pass",
                    "Cluster is active", duration_ms,
                    {
                        "active_services": cluster.get('activeServicesCount', 0),
                        "running_tasks": cluster.get('runningTasksCount', 0),
                        "pending_tasks": cluster.get('pendingTasksCount', 0)
                    }
                ))
            
            # Check service if it exists
            try:
                services_response = self.ecs_client.describe_services(
                    cluster=cluster_name,
                    services=[service_name]
                )
                
                if services_response['services']:
                    service = services_response['services'][0]
                    
                    if service['status'] == 'ACTIVE':
                        results.append(HealthCheckResult(
                            "ecs-service", "status", "pass",
                            "Service is active", duration_ms,
                            {
                                "desired_count": service.get('desiredCount', 0),
                                "running_count": service.get('runningCount', 0),
                                "pending_count": service.get('pendingCount', 0)
                            }
                        ))
                    else:
                        results.append(HealthCheckResult(
                            "ecs-service", "status", "warn",
                            f"Service status is {service['status']}", duration_ms
                        ))
                else:
                    results.append(HealthCheckResult(
                        "ecs-service", "availability", "warn",
                        "ECS service not found (may be expected for Lambda-only deployments)",
                        duration_ms
                    ))
                    
            except ClientError as e:
                if e.response.get('Error', {}).get('Code') != 'ServiceNotFoundException':
                    results.append(HealthCheckResult(
                        "ecs-service", "availability", "warn",
                        f"Error checking service: {e}", duration_ms
                    ))
        
        except ClientError as e:
            duration_ms = int((time.time() - start_time) * 1000)
            results.append(HealthCheckResult(
                "ecs-cluster", "availability", "fail",
                f"Error checking ECS cluster: {e}", duration_ms
            ))
        
        return results
    
    def _check_s3_buckets(self) -> List[HealthCheckResult]:
        """Check S3 bucket health and permissions"""
        results = []
        
        if not self.s3_client:
            return [HealthCheckResult(
                "s3", "availability", "fail",
                "AWS S3 client not available"
            )]
        
        bucket_name = f"homebrew-bottles-sync-{self.environment}"
        
        start_time = time.time()
        
        try:
            # Check bucket exists
            self.s3_client.head_bucket(Bucket=bucket_name)
            
            duration_ms = int((time.time() - start_time) * 1000)
            
            results.append(HealthCheckResult(
                "s3-bucket", "availability", "pass",
                f"Bucket {bucket_name} is accessible", duration_ms
            ))
            
            # Check bucket versioning
            try:
                versioning = self.s3_client.get_bucket_versioning(Bucket=bucket_name)
                if versioning.get('Status') == 'Enabled':
                    results.append(HealthCheckResult(
                        "s3-bucket", "versioning", "pass",
                        "Bucket versioning is enabled", duration_ms
                    ))
                else:
                    results.append(HealthCheckResult(
                        "s3-bucket", "versioning", "warn",
                        "Bucket versioning is not enabled", duration_ms
                    ))
            except ClientError:
                results.append(HealthCheckResult(
                    "s3-bucket", "versioning", "warn",
                    "Could not check bucket versioning", duration_ms
                ))
            
            # Check bucket encryption
            try:
                encryption = self.s3_client.get_bucket_encryption(Bucket=bucket_name)
                results.append(HealthCheckResult(
                    "s3-bucket", "encryption", "pass",
                    "Bucket encryption is configured", duration_ms
                ))
            except ClientError as e:
                if e.response.get('Error', {}).get('Code') == 'ServerSideEncryptionConfigurationNotFoundError':
                    results.append(HealthCheckResult(
                        "s3-bucket", "encryption", "warn",
                        "Bucket encryption is not configured", duration_ms
                    ))
                else:
                    results.append(HealthCheckResult(
                        "s3-bucket", "encryption", "warn",
                        f"Could not check bucket encryption: {e}", duration_ms
                    ))
        
        except ClientError as e:
            duration_ms = int((time.time() - start_time) * 1000)
            error_code = e.response.get('Error', {}).get('Code', 'Unknown')
            
            if error_code == 'NoSuchBucket':
                results.append(HealthCheckResult(
                    "s3-bucket", "availability", "fail",
                    f"Bucket {bucket_name} does not exist", duration_ms
                ))
            elif error_code == 'Forbidden':
                results.append(HealthCheckResult(
                    "s3-bucket", "availability", "fail",
                    f"Access denied to bucket {bucket_name}", duration_ms
                ))
            else:
                results.append(HealthCheckResult(
                    "s3-bucket", "availability", "fail",
                    f"Error accessing bucket: {error_code}", duration_ms
                ))
        
        return results
    
    def _check_eventbridge_rules(self) -> List[HealthCheckResult]:
        """Check EventBridge rules for scheduled execution"""
        results = []
        
        try:
            events_client = self.session.client('events')
            
            rule_name = f"homebrew-bottles-sync-{self.environment}-schedule"
            
            start_time = time.time()
            
            try:
                response = events_client.describe_rule(Name=rule_name)
                
                duration_ms = int((time.time() - start_time) * 1000)
                
                if response['State'] == 'ENABLED':
                    results.append(HealthCheckResult(
                        "eventbridge-rule", "status", "pass",
                        f"EventBridge rule {rule_name} is enabled", duration_ms,
                        {
                            "schedule": response.get('ScheduleExpression'),
                            "description": response.get('Description')
                        }
                    ))
                else:
                    results.append(HealthCheckResult(
                        "eventbridge-rule", "status", "warn",
                        f"EventBridge rule {rule_name} is disabled", duration_ms
                    ))
                
                # Check rule targets
                targets_response = events_client.list_targets_by_rule(Rule=rule_name)
                target_count = len(targets_response.get('Targets', []))
                
                if target_count > 0:
                    results.append(HealthCheckResult(
                        "eventbridge-rule", "targets", "pass",
                        f"Rule has {target_count} target(s)", duration_ms
                    ))
                else:
                    results.append(HealthCheckResult(
                        "eventbridge-rule", "targets", "warn",
                        "Rule has no targets configured", duration_ms
                    ))
                    
            except ClientError as e:
                duration_ms = int((time.time() - start_time) * 1000)
                if e.response.get('Error', {}).get('Code') == 'ResourceNotFoundException':
                    results.append(HealthCheckResult(
                        "eventbridge-rule", "availability", "warn",
                        f"EventBridge rule {rule_name} not found (may be expected)", duration_ms
                    ))
                else:
                    results.append(HealthCheckResult(
                        "eventbridge-rule", "availability", "fail",
                        f"Error checking EventBridge rule: {e}", duration_ms
                    ))
        
        except Exception as e:
            results.append(HealthCheckResult(
                "eventbridge", "availability", "fail",
                f"EventBridge client error: {e}", 0
            ))
        
        return results
    
    def _check_lambda_integration(self) -> List[HealthCheckResult]:
        """Check Lambda function integration with other services"""
        results = []
        
        if not self.lambda_client:
            return []
        
        orchestrator_function = f"homebrew-bottles-sync-{self.environment}-orchestrator"
        
        start_time = time.time()
        
        try:
            # Check Lambda environment variables
            response = self.lambda_client.get_function(FunctionName=orchestrator_function)
            env_vars = response['Configuration'].get('Environment', {}).get('Variables', {})
            
            duration_ms = int((time.time() - start_time) * 1000)
            
            required_env_vars = ['S3_BUCKET', 'ENVIRONMENT']
            missing_vars = [var for var in required_env_vars if var not in env_vars]
            
            if missing_vars:
                results.append(HealthCheckResult(
                    orchestrator_function, "configuration", "fail",
                    f"Missing environment variables: {', '.join(missing_vars)}",
                    duration_ms
                ))
            else:
                results.append(HealthCheckResult(
                    orchestrator_function, "configuration", "pass",
                    "Required environment variables are configured", duration_ms
                ))
            
            # Check Lambda permissions (EventBridge trigger)
            try:
                policy_response = self.lambda_client.get_policy(FunctionName=orchestrator_function)
                policy = json.loads(policy_response['Policy'])
                
                # Check if EventBridge has permission to invoke
                eventbridge_permission = any(
                    stmt.get('Principal', {}).get('Service') == 'events.amazonaws.com'
                    for stmt in policy.get('Statement', [])
                )
                
                if eventbridge_permission:
                    results.append(HealthCheckResult(
                        orchestrator_function, "permissions", "pass",
                        "EventBridge invoke permission is configured", duration_ms
                    ))
                else:
                    results.append(HealthCheckResult(
                        orchestrator_function, "permissions", "warn",
                        "EventBridge invoke permission not found", duration_ms
                    ))
                    
            except ClientError as e:
                if e.response.get('Error', {}).get('Code') == 'ResourceNotFoundException':
                    results.append(HealthCheckResult(
                        orchestrator_function, "permissions", "warn",
                        "No resource policy found", duration_ms
                    ))
        
        except ClientError as e:
            duration_ms = int((time.time() - start_time) * 1000)
            results.append(HealthCheckResult(
                orchestrator_function, "integration", "fail",
                f"Error checking integration: {e}", duration_ms
            ))
        
        return results
    
    def _check_s3_permissions(self) -> List[HealthCheckResult]:
        """Check S3 bucket permissions for Lambda functions"""
        results = []
        
        if not self.s3_client:
            return []
        
        bucket_name = f"homebrew-bottles-sync-{self.environment}"
        
        start_time = time.time()
        
        try:
            # Test basic read/write permissions with a test object
            test_key = f"health-check/{datetime.utcnow().isoformat()}.txt"
            test_content = "Health check test file"
            
            # Test write permission
            self.s3_client.put_object(
                Bucket=bucket_name,
                Key=test_key,
                Body=test_content.encode('utf-8')
            )
            
            # Test read permission
            response = self.s3_client.get_object(Bucket=bucket_name, Key=test_key)
            retrieved_content = response['Body'].read().decode('utf-8')
            
            # Clean up test object
            self.s3_client.delete_object(Bucket=bucket_name, Key=test_key)
            
            duration_ms = int((time.time() - start_time) * 1000)
            
            if retrieved_content == test_content:
                results.append(HealthCheckResult(
                    "s3-permissions", "read_write", "pass",
                    "S3 read/write permissions are working", duration_ms
                ))
            else:
                results.append(HealthCheckResult(
                    "s3-permissions", "read_write", "fail",
                    "S3 read/write test failed - content mismatch", duration_ms
                ))
        
        except ClientError as e:
            duration_ms = int((time.time() - start_time) * 1000)
            error_code = e.response.get('Error', {}).get('Code', 'Unknown')
            
            results.append(HealthCheckResult(
                "s3-permissions", "read_write", "fail",
                f"S3 permission test failed: {error_code}", duration_ms
            ))
        
        return results
    
    def _check_cloudwatch_metrics(self) -> List[HealthCheckResult]:
        """Check CloudWatch metrics and recent activity"""
        results = []
        
        if not self.cloudwatch_client:
            return []
        
        # Check for recent Lambda invocations
        function_names = [
            f"homebrew-bottles-sync-{self.environment}-orchestrator",
            f"homebrew-bottles-sync-{self.environment}-sync-worker"
        ]
        
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(hours=24)
        
        for function_name in function_names:
            try:
                response = self.cloudwatch_client.get_metric_statistics(
                    Namespace='AWS/Lambda',
                    MetricName='Invocations',
                    Dimensions=[
                        {
                            'Name': 'FunctionName',
                            'Value': function_name
                        }
                    ],
                    StartTime=start_time,
                    EndTime=end_time,
                    Period=3600,  # 1 hour periods
                    Statistics=['Sum']
                )
                
                datapoints = response.get('Datapoints', [])
                total_invocations = sum(dp['Sum'] for dp in datapoints)
                
                if total_invocations > 0:
                    results.append(HealthCheckResult(
                        function_name, "activity", "pass",
                        f"{int(total_invocations)} invocations in last 24h", 0,
                        {"invocations_24h": int(total_invocations)}
                    ))
                else:
                    results.append(HealthCheckResult(
                        function_name, "activity", "warn",
                        "No invocations in last 24h", 0
                    ))
                
                # Check for errors
                error_response = self.cloudwatch_client.get_metric_statistics(
                    Namespace='AWS/Lambda',
                    MetricName='Errors',
                    Dimensions=[
                        {
                            'Name': 'FunctionName',
                            'Value': function_name
                        }
                    ],
                    StartTime=start_time,
                    EndTime=end_time,
                    Period=3600,
                    Statistics=['Sum']
                )
                
                error_datapoints = error_response.get('Datapoints', [])
                total_errors = sum(dp['Sum'] for dp in error_datapoints)
                
                if total_errors > 0:
                    results.append(HealthCheckResult(
                        function_name, "errors", "warn",
                        f"{int(total_errors)} errors in last 24h", 0,
                        {"errors_24h": int(total_errors)}
                    ))
                
            except ClientError as e:
                results.append(HealthCheckResult(
                    function_name, "metrics", "warn",
                    f"Could not retrieve metrics: {e}", 0
                ))
        
        return results
    
    def _check_ssm_parameters(self) -> List[HealthCheckResult]:
        """Check SSM parameters for configuration"""
        results = []
        
        if not self.ssm_client:
            return []
        
        # Check for deployment tracking parameters
        parameter_name = f"/homebrew-bottles-sync/deployments/{self.environment}/latest"
        
        start_time = time.time()
        
        try:
            response = self.ssm_client.get_parameter(Name=parameter_name)
            
            duration_ms = int((time.time() - start_time) * 1000)
            
            # Validate parameter content
            try:
                param_data = json.loads(response['Parameter']['Value'])
                
                if 'timestamp' in param_data and 'status' in param_data:
                    results.append(HealthCheckResult(
                        "ssm-parameters", "deployment_tracking", "pass",
                        "Deployment tracking parameter is valid", duration_ms,
                        {
                            "last_update": param_data.get('timestamp'),
                            "status": param_data.get('status')
                        }
                    ))
                else:
                    results.append(HealthCheckResult(
                        "ssm-parameters", "deployment_tracking", "warn",
                        "Deployment tracking parameter has invalid format", duration_ms
                    ))
                    
            except json.JSONDecodeError:
                results.append(HealthCheckResult(
                    "ssm-parameters", "deployment_tracking", "warn",
                    "Deployment tracking parameter is not valid JSON", duration_ms
                ))
        
        except ClientError as e:
            duration_ms = int((time.time() - start_time) * 1000)
            if e.response.get('Error', {}).get('Code') == 'ParameterNotFound':
                results.append(HealthCheckResult(
                    "ssm-parameters", "deployment_tracking", "warn",
                    "Deployment tracking parameter not found", duration_ms
                ))
            else:
                results.append(HealthCheckResult(
                    "ssm-parameters", "deployment_tracking", "fail",
                    f"Error accessing SSM parameter: {e}", duration_ms
                ))
        
        return results


def format_health_report(results: List[HealthCheckResult], overall_healthy: bool) -> str:
    """Format health check results into a readable report"""
    
    report_lines = []
    report_lines.append("=" * 80)
    report_lines.append("DEPLOYMENT HEALTH CHECK REPORT")
    report_lines.append("=" * 80)
    report_lines.append(f"Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}")
    report_lines.append(f"Overall Status: {'✅ HEALTHY' if overall_healthy else '❌ UNHEALTHY'}")
    report_lines.append("")
    
    # Group results by service
    services = {}
    for result in results:
        if result.service not in services:
            services[result.service] = []
        services[result.service].append(result)
    
    # Summary
    total_checks = len(results)
    passed_checks = len([r for r in results if r.status == "pass"])
    failed_checks = len([r for r in results if r.status == "fail"])
    warning_checks = len([r for r in results if r.status == "warn"])
    
    report_lines.append("SUMMARY:")
    report_lines.append(f"  Total Checks: {total_checks}")
    report_lines.append(f"  ✅ Passed: {passed_checks}")
    report_lines.append(f"  ❌ Failed: {failed_checks}")
    report_lines.append(f"  ⚠️  Warnings: {warning_checks}")
    report_lines.append("")
    
    # Detailed results
    report_lines.append("DETAILED RESULTS:")
    report_lines.append("-" * 80)
    
    for service_name, service_results in services.items():
        report_lines.append(f"\n🔧 {service_name.upper()}")
        
        for result in service_results:
            status_icon = {"pass": "✅", "fail": "❌", "warn": "⚠️"}[result.status]
            report_lines.append(f"  {status_icon} {result.check_type}: {result.message}")
            
            if result.duration_ms > 0:
                report_lines.append(f"     Duration: {result.duration_ms}ms")
            
            if result.details:
                for key, value in result.details.items():
                    report_lines.append(f"     {key}: {value}")
    
    report_lines.append("")
    report_lines.append("=" * 80)
    
    return "\n".join(report_lines)


def main():
    """Main CLI interface for deployment health checks"""
    
    parser = argparse.ArgumentParser(description="Post-deployment health check system")
    parser.add_argument("--environment", required=True, 
                       choices=["dev", "staging", "prod"],
                       help="Environment to check")
    parser.add_argument("--aws-region", help="AWS region (default: from environment)")
    parser.add_argument("--output-format", choices=["text", "json"], default="text",
                       help="Output format")
    parser.add_argument("--fail-on-warnings", action="store_true",
                       help="Treat warnings as failures")
    parser.add_argument("--timeout", type=int, default=300,
                       help="Timeout in seconds (default: 300)")
    
    args = parser.parse_args()
    
    # Initialize health checker
    checker = DeploymentHealthChecker(args.environment, args.aws_region)
    
    print(f"🔍 Running health checks for {args.environment} environment...")
    
    try:
        # Run health checks
        results, overall_healthy = checker.run_all_checks()
        
        # Apply fail-on-warnings logic
        if args.fail_on_warnings:
            warning_count = len([r for r in results if r.status == "warn"])
            if warning_count > 0:
                overall_healthy = False
        
        # Output results
        if args.output_format == "json":
            output = {
                "environment": args.environment,
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "overall_healthy": overall_healthy,
                "summary": {
                    "total_checks": len(results),
                    "passed": len([r for r in results if r.status == "pass"]),
                    "failed": len([r for r in results if r.status == "fail"]),
                    "warnings": len([r for r in results if r.status == "warn"])
                },
                "results": [result.to_dict() for result in results]
            }
            print(json.dumps(output, indent=2))
        else:
            print(format_health_report(results, overall_healthy))
        
        # Exit with appropriate code
        sys.exit(0 if overall_healthy else 1)
        
    except KeyboardInterrupt:
        print("\n❌ Health check interrupted")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Health check failed with error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()