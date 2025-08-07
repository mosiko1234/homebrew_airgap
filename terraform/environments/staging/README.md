# Staging Environment

This directory contains the Terraform configuration for the staging environment of the Homebrew Bottles Sync System.

## Overview

The staging environment is designed to mirror production settings for testing and validation:
- Production-like resource allocations
- Enhanced monitoring and alerting
- Balanced cost optimization with reliability
- Weekly sync schedule for testing

## Configuration

The environment uses the following key settings:
- **AWS Region**: us-east-1
- **Size Threshold**: 15 GB
- **Schedule**: Weekly on Saturday at 3 AM (`cron(0 3 ? * SAT *)`)
- **Auto-shutdown**: Disabled for availability
- **Fargate Spot**: Enabled for cost optimization

## Resource Configuration

Staging environment uses production-like settings:
- Lambda orchestrator: 512 MB memory
- Lambda sync worker: 3008 MB memory
- ECS task: 2048 CPU, 8192 MB memory
- Log retention: 14 days
- S3 lifecycle: 60 days

## Monitoring and Alerting

The staging environment includes comprehensive monitoring:
- Lambda error rate alarms (threshold: 5 errors)
- Lambda duration alarms (threshold: 4 minutes)
- Cost monitoring alarms
- Custom CloudWatch dashboard
- SNS notifications for alerts

## Deployment

To deploy the staging environment:

```bash
# Navigate to the staging environment directory
cd terraform/environments/staging

# Initialize Terraform
terraform init

# Plan the deployment
terraform plan -var-file="terraform.tfvars"

# Apply the configuration
terraform apply -var-file="terraform.tfvars"
```

## Backend Configuration

Configure the Terraform backend by creating a `backend.hcl` file:

```hcl
bucket         = "your-terraform-state-bucket-staging"
key            = "homebrew-bottles-sync/staging/terraform.tfstate"
region         = "us-east-1"
encrypt        = true
dynamodb_table = "terraform-state-lock-staging"
```

Then initialize with:
```bash
terraform init -backend-config=backend.hcl
```

## Testing and Validation

The staging environment is used for:
- Integration testing of new features
- Performance testing under production-like conditions
- Validation of deployment procedures
- Testing of monitoring and alerting systems

## Monitoring Dashboard

The staging environment includes a custom CloudWatch dashboard with:
- Lambda function metrics (invocations, errors, duration)
- ECS cluster metrics (CPU, memory utilization)
- Custom alarms and notifications

## Variables

Key variables for the staging environment:
- `enable_cost_alerts`: Enable cost monitoring (default: true)
- `cost_threshold_usd`: Cost alert threshold (default: $100)
- `enable_fargate_spot`: Use Spot instances (default: true)

## Outputs

Important outputs from the staging environment:
- `dashboard_url`: URL to the CloudWatch dashboard
- `error_alarm_name`: Name of the error rate alarm
- `duration_alarm_name`: Name of the duration alarm
- `environment_config`: Summary of environment configuration
- `monitoring_config`: Monitoring configuration details