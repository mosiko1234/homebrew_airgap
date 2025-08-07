#!/usr/bin/env python3
"""
Configuration Processor for Homebrew Bottles Sync System
Validates config.yaml and generates environment-specific terraform.tfvars files
"""

import yaml
import json
import os
import sys
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from pathlib import Path


@dataclass
class ValidationError:
    field: str
    message: str
    fix_suggestion: str


class ConfigProcessor:
    """Processes and validates the central configuration file"""
    
    def __init__(self, config_path: str = "config.yaml"):
        self.config_path = config_path
        self.config = None
        self.validation_errors = []
        
    def load_config(self) -> Dict[str, Any]:
        """Load configuration from YAML file"""
        try:
            with open(self.config_path, 'r') as file:
                self.config = yaml.safe_load(file)
                return self.config
        except FileNotFoundError:
            raise FileNotFoundError(f"Configuration file not found: {self.config_path}")
        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML syntax in {self.config_path}: {e}")
    
    def validate_config(self) -> List[ValidationError]:
        """Validate the configuration and return list of errors"""
        if not self.config:
            self.load_config()
            
        self.validation_errors = []
        
        # Validate required top-level sections
        required_sections = ['project', 'environments', 'resources', 'notifications']
        for section in required_sections:
            if section not in self.config:
                self.validation_errors.append(ValidationError(
                    field=section,
                    message=f"Missing required section: {section}",
                    fix_suggestion=f"Add '{section}:' section to config.yaml"
                ))
        
        # Validate project section
        if 'project' in self.config:
            self._validate_project_section()
        
        # Validate environments section
        if 'environments' in self.config:
            self._validate_environments_section()
        
        # Validate resources section
        if 'resources' in self.config:
            self._validate_resources_section()
        
        # Validate notifications section
        if 'notifications' in self.config:
            self._validate_notifications_section()
        
        return self.validation_errors
    
    def _validate_project_section(self):
        """Validate project configuration section"""
        project = self.config['project']
        required_fields = ['name', 'description']
        
        for field in required_fields:
            if field not in project:
                self.validation_errors.append(ValidationError(
                    field=f"project.{field}",
                    message=f"Missing required field: project.{field}",
                    fix_suggestion=f"Add 'project.{field}: <value>' to config.yaml"
                ))
    
    def _validate_environments_section(self):
        """Validate environments configuration section"""
        environments = self.config['environments']
        required_envs = ['dev', 'staging', 'prod']
        
        for env in required_envs:
            if env not in environments:
                self.validation_errors.append(ValidationError(
                    field=f"environments.{env}",
                    message=f"Missing required environment: {env}",
                    fix_suggestion=f"Add 'environments.{env}:' section to config.yaml"
                ))
                continue
            
            self._validate_environment_config(env, environments[env])
    
    def _validate_environment_config(self, env_name: str, env_config: Dict):
        """Validate individual environment configuration"""
        required_fields = ['aws_region', 'size_threshold_gb', 'schedule_expression', 'enable_fargate_spot']
        
        for field in required_fields:
            if field not in env_config:
                self.validation_errors.append(ValidationError(
                    field=f"environments.{env_name}.{field}",
                    message=f"Missing required field: environments.{env_name}.{field}",
                    fix_suggestion=f"Add '{field}: <value>' to environments.{env_name} section"
                ))
        
        # Validate AWS region format
        if 'aws_region' in env_config:
            region = env_config['aws_region']
            if not isinstance(region, str) or len(region.split('-')) != 3:
                self.validation_errors.append(ValidationError(
                    field=f"environments.{env_name}.aws_region",
                    message=f"Invalid AWS region format: {region}",
                    fix_suggestion="Use format like 'us-east-1' or 'us-west-2'"
                ))
        
        # Validate size threshold
        if 'size_threshold_gb' in env_config:
            threshold = env_config['size_threshold_gb']
            if not isinstance(threshold, (int, float)) or threshold <= 0:
                self.validation_errors.append(ValidationError(
                    field=f"environments.{env_name}.size_threshold_gb",
                    message=f"Invalid size threshold: {threshold}",
                    fix_suggestion="Use a positive number for size_threshold_gb"
                ))
        
        # Validate cron expression
        if 'schedule_expression' in env_config:
            schedule = env_config['schedule_expression']
            if not isinstance(schedule, str) or not schedule.startswith('cron('):
                self.validation_errors.append(ValidationError(
                    field=f"environments.{env_name}.schedule_expression",
                    message=f"Invalid cron expression: {schedule}",
                    fix_suggestion="Use AWS cron format: 'cron(0 3 ? * SUN *)'"
                ))
    
    def _validate_resources_section(self):
        """Validate resources configuration section"""
        resources = self.config['resources']
        
        # Validate Lambda configuration
        if 'lambda' in resources:
            lambda_config = resources['lambda']
            lambda_fields = {
                'orchestrator_memory': (128, 10240),
                'sync_memory': (128, 10240),
                'timeout': (1, 900)
            }
            
            for field, (min_val, max_val) in lambda_fields.items():
                if field in lambda_config:
                    value = lambda_config[field]
                    if not isinstance(value, int) or not (min_val <= value <= max_val):
                        self.validation_errors.append(ValidationError(
                            field=f"resources.lambda.{field}",
                            message=f"Invalid {field}: {value}",
                            fix_suggestion=f"Use integer between {min_val} and {max_val}"
                        ))
        
        # Validate ECS configuration
        if 'ecs' in resources:
            ecs_config = resources['ecs']
            ecs_fields = {
                'task_cpu': [256, 512, 1024, 2048, 4096],
                'task_memory': (512, 30720),
                'ephemeral_storage': (20, 200)
            }
            
            for field, valid_values in ecs_fields.items():
                if field in ecs_config:
                    value = ecs_config[field]
                    if field == 'task_cpu':
                        if value not in valid_values:
                            self.validation_errors.append(ValidationError(
                                field=f"resources.ecs.{field}",
                                message=f"Invalid {field}: {value}",
                                fix_suggestion=f"Use one of: {valid_values}"
                            ))
                    else:
                        min_val, max_val = valid_values
                        if not isinstance(value, int) or not (min_val <= value <= max_val):
                            self.validation_errors.append(ValidationError(
                                field=f"resources.ecs.{field}",
                                message=f"Invalid {field}: {value}",
                                fix_suggestion=f"Use integer between {min_val} and {max_val}"
                            ))
    
    def _validate_notifications_section(self):
        """Validate notifications configuration section"""
        notifications = self.config['notifications']
        
        # Validate Slack configuration
        if 'slack' in notifications:
            slack_config = notifications['slack']
            if 'enabled' in slack_config and slack_config['enabled']:
                if 'channel' not in slack_config:
                    self.validation_errors.append(ValidationError(
                        field="notifications.slack.channel",
                        message="Missing Slack channel when Slack is enabled",
                        fix_suggestion="Add 'channel: \"#channel-name\"' to notifications.slack"
                    ))
        
        # Validate email configuration
        if 'email' in notifications:
            email_config = notifications['email']
            if 'enabled' in email_config and email_config['enabled']:
                if 'addresses' not in email_config or not email_config['addresses']:
                    self.validation_errors.append(ValidationError(
                        field="notifications.email.addresses",
                        message="Missing email addresses when email is enabled",
                        fix_suggestion="Add 'addresses: [\"email@example.com\"]' to notifications.email"
                    ))
    
    def generate_tfvars(self, environment: str) -> str:
        """Generate terraform.tfvars content for specific environment"""
        if not self.config:
            self.load_config()
        
        if environment not in self.config['environments']:
            raise ValueError(f"Environment '{environment}' not found in configuration")
        
        env_config = self.config['environments'][environment]
        project_config = self.config['project']
        resources_config = self.config['resources']
        notifications_config = self.config['notifications']
        
        # Build terraform variables
        tfvars = {
            # Project variables
            'project_name': project_config['name'],
            'project_description': project_config.get('description', ''),
            'environment': environment,
            
            # Environment-specific variables
            'aws_region': env_config['aws_region'],
            'size_threshold_gb': env_config['size_threshold_gb'],
            'schedule_expression': env_config['schedule_expression'],
            'enable_fargate_spot': env_config['enable_fargate_spot'],
            
            # Resource variables
            'lambda_orchestrator_memory': resources_config['lambda']['orchestrator_memory'],
            'lambda_sync_memory': resources_config['lambda']['sync_memory'],
            'lambda_timeout': resources_config['lambda']['timeout'],
            'ecs_task_cpu': resources_config['ecs']['task_cpu'],
            'ecs_task_memory': resources_config['ecs']['task_memory'],
            'ecs_ephemeral_storage': resources_config['ecs']['ephemeral_storage'],
            
            # Notification variables
            'slack_enabled': notifications_config['slack']['enabled'],
            'slack_channel': notifications_config['slack'].get('channel', ''),
            'email_enabled': notifications_config['email']['enabled'],
            'email_addresses': notifications_config['email'].get('addresses', []),
            
            # Environment-specific optimizations
            'auto_shutdown': env_config.get('auto_shutdown', False),
            
            # Environment isolation variables
            'github_repository': self.config.get('github_repository', ''),
            'enable_cross_environment_isolation': True,
            'enforce_resource_tagging': True,
            'enable_multi_account_isolation': self.config.get('multi_account', {}).get('enabled', False),
        }
        
        # Add cost optimization settings if present
        if 'cost_optimization' in self.config:
            cost_config = self.config['cost_optimization']
            tfvars.update({
                'cost_threshold_usd': cost_config.get('cost_threshold_usd', 100),
                'enable_cost_alerts': cost_config.get('enable_cost_alerts', True),
            })
            
            if environment == 'dev':
                tfvars.update({
                    'dev_shutdown_schedule': cost_config.get('dev_shutdown_schedule', ''),
                    'dev_startup_schedule': cost_config.get('dev_startup_schedule', ''),
                })
        
        # Add security settings if present
        if 'security' in self.config:
            security_config = self.config['security']
            tfvars.update({
                'enable_vpc_flow_logs': security_config.get('enable_vpc_flow_logs', True),
                'enable_cloudtrail': security_config.get('enable_cloudtrail', True),
                'encryption_at_rest': security_config.get('encryption_at_rest', True),
                'encryption_in_transit': security_config.get('encryption_in_transit', True),
            })
        
        # Add multi-account settings if present
        if 'multi_account' in self.config:
            multi_account_config = self.config['multi_account']
            tfvars.update({
                'dev_aws_account_id': multi_account_config.get('dev_account_id', ''),
                'staging_aws_account_id': multi_account_config.get('staging_account_id', ''),
                'prod_aws_account_id': multi_account_config.get('prod_account_id', ''),
            })
        
        # Convert to terraform.tfvars format
        tfvars_content = []
        for key, value in tfvars.items():
            if isinstance(value, str):
                tfvars_content.append(f'{key} = "{value}"')
            elif isinstance(value, bool):
                tfvars_content.append(f'{key} = {str(value).lower()}')
            elif isinstance(value, list):
                formatted_list = json.dumps(value)
                tfvars_content.append(f'{key} = {formatted_list}')
            else:
                tfvars_content.append(f'{key} = {value}')
        
        return '\n'.join(tfvars_content)
    
    def get_environment_config(self, env: str) -> Dict:
        """Get configuration for specific environment"""
        if not self.config:
            self.load_config()
        
        if env not in self.config['environments']:
            raise ValueError(f"Environment '{env}' not found in configuration")
        
        return self.config['environments'][env]
    
    def save_tfvars_files(self) -> bool:
        """Generate and save terraform.tfvars files for all environments"""
        if not self.config:
            self.load_config()
        
        # Validate configuration first
        errors = self.validate_config()
        if errors:
            print("Configuration validation failed:")
            for error in errors:
                print(f"  - {error.field}: {error.message}")
                print(f"    Fix: {error.fix_suggestion}")
            return False
        
        # Create terraform directory if it doesn't exist
        terraform_dir = Path("terraform")
        terraform_dir.mkdir(exist_ok=True)
        
        # Generate tfvars for each environment
        for env_name in self.config['environments'].keys():
            try:
                tfvars_content = self.generate_tfvars(env_name)
                
                # Save to both root terraform directory and environment-specific directory
                # Root directory for backward compatibility
                root_tfvars_file = terraform_dir / f"{env_name}.tfvars"
                
                # Environment-specific directory
                env_dir = terraform_dir / "environments" / env_name
                env_dir.mkdir(parents=True, exist_ok=True)
                env_tfvars_file = env_dir / "terraform.tfvars"
                
                # Write to both locations
                for tfvars_file in [root_tfvars_file, env_tfvars_file]:
                    with open(tfvars_file, 'w') as f:
                        f.write(f"# Generated from config.yaml for {env_name} environment\n")
                        f.write(f"# Do not edit manually - changes will be overwritten\n\n")
                        f.write(tfvars_content)
                    
                    print(f"Generated {tfvars_file}")
                
            except Exception as e:
                print(f"Error generating tfvars for {env_name}: {e}")
                return False
        
        return True


