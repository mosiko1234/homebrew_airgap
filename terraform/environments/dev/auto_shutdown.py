#!/usr/bin/env python3
"""
Enhanced auto-shutdown Lambda function for development environment
Handles automatic shutdown and startup of ECS services, Lambda functions, and other resources for cost optimization
"""

import json
import boto3
import os
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List
import pytz

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize AWS clients
ecs_client = boto3.client('ecs')
lambda_client = boto3.client('lambda')
cloudwatch_client = boto3.client('cloudwatch')
ssm_client = boto3.client('ssm')

# Configuration
BUSINESS_HOURS_START = 9  # 9 AM
BUSINESS_HOURS_END = 18   # 6 PM
TIMEZONE = 'UTC'


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Enhanced Lambda handler for auto-shutdown functionality
    
    Args:
        event: Lambda event containing action and configuration
        context: Lambda context
        
    Returns:
        Response dictionary with status and message
    """
    try:
        # Get environment variables
        cluster_name = os.environ.get('ECS_CLUSTER_NAME')
        environment = os.environ.get('ENVIRONMENT', 'dev')
        
        if not cluster_name:
            raise ValueError("ECS_CLUSTER_NAME environment variable not set")
        
        # Parse the action from event
        action = event.get('action')
        
        # If no action specified, determine based on time
        if not action:
            action = determine_action_by_time()
        
        logger.info(f"Processing {action} action for environment {environment}")
        
        # Track the operation
        operation_start = datetime.utcnow()
        
        if action == 'shutdown':
            result = shutdown_environment(cluster_name, environment)
        elif action == 'startup':
            result = startup_environment(cluster_name, environment)
        elif action == 'status':
            result = get_environment_status(cluster_name, environment)
        else:
            raise ValueError(f"Unknown action: {action}")
        
        # Calculate operation duration
        operation_duration = (datetime.utcnow() - operation_start).total_seconds()
        
        # Store operation result in SSM for tracking
        store_operation_result(environment, action, result, operation_duration)
        
        # Send CloudWatch metrics
        send_cloudwatch_metrics(environment, action, result, operation_duration)
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': f'Successfully processed {action} for {environment}',
                'result': result,
                'environment': environment,
                'duration_seconds': operation_duration,
                'timestamp': datetime.utcnow().isoformat() + 'Z'
            })
        }
        
    except Exception as e:
        logger.error(f"Error processing auto-shutdown: {str(e)}")
        
        # Send error metrics
        try:
            send_error_metrics(environment, str(e))
        except:
            pass
        
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': str(e),
                'message': f'Failed to process {action}',
                'timestamp': datetime.utcnow().isoformat() + 'Z'
            })
        }


def determine_action_by_time() -> str:
    """
    Determine whether to shutdown or startup based on current time
    
    Returns:
        Action to take ('shutdown' or 'startup')
    """
    try:
        tz = pytz.timezone(TIMEZONE)
        current_time = datetime.now(tz)
        current_hour = current_time.hour
        is_weekend = current_time.weekday() >= 5  # Saturday = 5, Sunday = 6
        
        logger.info(f"Current time: {current_time}, Hour: {current_hour}, Weekend: {is_weekend}")
        
        # Shutdown during weekends or outside business hours
        if is_weekend or current_hour < BUSINESS_HOURS_START or current_hour >= BUSINESS_HOURS_END:
            return 'shutdown'
        else:
            return 'startup'
            
    except Exception as e:
        logger.error(f"Error determining action by time: {e}")
        # Default to shutdown for safety
        return 'shutdown'


def shutdown_environment(cluster_name: str, environment: str) -> Dict[str, Any]:
    """
    Shutdown all resources in the environment
    
    Args:
        cluster_name: Name of the ECS cluster
        environment: Environment name
        
    Returns:
        Dictionary with shutdown results
    """
    results = {
        'ecs_services': {},
        'lambda_functions': {},
        'total_resources_shutdown': 0,
        'estimated_cost_savings': 0.0
    }
    
    # Shutdown ECS services
    ecs_result = shutdown_services(cluster_name)
    results['ecs_services'] = ecs_result
    results['total_resources_shutdown'] += ecs_result.get('services_shutdown', 0)
    
    # Scale down Lambda concurrency (if configured)
    lambda_result = scale_down_lambda_functions(environment)
    results['lambda_functions'] = lambda_result
    results['total_resources_shutdown'] += lambda_result.get('functions_scaled', 0)
    
    # Calculate estimated cost savings
    results['estimated_cost_savings'] = calculate_shutdown_savings(results)
    
    logger.info(f"Environment shutdown complete. Resources affected: {results['total_resources_shutdown']}")
    
    return results


def startup_environment(cluster_name: str, environment: str) -> Dict[str, Any]:
    """
    Startup all resources in the environment
    
    Args:
        cluster_name: Name of the ECS cluster
        environment: Environment name
        
    Returns:
        Dictionary with startup results
    """
    results = {
        'ecs_services': {},
        'lambda_functions': {},
        'total_resources_started': 0
    }
    
    # Startup ECS services
    ecs_result = startup_services(cluster_name)
    results['ecs_services'] = ecs_result
    results['total_resources_started'] += ecs_result.get('services_started', 0)
    
    # Restore Lambda concurrency
    lambda_result = restore_lambda_functions(environment)
    results['lambda_functions'] = lambda_result
    results['total_resources_started'] += lambda_result.get('functions_restored', 0)
    
    logger.info(f"Environment startup complete. Resources affected: {results['total_resources_started']}")
    
    return results


def get_environment_status(cluster_name: str, environment: str) -> Dict[str, Any]:
    """
    Get current status of environment resources
    
    Args:
        cluster_name: Name of the ECS cluster
        environment: Environment name
        
    Returns:
        Dictionary with environment status
    """
    status = {
        'environment': environment,
        'timestamp': datetime.utcnow().isoformat() + 'Z',
        'ecs_services': [],
        'lambda_functions': [],
        'overall_status': 'unknown'
    }
    
    try:
        # Get ECS service status
        services_response = ecs_client.list_services(cluster=cluster_name)
        for service_arn in services_response.get('serviceArns', []):
            describe_response = ecs_client.describe_services(
                cluster=cluster_name,
                services=[service_arn]
            )
            
            if describe_response['services']:
                service = describe_response['services'][0]
                status['ecs_services'].append({
                    'name': service['serviceName'],
                    'desired_count': service['desiredCount'],
                    'running_count': service['runningCount'],
                    'status': 'active' if service['desiredCount'] > 0 else 'inactive'
                })
        
        # Get Lambda function status (simplified)
        lambda_functions = get_environment_lambda_functions(environment)
        for func_name in lambda_functions:
            try:
                response = lambda_client.get_function(FunctionName=func_name)
                config = response['Configuration']
                status['lambda_functions'].append({
                    'name': func_name,
                    'state': config.get('State', 'Unknown'),
                    'last_modified': config.get('LastModified', 'Unknown')
                })
            except Exception as e:
                logger.warning(f"Could not get status for Lambda function {func_name}: {e}")
        
        # Determine overall status
        active_ecs = len([s for s in status['ecs_services'] if s['status'] == 'active'])
        total_ecs = len(status['ecs_services'])
        
        if active_ecs == 0:
            status['overall_status'] = 'shutdown'
        elif active_ecs == total_ecs:
            status['overall_status'] = 'active'
        else:
            status['overall_status'] = 'partial'
        
    except Exception as e:
        logger.error(f"Error getting environment status: {e}")
        status['error'] = str(e)
    
    return status


def scale_down_lambda_functions(environment: str) -> Dict[str, Any]:
    """
    Scale down Lambda functions by setting reserved concurrency to 0
    
    Args:
        environment: Environment name
        
    Returns:
        Dictionary with scaling results
    """
    results = {
        'functions_scaled': 0,
        'functions_skipped': 0,
        'errors': []
    }
    
    try:
        lambda_functions = get_environment_lambda_functions(environment)
        
        for func_name in lambda_functions:
            try:
                # Set reserved concurrency to 0 to prevent new invocations
                lambda_client.put_provisioned_concurrency_config(
                    FunctionName=func_name,
                    ProvisionedConcurrencyConfig={
                        'ProvisionedConcurrency': 0
                    }
                )
                results['functions_scaled'] += 1
                logger.info(f"Scaled down Lambda function: {func_name}")
                
            except lambda_client.exceptions.ResourceNotFoundException:
                results['functions_skipped'] += 1
                logger.info(f"Lambda function not found, skipping: {func_name}")
            except Exception as e:
                results['errors'].append(f"Error scaling {func_name}: {str(e)}")
                logger.error(f"Error scaling Lambda function {func_name}: {e}")
    
    except Exception as e:
        results['errors'].append(f"Error getting Lambda functions: {str(e)}")
        logger.error(f"Error in scale_down_lambda_functions: {e}")
    
    return results


def restore_lambda_functions(environment: str) -> Dict[str, Any]:
    """
    Restore Lambda functions by removing concurrency restrictions
    
    Args:
        environment: Environment name
        
    Returns:
        Dictionary with restoration results
    """
    results = {
        'functions_restored': 0,
        'functions_skipped': 0,
        'errors': []
    }
    
    try:
        lambda_functions = get_environment_lambda_functions(environment)
        
        for func_name in lambda_functions:
            try:
                # Remove reserved concurrency restrictions
                lambda_client.delete_provisioned_concurrency_config(
                    FunctionName=func_name
                )
                results['functions_restored'] += 1
                logger.info(f"Restored Lambda function: {func_name}")
                
            except lambda_client.exceptions.ResourceNotFoundException:
                results['functions_skipped'] += 1
                logger.info(f"No concurrency config to remove for: {func_name}")
            except Exception as e:
                results['errors'].append(f"Error restoring {func_name}: {str(e)}")
                logger.error(f"Error restoring Lambda function {func_name}: {e}")
    
    except Exception as e:
        results['errors'].append(f"Error getting Lambda functions: {str(e)}")
        logger.error(f"Error in restore_lambda_functions: {e}")
    
    return results


def get_environment_lambda_functions(environment: str) -> List[str]:
    """
    Get list of Lambda functions for the environment
    
    Args:
        environment: Environment name
        
    Returns:
        List of Lambda function names
    """
    function_names = [
        f"homebrew-bottles-sync-{environment}-orchestrator",
        f"homebrew-bottles-sync-{environment}-sync-worker"
    ]
    
    return function_names


def calculate_shutdown_savings(results: Dict[str, Any]) -> float:
    """
    Calculate estimated cost savings from shutdown
    
    Args:
        results: Shutdown results
        
    Returns:
        Estimated daily cost savings in USD
    """
    # Rough estimates based on typical AWS costs
    ecs_service_cost_per_day = 5.0  # $5 per ECS service per day
    lambda_cost_savings = 0.5  # Minimal savings for Lambda
    
    ecs_services_shutdown = results.get('ecs_services', {}).get('services_shutdown', 0)
    lambda_functions_scaled = results.get('lambda_functions', {}).get('functions_scaled', 0)
    
    estimated_savings = (ecs_services_shutdown * ecs_service_cost_per_day) + (lambda_functions_scaled * lambda_cost_savings)
    
    return round(estimated_savings, 2)


def store_operation_result(environment: str, action: str, result: Dict[str, Any], duration: float):
    """
    Store operation result in SSM Parameter Store for tracking
    
    Args:
        environment: Environment name
        action: Action performed
        result: Operation result
        duration: Operation duration in seconds
    """
    try:
        parameter_name = f"/homebrew-bottles-sync/auto-shutdown/{environment}/last-operation"
        
        operation_data = {
            'action': action,
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'duration_seconds': duration,
            'result': result
        }
        
        ssm_client.put_parameter(
            Name=parameter_name,
            Value=json.dumps(operation_data),
            Type='String',
            Overwrite=True,
            Description=f"Last auto-shutdown operation for {environment}"
        )
        
        logger.info(f"Stored operation result in SSM: {parameter_name}")
        
    except Exception as e:
        logger.error(f"Failed to store operation result in SSM: {e}")


def send_cloudwatch_metrics(environment: str, action: str, result: Dict[str, Any], duration: float):
    """
    Send metrics to CloudWatch for monitoring
    
    Args:
        environment: Environment name
        action: Action performed
        result: Operation result
        duration: Operation duration in seconds
    """
    try:
        namespace = 'HomebrewBottlesSync/AutoShutdown'
        
        metrics = [
            {
                'MetricName': 'OperationDuration',
                'Value': duration,
                'Unit': 'Seconds',
                'Dimensions': [
                    {'Name': 'Environment', 'Value': environment},
                    {'Name': 'Action', 'Value': action}
                ]
            },
            {
                'MetricName': 'ResourcesAffected',
                'Value': result.get('total_resources_shutdown', 0) or result.get('total_resources_started', 0),
                'Unit': 'Count',
                'Dimensions': [
                    {'Name': 'Environment', 'Value': environment},
                    {'Name': 'Action', 'Value': action}
                ]
            }
        ]
        
        if 'estimated_cost_savings' in result:
            metrics.append({
                'MetricName': 'EstimatedCostSavings',
                'Value': result['estimated_cost_savings'],
                'Unit': 'None',
                'Dimensions': [
                    {'Name': 'Environment', 'Value': environment}
                ]
            })
        
        cloudwatch_client.put_metric_data(
            Namespace=namespace,
            MetricData=metrics
        )
        
        logger.info(f"Sent {len(metrics)} metrics to CloudWatch")
        
    except Exception as e:
        logger.error(f"Failed to send CloudWatch metrics: {e}")


def send_error_metrics(environment: str, error_message: str):
    """
    Send error metrics to CloudWatch
    
    Args:
        environment: Environment name
        error_message: Error message
    """
    try:
        cloudwatch_client.put_metric_data(
            Namespace='HomebrewBottlesSync/AutoShutdown',
            MetricData=[
                {
                    'MetricName': 'Errors',
                    'Value': 1,
                    'Unit': 'Count',
                    'Dimensions': [
                        {'Name': 'Environment', 'Value': environment}
                    ]
                }
            ]
        )
    except Exception as e:
        logger.error(f"Failed to send error metrics: {e}")


def shutdown_services(cluster_name: str) -> Dict[str, Any]:
    """
    Shutdown ECS services in the cluster
    
    Args:
        cluster_name: Name of the ECS cluster
        
    Returns:
        Dictionary with shutdown results
    """
    try:
        # List all services in the cluster
        services_response = ecs_client.list_services(cluster=cluster_name)
        service_arns = services_response.get('serviceArns', [])
        
        if not service_arns:
            logger.info(f"No services found in cluster {cluster_name}")
            return {'services_shutdown': 0, 'message': 'No services to shutdown'}
        
        shutdown_results = []
        
        for service_arn in service_arns:
            try:
                # Update service to desired count 0
                response = ecs_client.update_service(
                    cluster=cluster_name,
                    service=service_arn,
                    desiredCount=0
                )
                
                service_name = response['service']['serviceName']
                logger.info(f"Shutdown service {service_name}")
                shutdown_results.append({
                    'service': service_name,
                    'status': 'shutdown',
                    'desired_count': 0
                })
                
            except Exception as e:
                logger.error(f"Failed to shutdown service {service_arn}: {str(e)}")
                shutdown_results.append({
                    'service': service_arn,
                    'status': 'error',
                    'error': str(e)
                })
        
        return {
            'services_shutdown': len([r for r in shutdown_results if r['status'] == 'shutdown']),
            'results': shutdown_results
        }
        
    except Exception as e:
        logger.error(f"Error shutting down services: {str(e)}")
        raise


def startup_services(cluster_name: str) -> Dict[str, Any]:
    """
    Startup ECS services in the cluster
    
    Args:
        cluster_name: Name of the ECS cluster
        
    Returns:
        Dictionary with startup results
    """
    try:
        # List all services in the cluster
        services_response = ecs_client.list_services(cluster=cluster_name)
        service_arns = services_response.get('serviceArns', [])
        
        if not service_arns:
            logger.info(f"No services found in cluster {cluster_name}")
            return {'services_started': 0, 'message': 'No services to startup'}
        
        startup_results = []
        
        for service_arn in service_arns:
            try:
                # Get current service configuration
                describe_response = ecs_client.describe_services(
                    cluster=cluster_name,
                    services=[service_arn]
                )
                
                if not describe_response['services']:
                    continue
                
                service = describe_response['services'][0]
                service_name = service['serviceName']
                current_desired = service['desiredCount']
                
                # Only start services that are currently at 0
                if current_desired == 0:
                    # Update service to desired count 1 (or configured default)
                    response = ecs_client.update_service(
                        cluster=cluster_name,
                        service=service_arn,
                        desiredCount=1
                    )
                    
                    logger.info(f"Started service {service_name}")
                    startup_results.append({
                        'service': service_name,
                        'status': 'started',
                        'desired_count': 1
                    })
                else:
                    logger.info(f"Service {service_name} already running with {current_desired} tasks")
                    startup_results.append({
                        'service': service_name,
                        'status': 'already_running',
                        'desired_count': current_desired
                    })
                
            except Exception as e:
                logger.error(f"Failed to startup service {service_arn}: {str(e)}")
                startup_results.append({
                    'service': service_arn,
                    'status': 'error',
                    'error': str(e)
                })
        
        return {
            'services_started': len([r for r in startup_results if r['status'] == 'started']),
            'results': startup_results
        }
        
    except Exception as e:
        logger.error(f"Error starting up services: {str(e)}")
        raise


if __name__ == "__main__":
    # Test the function locally
    import sys
    
    if len(sys.argv) > 1:
        action = sys.argv[1]
    else:
        action = 'status'
    
    test_event = {
        'action': action
    }
    
    # Mock environment variables for testing
    os.environ['ECS_CLUSTER_NAME'] = 'homebrew-bottles-sync-dev'
    os.environ['ENVIRONMENT'] = 'dev'
    
    print(f"Testing auto-shutdown with action: {action}")
    result = handler(test_event, None)
    print(json.dumps(result, indent=2))