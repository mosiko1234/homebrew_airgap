# Production Environment

This directory contains the Terraform configuration for the production environment of the Homebrew Bottles Sync System.

## Overview

The production environment is optimized for reliability, performance, and security:
- Maximum resource allocations for performance
- Enhanced security settings
- Comprehensive monitoring and alerting
- Backup and disaster recovery
- No cost-cutting measures that impact reliability

## Configuration

The environment uses the following key settings:
- **AWS Region**: us-east-1
- **Size Threshold**: 20 GB
- **Schedule**: Weekly on Sunday at 3 AM (`cron(0 3 ? * SUN *)`)
- **Auto-shutdown**: Disabled for reliability
- **Fargate Spot**: Disabled for reliability

## Resource Configuration

Production environment uses optimized settings for performance:
- Lambda orchestrator: 512 MB memory
- Lambda sync worker: 3008 MB memory
- ECS task: 2048 CPU, 8192 MB memory
- Log retention: 30 days
- S3 lifecycle: 90 days
- Only on-demand Fargate instances (no Spot)

## Security Features

Enhanced security for production:
- VPC Flow Logs enabled
- CloudTrail logging enabled
- Encryption at rest and in transit
- Separate IAM roles with least privilege
- Enhanced monitoring for security events

## Monitoring and Alerting

Comprehensive production monitoring:
- Lambda error rate alarms (threshold: 3 errors - stricter than staging)
- Lambda duration alarms (threshold: 3 minutes - stricter than staging)
- Availability monitoring (ensures system is running)
- Cost monitoring alarms
- Enhanced CloudWatch dashboard with all metrics
- SNS notifications for all alerts

## Backup and Recovery

Production includes backup features:
- AWS Backup vault for critical resources
- Daily backup schedule at 5 AM
- 30-day cold storage transition
- 120-day backup retention
- Cross-region backup capability (optional)

## Deployment

To deploy the production environment:

```bash
# Navigate to the production environment directory
cd terraform/environments/prod

# Initialize Terraform
terraform init

# Plan the deployment (review carefully)
terraform plan -var-file="terraform.tfvars"

# Apply the configuration (requires approval)
terraform apply -var-file="terraform.tfvars"
```

## Backend Configuration

Configure the Terraform backend by creating a `backend.hcl` file:

```hcl
bucket         = "your-terraform-state-bucket-prod"
key            = "homebrew-bottles-sync/prod/terraform.tfstate"
region         = "us-east-1"
encrypt        = true
dynamodb_table = "terraform-state-lock-prod"
```

Then initialize with:
```bash
terraform init -backend-config=backend.hcl
```

## Production Monitoring Dashboard

The production dashboard includes comprehensive metrics:
- Lambda orchestrator metrics (invocations, errors, duration, throttles)
- Lambda sync worker metrics
- ECS cluster metrics (CPU, memory, running tasks)
- S3 storage metrics (bucket size, object count)
- All with appropriate time ranges and alerting

## Disaster Recovery

Production environment includes:
- Multi-AZ deployment for high availability
- Automated backups with AWS Backup
- State file stored in S3 with versioning
- DynamoDB table for state locking
- Cross-region backup capability

## Variables

Key variables for the production environment:
- `enable_backup`: Enable AWS Backup (default: true)
- `backup_kms_key_arn`: KMS key for backup encryption
- `enable_cost_alerts`: Enable cost monitoring (default: true)
- `cost_threshold_usd`: Cost alert threshold (default: $100)

## Outputs

Important outputs from the production environment:
- `dashboard_url`: URL to the comprehensive CloudWatch dashboard
- `error_alarm_name`: Name of the error rate alarm
- `duration_alarm_name`: Name of the duration alarm
- `availability_alarm_name`: Name of the availability alarm
- `backup_vault_name`: Name of the backup vault
- `backup_plan_name`: Name of the backup plan
- `environment_config`: Summary of environment configuration
- `security_config`: Security configuration details

## Maintenance

Regular maintenance tasks for production:
- Review CloudWatch alarms and metrics weekly
- Check backup status monthly
- Review and rotate secrets quarterly
- Update Terraform modules and providers regularly
- Test disaster recovery procedures quarterly