def main():
    """Main function for command-line usage"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Process Homebrew Bottles Sync configuration")
    parser.add_argument("--config", default="config.yaml", help="Path to configuration file")
    parser.add_argument("--validate", action="store_true", help="Validate configuration only")
    parser.add_argument("--generate", action="store_true", help="Generate terraform.tfvars files")
    parser.add_argument("--environment", help="Generate tfvars for specific environment only")
    
    args = parser.parse_args()
    
    processor = ConfigProcessor(args.config)
    
    try:
        processor.load_config()
        
        if args.validate:
            errors = processor.validate_config()
            if errors:
                print("Configuration validation failed:")
                for error in errors:
                    print(f"  - {error.field}: {error.message}")
                    print(f"    Fix: {error.fix_suggestion}")
                sys.exit(1)
            else:
                print("Configuration validation passed!")
                sys.exit(0)
        
        if args.generate:
            if args.environment:
                # Generate for specific environment
                tfvars_content = processor.generate_tfvars(args.environment)
                print(f"# terraform.tfvars for {args.environment}")
                print(tfvars_content)
            else:
                # Generate all tfvars files
                success = processor.save_tfvars_files()
                sys.exit(0 if success else 1)
        
        # Default: validate and generate
        errors = processor.validate_config()
        if errors:
            print("Configuration validation failed:")
            for error in errors:
                print(f"  - {error.field}: {error.message}")
                print(f"    Fix: {error.fix_suggestion}")
            sys.exit(1)
        
        success = processor.save_tfvars_files()
        sys.exit(0 if success else 1)
        
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()