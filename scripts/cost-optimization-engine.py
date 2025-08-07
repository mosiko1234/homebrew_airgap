#!/usr/bin/env python3
"""
Advanced Cost Optimization Engine

Implements comprehensive cost optimization features including:
- Automatic resource sizing based on environment type
- Scheduled shutdown/startup for development environments
- Cost reporting and optimization recommendations
- Resource right-sizing based on usage patterns
"""

import json
import os
import sys
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
import argparse
import boto3
from botocore.exceptions import ClientError, NoCredentialsError
import yaml
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.cost-monitor import CostMonitor
from scripts.notification_config import NotificationConfig
from scripts.notify_deployment import NotificationManager


class CostOptimizationEngine:
    """Advanced cost optimization engine for AWS infrastructure"""
    
    def __init__(self, environment: str, aws_region: str = None):
        self.environment = environment
        self.aws_region = aws_region or os.getenv('AWS_DEFAULT_REGION', 'us-east-1')
        
        # Initialize AWS clients
        try:
            self.session = boto3.Session(region_name=self.aws_region)
            self.ecs_client = self.session.client('ecs')
            self.lambda_client = self.session.client('lambda')
            self.cloudwatch_client = self.session.client('cloudwatch')
            self.application_autoscaling_client = self.session.client('application-autoscaling')
            self.events_client = self.session.client('events')
            self.ssm_client = self.session.client('ssm')
            self.ce_client = self.session.client('ce')
        except (ClientError, NoCredentialsError) as e:
            print(f"Warning: AWS client initialization failed: {e}")
            self.ecs_client = None
            self.lambda_client = None
            self.cloudwatch_client = None
            self.application_autoscaling_client = None
            self.events_client = None
            self.ssm_client = None
            self.ce_client = None
        
        # Initialize cost monitor
        self.cost_monitor = CostMonitor(environment, aws_region)
        
        # Load configuration
        self.config = self._load_optimization_config()
        
        # Environment-specific settings
        self.environment_settings = self._get_environment_settings()
    
    def _load_optimization_config(self) -> Dict[str, Any]:
        """Load cost optimization configuration"""
        config_path = Path(__file__).parent.parent / 'config' / 'cost-optimization.yaml'
        
        default_config = {
            'environments': {
                'dev': {
                    'auto_shutdown': True,
                    'business_hours': {'start': 9, 'end': 18},
                    'weekend_shutdown': True,
                    'resource_scaling': {
                        'ecs_task_cpu': 512,
                        'ecs_task_memory': 1024,
                        'lambda_memory': 256
                    },
                    'cost_threshold': 50.0
                },
                'staging': {
                    'auto_shutdown': False,
                    'resource_scaling': {
                        'ecs_task_cpu': 1024,
                        'ecs_task_memory': 2048,
                        'lambda_memory': 512
                    },
                    'cost_threshold': 200.0
                },
                'prod': {
                    'auto_shutdown': False,
                    'resource_scaling': {
                        'ecs_task_cpu': 2048,
                        'ecs_task_memory': 4096,
                        'lambda_memory': 1024
                    },
                    'cost_threshold': 1000.0
                }
            },
            'optimization_rules': {
                'right_sizing': {
                    'cpu_utilization_threshold': 20,
                    'memory_utilization_threshold': 30,
                    'evaluation_period_days': 7
                },
                'auto_scaling': {
                    'enable_for_environments': ['staging', 'prod'],
                    'scale_down_cooldown': 300,
                    'scale_up_cooldown': 60
                }
            }
        }
        
        try:
            if config_path.exists():
                with open(config_path, 'r') as f:
                    loaded_config = yaml.safe_load(f)
                    # Merge with defaults
                    default_config.update(loaded_config)
        except Exception as e:
            print(f"Warning: Could not load optimization config: {e}")
        
        return default_config
    
    def _get_environment_settings(self) -> Dict[str, Any]:
        """Get environment-specific optimization settings"""
        return self.config.get('environments', {}).get(self.environment, {})
    
    def implement_automatic_resource_sizing(self) -> Dict[str, Any]:
        """Implement automatic resource sizing based on environment type"""
        print(f"🔧 Implementing automatic resource sizing for {self.environment}")
        
        results = {
            'environment': self.environment,
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'ecs_services': [],
            'lambda_functions': [],
            'cost_impact': 0.0,
            'errors': []
        }
        
        try:
            # Get resource scaling configuration
            resource_config = self.environment_settings.get('resource_scaling', {})
            
            if not resource_config:
                results['errors'].append("No resource scaling configuration found")
                return results
            
            # Optimize ECS services
            ecs_results = self._optimize_ecs_resources(resource_config)
            results['ecs_services'] = ecs_results
            
            # Optimize Lambda functions
            lambda_results = self._optimize_lambda_resources(resource_config)
            results['lambda_functions'] = lambda_results
            
            # Calculate cost impact
            results['cost_impact'] = self._calculate_optimization_cost_impact(ecs_results, lambda_results)
            
            print(f"✅ Resource sizing complete. Estimated monthly savings: ${results['cost_impact']:.2f}")
            
        except Exception as e:
            error_msg = f"Error implementing resource sizing: {e}"
            results['errors'].append(error_msg)
            print(f"❌ {error_msg}")
        
        return results
    
    def _optimize_ecs_resources(self, resource_config: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Optimize ECS service resources"""
        if not self.ecs_client:
            return [{'error': 'ECS client not available'}]
        
        results = []
        cluster_name = f"homebrew-bottles-sync-{self.environment}"
        
        try:
            # List services in cluster
            services_response = self.ecs_client.list_services(cluster=cluster_name)
            
            for service_arn in services_response.get('serviceArns', []):
                try:
                    # Get current service configuration
                    service_response = self.ecs_client.describe_services(
                        cluster=cluster_name,
                        services=[service_arn]
                    )
                    
                    if not service_response['services']:
                        continue
                    
                    service = service_response['services'][0]
                    service_name = service['serviceName']
                    
                    # Get task definition
                    task_def_arn = service['taskDefinition']
                    task_def_response = self.ecs_client.describe_task_definition(
                        taskDefinition=task_def_arn
                    )
                    
                    task_def = task_def_response['taskDefinition']
                    current_cpu = int(task_def.get('cpu', 256))
                    current_memory = int(task_def.get('memory', 512))
                    
                    # Get target resources from config
                    target_cpu = resource_config.get('ecs_task_cpu', current_cpu)
                    target_memory = resource_config.get('ecs_task_memory', current_memory)
                    
                    # Check if optimization is needed
                    if current_cpu != target_cpu or current_memory != target_memory:
                        # Create new task definition with optimized resources
                        new_task_def = self._create_optimized_task_definition(
                            task_def, target_cpu, target_memory
                        )
                        
                        # Register new task definition
                        register_response = self.ecs_client.register_task_definition(**new_task_def)
                        new_task_def_arn = register_response['taskDefinition']['taskDefinitionArn']
                        
                        # Update service to use new task definition
                        self.ecs_client.update_service(
                            cluster=cluster_name,
                            service=service_arn,
                            taskDefinition=new_task_def_arn
                        )
                        
                        results.append({
                            'service_name': service_name,
                            'status': 'optimized',
                            'changes': {
                                'cpu': {'from': current_cpu, 'to': target_cpu},
                                'memory': {'from': current_memory, 'to': target_memory}
                            },
                            'estimated_monthly_savings': self._calculate_ecs_savings(
                                current_cpu, current_memory, target_cpu, target_memory
                            )
                        })
                        
                        print(f"  ✅ Optimized ECS service {service_name}: CPU {current_cpu}→{target_cpu}, Memory {current_memory}→{target_memory}")
                    else:
                        results.append({
                            'service_name': service_name,
                            'status': 'already_optimized',
                            'current_resources': {'cpu': current_cpu, 'memory': current_memory}
                        })
                
                except Exception as e:
                    results.append({
                        'service_arn': service_arn,
                        'status': 'error',
                        'error': str(e)
                    })
        
        except Exception as e:
            results.append({'error': f"Failed to optimize ECS resources: {e}"})
        
        return results
    
    def _optimize_lambda_resources(self, resource_config: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Optimize Lambda function resources"""
        if not self.lambda_client:
            return [{'error': 'Lambda client not available'}]
        
        results = []
        target_memory = resource_config.get('lambda_memory', 512)
        
        # Get Lambda functions for this environment
        function_names = [
            f"homebrew-bottles-sync-{self.environment}-orchestrator",
            f"homebrew-bottles-sync-{self.environment}-sync-worker"
        ]
        
        for func_name in function_names:
            try:
                # Get current function configuration
                response = self.lambda_client.get_function_configuration(FunctionName=func_name)
                current_memory = response['MemorySize']
                
                if current_memory != target_memory:
                    # Update function configuration
                    self.lambda_client.update_function_configuration(
                        FunctionName=func_name,
                        MemorySize=target_memory
                    )
                    
                    results.append({
                        'function_name': func_name,
                        'status': 'optimized',
                        'changes': {
                            'memory': {'from': current_memory, 'to': target_memory}
                        },
                        'estimated_monthly_savings': self._calculate_lambda_savings(
                            current_memory, target_memory
                        )
                    })
                    
                    print(f"  ✅ Optimized Lambda function {func_name}: Memory {current_memory}→{target_memory}MB")
                else:
                    results.append({
                        'function_name': func_name,
                        'status': 'already_optimized',
                        'current_memory': current_memory
                    })
            
            except self.lambda_client.exceptions.ResourceNotFoundException:
                results.append({
                    'function_name': func_name,
                    'status': 'not_found'
                })
            except Exception as e:
                results.append({
                    'function_name': func_name,
                    'status': 'error',
                    'error': str(e)
                })
        
        return results
    
    def setup_scheduled_shutdown_startup(self) -> Dict[str, Any]:
        """Set up scheduled shutdown/startup for development environments"""
        print(f"⏰ Setting up scheduled shutdown/startup for {self.environment}")
        
        if self.environment != 'dev':
            return {'error': 'Scheduled shutdown only available for dev environment'}
        
        if not self.environment_settings.get('auto_shutdown', False):
            return {'error': 'Auto shutdown not enabled for this environment'}
        
        results = {
            'environment': self.environment,
            'rules_created': [],
            'errors': []
        }
        
        try:
            business_hours = self.environment_settings.get('business_hours', {'start': 9, 'end': 18})
            
            # Create shutdown rule (after business hours)
            shutdown_rule = self._create_eventbridge_rule(
                name=f"homebrew-sync-{self.environment}-shutdown",
                description=f"Shutdown {self.environment} environment after business hours",
                schedule_expression=f"cron(0 {business_hours['end']} * * MON-FRI *)",
                target_action='shutdown'
            )
            
            if shutdown_rule:
                results['rules_created'].append(shutdown_rule)
            
            # Create startup rule (before business hours)
            startup_rule = self._create_eventbridge_rule(
                name=f"homebrew-sync-{self.environment}-startup",
                description=f"Startup {self.environment} environment before business hours",
                schedule_expression=f"cron(0 {business_hours['start']} * * MON-FRI *)",
                target_action='startup'
            )
            
            if startup_rule:
                results['rules_created'].append(startup_rule)
            
            # Create weekend shutdown rule
            if self.environment_settings.get('weekend_shutdown', True):
                weekend_shutdown_rule = self._create_eventbridge_rule(
                    name=f"homebrew-sync-{self.environment}-weekend-shutdown",
                    description=f"Shutdown {self.environment} environment on weekends",
                    schedule_expression="cron(0 18 * * FRI *)",  # Friday evening
                    target_action='shutdown'
                )
                
                if weekend_shutdown_rule:
                    results['rules_created'].append(weekend_shutdown_rule)
                
                # Monday morning startup
                monday_startup_rule = self._create_eventbridge_rule(
                    name=f"homebrew-sync-{self.environment}-monday-startup",
                    description=f"Startup {self.environment} environment on Monday morning",
                    schedule_expression=f"cron(0 {business_hours['start']} * * MON *)",
                    target_action='startup'
                )
                
                if monday_startup_rule:
                    results['rules_created'].append(monday_startup_rule)
            
            print(f"✅ Created {len(results['rules_created'])} scheduled rules")
            
        except Exception as e:
            error_msg = f"Error setting up scheduled shutdown/startup: {e}"
            results['errors'].append(error_msg)
            print(f"❌ {error_msg}")
        
        return results
    
    def _create_eventbridge_rule(self, name: str, description: str, schedule_expression: str, target_action: str) -> Optional[Dict[str, Any]]:
        """Create EventBridge rule for scheduled actions"""
        if not self.events_client:
            return None
        
        try:
            # Create the rule
            rule_response = self.events_client.put_rule(
                Name=name,
                ScheduleExpression=schedule_expression,
                Description=description,
                State='ENABLED'
            )
            
            # Add target (Lambda function for auto-shutdown)
            lambda_function_name = f"homebrew-bottles-sync-{self.environment}-auto-shutdown"
            
            self.events_client.put_targets(
                Rule=name,
                Targets=[
                    {
                        'Id': '1',
                        'Arn': f"arn:aws:lambda:{self.aws_region}:{self._get_account_id()}:function:{lambda_function_name}",
                        'Input': json.dumps({'action': target_action})
                    }
                ]
            )
            
            return {
                'name': name,
                'arn': rule_response['RuleArn'],
                'schedule': schedule_expression,
                'action': target_action
            }
        
        except Exception as e:
            print(f"❌ Failed to create EventBridge rule {name}: {e}")
            return None
    
    def generate_cost_optimization_report(self, days: int = 30) -> Dict[str, Any]:
        """Generate comprehensive cost optimization report"""
        print(f"📊 Generating cost optimization report for {self.environment}")
        
        # Get base cost report
        cost_report = self.cost_monitor.generate_cost_report(days)
        
        # Add optimization-specific analysis
        optimization_report = {
            'base_cost_analysis': cost_report,
            'optimization_opportunities': self._analyze_optimization_opportunities(),
            'resource_utilization': self._analyze_resource_utilization(),
            'right_sizing_recommendations': self._generate_right_sizing_recommendations(),
            'potential_savings': self._calculate_potential_savings(),
            'implementation_plan': self._generate_implementation_plan()
        }
        
        return optimization_report
    
    def _analyze_optimization_opportunities(self) -> List[Dict[str, Any]]:
        """Analyze optimization opportunities"""
        opportunities = []
        
        # Environment-specific opportunities
        if self.environment == 'dev':
            opportunities.append({
                'type': 'scheduled_shutdown',
                'priority': 'high',
                'potential_savings_percentage': 60,
                'description': 'Implement scheduled shutdown during non-business hours',
                'implementation_effort': 'low',
                'estimated_setup_time': '2 hours'
            })
        
        # Resource right-sizing opportunities
        utilization_data = self._get_resource_utilization_data()
        
        if utilization_data.get('avg_cpu_utilization', 100) < 30:
            opportunities.append({
                'type': 'cpu_right_sizing',
                'priority': 'medium',
                'potential_savings_percentage': 25,
                'description': 'Reduce CPU allocation based on low utilization',
                'current_utilization': f"{utilization_data.get('avg_cpu_utilization', 0):.1f}%",
                'implementation_effort': 'medium'
            })
        
        if utilization_data.get('avg_memory_utilization', 100) < 40:
            opportunities.append({
                'type': 'memory_right_sizing',
                'priority': 'medium',
                'potential_savings_percentage': 20,
                'description': 'Reduce memory allocation based on low utilization',
                'current_utilization': f"{utilization_data.get('avg_memory_utilization', 0):.1f}%",
                'implementation_effort': 'medium'
            })
        
        # Spot instance opportunities
        if self.environment in ['dev', 'staging']:
            opportunities.append({
                'type': 'spot_instances',
                'priority': 'medium',
                'potential_savings_percentage': 50,
                'description': 'Use Spot instances for non-critical workloads',
                'implementation_effort': 'high',
                'risk_level': 'medium'
            })
        
        return opportunities
    
    def _analyze_resource_utilization(self) -> Dict[str, Any]:
        """Analyze current resource utilization"""
        if not self.cloudwatch_client:
            return {'error': 'CloudWatch client not available'}
        
        utilization = {
            'period_days': 7,
            'ecs_services': [],
            'lambda_functions': [],
            'overall_efficiency': 0.0
        }
        
        try:
            # Analyze ECS service utilization
            cluster_name = f"homebrew-bottles-sync-{self.environment}"
            ecs_utilization = self._get_ecs_utilization(cluster_name)
            utilization['ecs_services'] = ecs_utilization
            
            # Analyze Lambda function utilization
            lambda_utilization = self._get_lambda_utilization()
            utilization['lambda_functions'] = lambda_utilization
            
            # Calculate overall efficiency
            all_cpu_utils = [s.get('avg_cpu_utilization', 0) for s in ecs_utilization]
            all_memory_utils = [s.get('avg_memory_utilization', 0) for s in ecs_utilization]
            
            if all_cpu_utils or all_memory_utils:
                avg_cpu = sum(all_cpu_utils) / len(all_cpu_utils) if all_cpu_utils else 0
                avg_memory = sum(all_memory_utils) / len(all_memory_utils) if all_memory_utils else 0
                utilization['overall_efficiency'] = (avg_cpu + avg_memory) / 2
        
        except Exception as e:
            utilization['error'] = str(e)
        
        return utilization
    
    def _get_ecs_utilization(self, cluster_name: str) -> List[Dict[str, Any]]:
        """Get ECS service utilization metrics"""
        utilization_data = []
        
        try:
            # Get services in cluster
            services_response = self.ecs_client.list_services(cluster=cluster_name)
            
            for service_arn in services_response.get('serviceArns', []):
                service_response = self.ecs_client.describe_services(
                    cluster=cluster_name,
                    services=[service_arn]
                )
                
                if not service_response['services']:
                    continue
                
                service = service_response['services'][0]
                service_name = service['serviceName']
                
                # Get CloudWatch metrics for the service
                end_time = datetime.utcnow()
                start_time = end_time - timedelta(days=7)
                
                # CPU utilization
                cpu_response = self.cloudwatch_client.get_metric_statistics(
                    Namespace='AWS/ECS',
                    MetricName='CPUUtilization',
                    Dimensions=[
                        {'Name': 'ServiceName', 'Value': service_name},
                        {'Name': 'ClusterName', 'Value': cluster_name}
                    ],
                    StartTime=start_time,
                    EndTime=end_time,
                    Period=3600,  # 1 hour
                    Statistics=['Average']
                )
                
                # Memory utilization
                memory_response = self.cloudwatch_client.get_metric_statistics(
                    Namespace='AWS/ECS',
                    MetricName='MemoryUtilization',
                    Dimensions=[
                        {'Name': 'ServiceName', 'Value': service_name},
                        {'Name': 'ClusterName', 'Value': cluster_name}
                    ],
                    StartTime=start_time,
                    EndTime=end_time,
                    Period=3600,  # 1 hour
                    Statistics=['Average']
                )
                
                # Calculate averages
                cpu_values = [dp['Average'] for dp in cpu_response.get('Datapoints', [])]
                memory_values = [dp['Average'] for dp in memory_response.get('Datapoints', [])]
                
                avg_cpu = sum(cpu_values) / len(cpu_values) if cpu_values else 0
                avg_memory = sum(memory_values) / len(memory_values) if memory_values else 0
                
                utilization_data.append({
                    'service_name': service_name,
                    'avg_cpu_utilization': round(avg_cpu, 2),
                    'avg_memory_utilization': round(avg_memory, 2),
                    'max_cpu_utilization': round(max(cpu_values), 2) if cpu_values else 0,
                    'max_memory_utilization': round(max(memory_values), 2) if memory_values else 0,
                    'data_points': len(cpu_values)
                })
        
        except Exception as e:
            print(f"Warning: Could not get ECS utilization data: {e}")
        
        return utilization_data
    
    def _get_lambda_utilization(self) -> List[Dict[str, Any]]:
        """Get Lambda function utilization metrics"""
        utilization_data = []
        
        function_names = [
            f"homebrew-bottles-sync-{self.environment}-orchestrator",
            f"homebrew-bottles-sync-{self.environment}-sync-worker"
        ]
        
        for func_name in function_names:
            try:
                end_time = datetime.utcnow()
                start_time = end_time - timedelta(days=7)
                
                # Get invocation count
                invocations_response = self.cloudwatch_client.get_metric_statistics(
                    Namespace='AWS/Lambda',
                    MetricName='Invocations',
                    Dimensions=[{'Name': 'FunctionName', 'Value': func_name}],
                    StartTime=start_time,
                    EndTime=end_time,
                    Period=3600,
                    Statistics=['Sum']
                )
                
                # Get duration
                duration_response = self.cloudwatch_client.get_metric_statistics(
                    Namespace='AWS/Lambda',
                    MetricName='Duration',
                    Dimensions=[{'Name': 'FunctionName', 'Value': func_name}],
                    StartTime=start_time,
                    EndTime=end_time,
                    Period=3600,
                    Statistics=['Average']
                )
                
                invocation_values = [dp['Sum'] for dp in invocations_response.get('Datapoints', [])]
                duration_values = [dp['Average'] for dp in duration_response.get('Datapoints', [])]
                
                total_invocations = sum(invocation_values)
                avg_duration = sum(duration_values) / len(duration_values) if duration_values else 0
                
                utilization_data.append({
                    'function_name': func_name,
                    'total_invocations': int(total_invocations),
                    'avg_duration_ms': round(avg_duration, 2),
                    'invocations_per_day': round(total_invocations / 7, 2)
                })
            
            except Exception as e:
                utilization_data.append({
                    'function_name': func_name,
                    'error': str(e)
                })
        
        return utilization_data
    
    def _get_resource_utilization_data(self) -> Dict[str, float]:
        """Get aggregated resource utilization data"""
        utilization = self._analyze_resource_utilization()
        
        if 'error' in utilization:
            return {}
        
        ecs_services = utilization.get('ecs_services', [])
        
        if not ecs_services:
            return {}
        
        avg_cpu = sum(s.get('avg_cpu_utilization', 0) for s in ecs_services) / len(ecs_services)
        avg_memory = sum(s.get('avg_memory_utilization', 0) for s in ecs_services) / len(ecs_services)
        
        return {
            'avg_cpu_utilization': avg_cpu,
            'avg_memory_utilization': avg_memory
        }
    
    def _generate_right_sizing_recommendations(self) -> List[Dict[str, Any]]:
        """Generate right-sizing recommendations based on utilization"""
        recommendations = []
        
        utilization = self._analyze_resource_utilization()
        
        if 'error' in utilization:
            return recommendations
        
        for service in utilization.get('ecs_services', []):
            service_name = service.get('service_name', 'unknown')
            avg_cpu = service.get('avg_cpu_utilization', 0)
            avg_memory = service.get('avg_memory_utilization', 0)
            
            # CPU right-sizing
            if avg_cpu < 20:
                recommendations.append({
                    'type': 'cpu_downsize',
                    'resource': service_name,
                    'current_utilization': f"{avg_cpu:.1f}%",
                    'recommended_action': 'Reduce CPU allocation by 25-50%',
                    'potential_savings': '15-30%',
                    'confidence': 'high' if avg_cpu < 10 else 'medium'
                })
            elif avg_cpu > 80:
                recommendations.append({
                    'type': 'cpu_upsize',
                    'resource': service_name,
                    'current_utilization': f"{avg_cpu:.1f}%",
                    'recommended_action': 'Increase CPU allocation by 25-50%',
                    'reason': 'High CPU utilization may impact performance',
                    'confidence': 'high'
                })
            
            # Memory right-sizing
            if avg_memory < 30:
                recommendations.append({
                    'type': 'memory_downsize',
                    'resource': service_name,
                    'current_utilization': f"{avg_memory:.1f}%",
                    'recommended_action': 'Reduce memory allocation by 25-40%',
                    'potential_savings': '10-25%',
                    'confidence': 'high' if avg_memory < 15 else 'medium'
                })
            elif avg_memory > 85:
                recommendations.append({
                    'type': 'memory_upsize',
                    'resource': service_name,
                    'current_utilization': f"{avg_memory:.1f}%",
                    'recommended_action': 'Increase memory allocation by 25-50%',
                    'reason': 'High memory utilization may cause OOM errors',
                    'confidence': 'high'
                })
        
        return recommendations
    
    def _calculate_potential_savings(self) -> Dict[str, Any]:
        """Calculate potential cost savings from optimizations"""
        # Get current costs
        current_costs = self.cost_monitor.get_current_month_costs()
        
        if 'error' in current_costs:
            return {'error': current_costs['error']}
        
        total_current_cost = current_costs.get('total_cost', 0)
        
        # Calculate savings from different optimization strategies
        savings = {
            'total_current_monthly_cost': total_current_cost,
            'optimization_strategies': []
        }
        
        # Scheduled shutdown savings (dev environment)
        if self.environment == 'dev' and self.environment_settings.get('auto_shutdown', False):
            shutdown_savings = total_current_cost * 0.6  # 60% savings
            savings['optimization_strategies'].append({
                'strategy': 'scheduled_shutdown',
                'monthly_savings': round(shutdown_savings, 2),
                'percentage_savings': 60,
                'implementation_effort': 'low'
            })
        
        # Right-sizing savings
        utilization_data = self._get_resource_utilization_data()
        if utilization_data:
            avg_cpu_util = utilization_data.get('avg_cpu_utilization', 100)
            avg_memory_util = utilization_data.get('avg_memory_utilization', 100)
            
            if avg_cpu_util < 30 or avg_memory_util < 40:
                rightsizing_savings = total_current_cost * 0.25  # 25% savings
                savings['optimization_strategies'].append({
                    'strategy': 'resource_right_sizing',
                    'monthly_savings': round(rightsizing_savings, 2),
                    'percentage_savings': 25,
                    'implementation_effort': 'medium',
                    'current_cpu_utilization': f"{avg_cpu_util:.1f}%",
                    'current_memory_utilization': f"{avg_memory_util:.1f}%"
                })
        
        # Spot instance savings (non-prod environments)
        if self.environment in ['dev', 'staging']:
            spot_savings = total_current_cost * 0.5  # 50% savings on compute
            savings['optimization_strategies'].append({
                'strategy': 'spot_instances',
                'monthly_savings': round(spot_savings, 2),
                'percentage_savings': 50,
                'implementation_effort': 'high',
                'risk_level': 'medium'
            })
        
        # Calculate total potential savings
        total_savings = sum(s['monthly_savings'] for s in savings['optimization_strategies'])
        savings['total_potential_monthly_savings'] = round(total_savings, 2)
        savings['total_potential_percentage_savings'] = round((total_savings / total_current_cost * 100), 1) if total_current_cost > 0 else 0
        
        return savings
    
    def _generate_implementation_plan(self) -> List[Dict[str, Any]]:
        """Generate step-by-step implementation plan"""
        plan = []
        
        # Phase 1: Quick wins
        plan.append({
            'phase': 1,
            'title': 'Quick Wins (Week 1)',
            'tasks': [
                {
                    'task': 'Implement scheduled shutdown for dev environment',
                    'effort': 'low',
                    'impact': 'high',
                    'estimated_time': '2 hours',
                    'potential_savings': '60%'
                },
                {
                    'task': 'Review and optimize Lambda memory settings',
                    'effort': 'low',
                    'impact': 'medium',
                    'estimated_time': '1 hour',
                    'potential_savings': '10-15%'
                }
            ]
        })
        
        # Phase 2: Resource optimization
        plan.append({
            'phase': 2,
            'title': 'Resource Optimization (Week 2-3)',
            'tasks': [
                {
                    'task': 'Implement ECS resource right-sizing',
                    'effort': 'medium',
                    'impact': 'high',
                    'estimated_time': '4 hours',
                    'potential_savings': '20-30%'
                },
                {
                    'task': 'Set up auto-scaling policies',
                    'effort': 'medium',
                    'impact': 'medium',
                    'estimated_time': '3 hours',
                    'potential_savings': '15-25%'
                }
            ]
        })
        
        # Phase 3: Advanced optimizations
        if self.environment in ['dev', 'staging']:
            plan.append({
                'phase': 3,
                'title': 'Advanced Optimizations (Week 4)',
                'tasks': [
                    {
                        'task': 'Implement Spot instances for ECS tasks',
                        'effort': 'high',
                        'impact': 'high',
                        'estimated_time': '8 hours',
                        'potential_savings': '40-60%',
                        'risk': 'medium'
                    },
                    {
                        'task': 'Set up cost monitoring and alerting',
                        'effort': 'medium',
                        'impact': 'medium',
                        'estimated_time': '3 hours',
                        'benefit': 'Ongoing cost visibility'
                    }
                ]
            })
        
        return plan
    
    def _create_optimized_task_definition(self, task_def: Dict[str, Any], target_cpu: int, target_memory: int) -> Dict[str, Any]:
        """Create optimized task definition with new resource allocations"""
        # Remove read-only fields
        new_task_def = {
            'family': task_def['family'],
            'taskRoleArn': task_def.get('taskRoleArn'),
            'executionRoleArn': task_def.get('executionRoleArn'),
            'networkMode': task_def.get('networkMode'),
            'requiresCompatibilities': task_def.get('requiresCompatibilities', []),
            'cpu': str(target_cpu),
            'memory': str(target_memory),
            'containerDefinitions': task_def['containerDefinitions']
        }
        
        # Remove None values
        new_task_def = {k: v for k, v in new_task_def.items() if v is not None}
        
        return new_task_def
    
    def _calculate_ecs_savings(self, current_cpu: int, current_memory: int, target_cpu: int, target_memory: int) -> float:
        """Calculate estimated monthly savings from ECS optimization"""
        # Rough calculation based on Fargate pricing
        # CPU: ~$0.04048 per vCPU per hour
        # Memory: ~$0.004445 per GB per hour
        
        cpu_diff = (current_cpu - target_cpu) / 1024  # Convert to vCPUs
        memory_diff = (current_memory - target_memory) / 1024  # Convert to GB
        
        hours_per_month = 24 * 30  # Assume 30 days
        
        cpu_savings = cpu_diff * 0.04048 * hours_per_month
        memory_savings = memory_diff * 0.004445 * hours_per_month
        
        return max(0, cpu_savings + memory_savings)
    
    def _calculate_lambda_savings(self, current_memory: int, target_memory: int) -> float:
        """Calculate estimated monthly savings from Lambda optimization"""
        # Lambda pricing is based on GB-seconds
        # Assume average execution time and invocations
        
        memory_diff_gb = (current_memory - target_memory) / 1024
        
        # Rough estimate: 1000 invocations per month, 5 seconds average duration
        gb_seconds_saved = memory_diff_gb * 5 * 1000
        
        # Lambda pricing: ~$0.0000166667 per GB-second
        savings = gb_seconds_saved * 0.0000166667
        
        return max(0, savings)
    
    def _calculate_optimization_cost_impact(self, ecs_results: List[Dict], lambda_results: List[Dict]) -> float:
        """Calculate total cost impact from optimizations"""
        total_savings = 0.0
        
        # Sum ECS savings
        for result in ecs_results:
            if result.get('status') == 'optimized':
                total_savings += result.get('estimated_monthly_savings', 0)
        
        # Sum Lambda savings
        for result in lambda_results:
            if result.get('status') == 'optimized':
                total_savings += result.get('estimated_monthly_savings', 0)
        
        return round(total_savings, 2)
    
    def _get_account_id(self) -> str:
        """Get AWS account ID"""
        try:
            sts_client = self.session.client('sts')
            return sts_client.get_caller_identity()['Account']
        except Exception:
            return '123456789012'  # Fallback


def format_optimization_report(report: Dict[str, Any]) -> str:
    """Format optimization report into readable text"""
    lines = []
    lines.append("=" * 80)
    lines.append("COST OPTIMIZATION REPORT")
    lines.append("=" * 80)
    
    base_report = report.get('base_cost_analysis', {})
    lines.append(f"Environment: {base_report.get('environment', 'unknown').upper()}")
    lines.append(f"Generated: {base_report.get('generated_at', 'unknown')}")
    lines.append("")
    
    # Current costs
    current_month = base_report.get('current_month', {})
    if 'error' not in current_month:
        lines.append("💰 CURRENT COSTS:")
        lines.append(f"  Monthly Cost: ${current_month.get('total_cost', 0):.2f}")
        lines.append("")
    
    # Optimization opportunities
    opportunities = report.get('optimization_opportunities', [])
    if opportunities:
        lines.append("🎯 OPTIMIZATION OPPORTUNITIES:")
        for i, opp in enumerate(opportunities, 1):
            priority_icon = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(opp.get('priority', 'medium'), "🟡")
            lines.append(f"  {i}. {priority_icon} {opp.get('description', 'No description')}")
            lines.append(f"     Potential Savings: {opp.get('potential_savings_percentage', 0)}%")
            lines.append(f"     Implementation: {opp.get('implementation_effort', 'unknown')} effort")
        lines.append("")
    
    # Potential savings
    savings = report.get('potential_savings', {})
    if 'error' not in savings:
        lines.append("💡 POTENTIAL SAVINGS:")
        lines.append(f"  Total Monthly Savings: ${savings.get('total_potential_monthly_savings', 0):.2f}")
        lines.append(f"  Percentage Savings: {savings.get('total_potential_percentage_savings', 0):.1f}%")
        
        strategies = savings.get('optimization_strategies', [])
        if strategies:
            lines.append("  Breakdown by Strategy:")
            for strategy in strategies:
                lines.append(f"    • {strategy.get('strategy', 'unknown')}: ${strategy.get('monthly_savings', 0):.2f} ({strategy.get('percentage_savings', 0)}%)")
        lines.append("")
    
    # Implementation plan
    plan = report.get('implementation_plan', [])
    if plan:
        lines.append("📋 IMPLEMENTATION PLAN:")
        for phase in plan:
            lines.append(f"  Phase {phase.get('phase', 0)}: {phase.get('title', 'Unknown')}")
            for task in phase.get('tasks', []):
                lines.append(f"    • {task.get('task', 'Unknown task')}")
                lines.append(f"      Effort: {task.get('effort', 'unknown')}, Impact: {task.get('impact', 'unknown')}")
        lines.append("")
    
    lines.append("=" * 80)
    
    return "\n".join(lines)


def main():
    """Main CLI interface for cost optimization engine"""
    parser = argparse.ArgumentParser(description="Advanced cost optimization engine")
    parser.add_argument("--environment", required=True,
                       choices=["dev", "staging", "prod"],
                       help="Environment to optimize")
    parser.add_argument("--aws-region", help="AWS region (default: from environment)")
    
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Resource sizing command
    subparsers.add_parser("resource-sizing", help="Implement automatic resource sizing")
    
    # Scheduled shutdown command
    subparsers.add_parser("setup-scheduling", help="Set up scheduled shutdown/startup")
    
    # Optimization report command
    report_parser = subparsers.add_parser("optimization-report", help="Generate optimization report")
    report_parser.add_argument("--days", type=int, default=30, help="Report period in days")
    report_parser.add_argument("--output-format", choices=["text", "json"], default="text")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    # Initialize optimization engine
    engine = CostOptimizationEngine(args.environment, args.aws_region)
    
    try:
        if args.command == "resource-sizing":
            result = engine.implement_automatic_resource_sizing()
            print(json.dumps(result, indent=2))
        
        elif args.command == "setup-scheduling":
            result = engine.setup_scheduled_shutdown_startup()
            print(json.dumps(result, indent=2))
        
        elif args.command == "optimization-report":
            result = engine.generate_cost_optimization_report(args.days)
            
            if args.output_format == "json":
                print(json.dumps(result, indent=2))
            else:
                print(format_optimization_report(result))
    
    except KeyboardInterrupt:
        print("\n🛑 Cost optimization interrupted")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Cost optimization failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()