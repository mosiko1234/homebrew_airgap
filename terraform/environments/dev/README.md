# Development Environment

This directory contains the Terraform configuration for the development environment of the Homebrew Bottles Sync System.

## Overview

The development environment is optimized for cost and includes features like:
- Auto-shutdown functionality to reduce costs
- Smaller resource allocations
- Fargate Spot instances enabled
- Shorter log retention periods
- More frequent sync schedule for testing

## Configuration

The environment uses the following key settings:
- **AWS Region**: us-west-2
- **Size Threshold**: 5 GB
- **Schedule**: Every 6 hours (`cron(0 */6 * * ? *)`)
- **Auto-shutdown**: Enabled (8 PM - 8 AM weekdays)
- **Fargate Spot**: Enabled for cost savings

## Resource Optimization

Development environment uses cost-optimized settings:
- Lambda orchestrator: 512 MB memory
- Lambda sync worker: 3008 MB memory
- ECS task: 2048 CPU, 8192 MB memory
- Log retention: 7 days
- S3 lifecycle: 30 days

## Auto-shutdown Feature

The development environment includes an auto-shutdown Lambda function that:
- Shuts down ECS services at 8 PM on weekdays
- Starts up ECS services at 8 AM on weekdays
- Helps reduce costs when not actively developing

## Deployment

To deploy the development environment:

```bash
# Navigate to the dev environment directory
cd terraform/environments/dev

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
bucket         = "your-terraform-state-bucket-dev"
key            = "homebrew-bottles-sync/dev/terraform.tfstate"
region         = "us-west-2"
encrypt        = true
dynamodb_table = "terraform-state-lock-dev"
```

Then initialize with:
```bash
terraform init -backend-config=backend.hcl
```

## Monitoring

The development environment includes:
- Cost monitoring alarms
- Lambda error rate monitoring
- Auto-shutdown status tracking
- CloudWatch dashboard for key metrics

## Variables

Key variables for the development environment:
- `auto_shutdown`: Enable/disable auto-shutdown (default: true)
- `cost_threshold_usd`: Cost alert threshold (default: $100)
- `enable_cost_alerts`: Enable cost monitoring (default: true)
- `dev_shutdown_schedule`: Shutdown schedule (default: 8 PM weekdays)
- `dev_startup_schedule`: Startup schedule (default: 8 AM weekdays)

## Outputs

Important outputs from the development environment:
- `auto_shutdown_enabled`: Whether auto-shutdown is active
- `auto_shutdown_function_name`: Name of the auto-shutdown Lambda
- `cost_monitoring_enabled`: Whether cost monitoring is active
- `environment_config`: Summary of environment configuration