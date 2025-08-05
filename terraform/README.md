# Homebrew Bottles Sync System - Terraform Deployment

This directory contains the Terraform configuration for deploying the Homebrew Bottles Sync System infrastructure on AWS.

## Architecture Overview

The system consists of the following components:

- **Lambda Functions**: Orchestrator and sync worker for small downloads
- **ECS Fargate**: Container-based sync worker for large downloads
- **S3 Bucket**: Storage for Homebrew bottles and metadata
- **EventBridge**: Scheduled triggers for sync operations
- **VPC & Networking**: Secure network infrastructure
- **IAM Roles**: Least-privilege access control
- **CloudWatch**: Monitoring, logging, and alerting
- **Secrets Manager**: Secure storage for Slack webhook URLs

## Prerequisites

Before deploying, ensure you have:

1. **AWS CLI** installed and configured with appropriate credentials
2. **Terraform** >= 1.0 installed
3. **Python 3.11+** for building Lambda packages
4. **Docker** (optional, for building ECS container images)
5. **Appropriate AWS permissions** for creating the required resources

### Required AWS Permissions

Your AWS credentials need permissions for:
- S3 (buckets, objects, policies)
- Lambda (functions, layers, permissions)
- ECS (clusters, tasks, services)
- IAM (roles, policies, attachments)
- VPC (subnets, security groups, NAT gateways)
- EventBridge (rules, targets)
- CloudWatch (logs, metrics, alarms)
- Secrets Manager (secrets, versions)

## Quick Start

### 1. Build Lambda Packages

First, build the Lambda deployment packages:

```bash
# From the project root directory
./scripts/build-lambda-packages.sh
```

This creates ZIP files in the `build/` directory and generates hash values for Terraform.

### 2. Configure Variables

Copy the example variables file and customize it:

```bash
cd terraform
cp terraform.tfvars.example terraform.tfvars
```

Edit `terraform.tfvars` with your specific configuration. Key variables to set:

```hcl
# Basic configuration
project_name = "homebrew-bottles-sync"
environment  = "prod"
aws_region   = "us-east-1"

# Lambda package paths (from build script output)
lambda_layer_zip_path             = "../build/layer.zip"
lambda_orchestrator_zip_path      = "../build/orchestrator.zip"
lambda_sync_zip_path              = "../build/sync.zip"

# ECS container image (build and push to ECR first)
ecs_container_image = "123456789012.dkr.ecr.us-east-1.amazonaws.com/homebrew-bottles-sync:latest"

# Slack webhook URL (optional, can be set later)
slack_webhook_url = "https://hooks.slack.com/services/YOUR/SLACK/WEBHOOK"
```

### 3. Deploy Infrastructure

Deploy using the deployment script:

```bash
# Deploy to production
./scripts/deploy-prod.sh

# Or deploy to development
./scripts/deploy-dev.sh

# Or deploy to staging
./scripts/deploy-staging.sh
```

### 4. Verify Deployment

After deployment, verify the system:

1. Check the CloudWatch dashboard (URL in Terraform outputs)
2. Verify the EventBridge rule is enabled
3. Test the Lambda functions manually if needed
4. Check S3 bucket creation and permissions

## Environment-Specific Deployments

### Development Environment

For development deployments, create a `dev.tfvars` file:

```hcl
# Development-specific overrides
environment = "dev"
aws_region  = "us-west-2"

# Smaller resources for cost savings
ecs_task_cpu                    = 1024
ecs_task_memory                 = 4096
ecs_ephemeral_storage_size_gb   = 50
lambda_sync_memory_size         = 1024
size_threshold_gb               = 5

# More frequent schedule for testing
schedule_expression = "cron(0 */6 * * ? *)"  # Every 6 hours

# Shorter log retention
log_retention_days = 7
```

Deploy with:
```bash
./scripts/deploy.sh -e dev -r us-west-2
```

### Staging Environment

For staging deployments, create a `staging.tfvars` file:

```hcl
# Staging-specific overrides
environment = "staging"

# Production-like but with cost optimizations
ecs_enable_fargate_spot = true
ecs_fargate_spot_weight = 3

# Different schedule to avoid conflicts
schedule_expression = "cron(0 3 ? * SAT *)"  # Saturday at 03:00 UTC

# Enable email notifications
enable_sns_notifications = true
notification_email_addresses = ["staging-alerts@company.com"]
```

Deploy with:
```bash
./scripts/deploy.sh -e staging
```

## Deployment Options

The deployment script supports various options:

```bash
# Plan only (don't apply)
./scripts/deploy.sh -e prod -p

# Auto-approve (skip confirmation)
./scripts/deploy.sh -e prod -a

# Destroy infrastructure
./scripts/deploy.sh -e prod -d

# Initialize Terraform only
./scripts/deploy.sh -i

# Validate configuration only
./scripts/deploy.sh -v
```

## Module Structure

The Terraform configuration is organized into modules:

- **`modules/network/`**: VPC, subnets, security groups
- **`modules/s3/`**: S3 bucket and policies
- **`modules/iam/`**: IAM roles and policies
- **`modules/lambda/`**: Lambda functions and layers
- **`modules/ecs/`**: ECS cluster and task definitions
- **`modules/eventbridge/`**: Scheduled event rules
- **`modules/notifications/`**: Slack and SNS notifications
- **`modules/monitoring/`**: CloudWatch dashboards and alarms

## State Management

Terraform state is stored in S3 with the following structure:
- **Bucket**: `terraform-state-{account-id}-{region}`
- **Key**: `homebrew-bottles-sync/{environment}/terraform.tfstate`
- **Region**: Same as deployment region

The state bucket is created automatically during the first deployment.

## Security Considerations

### IAM Permissions

All IAM roles follow the principle of least privilege:
- Lambda functions have minimal S3 and Secrets Manager access
- ECS tasks have scoped permissions for their specific operations
- Cross-service access is explicitly defined and limited

### Network Security

- ECS tasks run in private subnets with NAT Gateway for outbound access
- Security groups restrict traffic to necessary ports only
- VPC endpoints can be added for enhanced security (optional)

### Secrets Management

- Slack webhook URLs are stored in AWS Secrets Manager
- Secrets are encrypted with AWS KMS
- Optional cross-region backup for disaster recovery

## Monitoring and Alerting

The deployment includes comprehensive monitoring:

### CloudWatch Dashboards
- System overview with key metrics
- Lambda function performance
- ECS task monitoring
- Error rates and success metrics

### CloudWatch Alarms
- High error rates
- Function duration thresholds
- ECS task failures
- Sync progress monitoring

### Notifications
- Slack notifications for sync status
- SNS topics for email alerts (optional)
- CloudWatch alarm notifications

## Troubleshooting

### Common Issues

1. **Lambda package build failures**
   - Ensure Python 3.11+ is installed
   - Check that all dependencies in `requirements.txt` are available
   - Verify the `shared/` directory exists

2. **ECS container image not found**
   - Build and push the container image to ECR first
   - Update `ecs_container_image` variable with correct ECR URI
   - Ensure ECS task execution role has ECR permissions

3. **Terraform state conflicts**
   - Ensure no other deployments are running simultaneously
   - Check S3 state bucket permissions
   - Use different state keys for different environments

4. **Permission denied errors**
   - Verify AWS credentials have sufficient permissions
   - Check IAM policies for required actions
   - Ensure cross-account access is properly configured

### Debugging

Enable debug logging:
```bash
export TF_LOG=DEBUG
./scripts/deploy.sh -e dev
```

Check CloudWatch logs:
- Lambda function logs: `/aws/lambda/{function-name}`
- ECS task logs: `/aws/ecs/{cluster-name}`
- EventBridge logs: `/aws/events/rule/{rule-name}`

## Cleanup

To destroy the infrastructure:

```bash
# Destroy production environment
./scripts/deploy.sh -e prod -d

# Destroy with auto-approve
./scripts/deploy.sh -e prod -d -a
```

**Warning**: This will permanently delete all resources including S3 buckets and their contents.

## Cost Optimization

### Development Environment
- Use smaller ECS task sizes
- Enable Fargate Spot instances
- Reduce log retention periods
- Use lower Lambda memory allocations

### Production Environment
- Enable S3 lifecycle policies
- Use Fargate Spot for cost savings
- Monitor CloudWatch costs
- Set up billing alerts

## Support

For issues and questions:
1. Check the troubleshooting section above
2. Review CloudWatch logs for error details
3. Consult the main project README for application-specific issues
4. Check AWS service status for regional issues

## Contributing

When modifying the Terraform configuration:
1. Test changes in development environment first
2. Update variable descriptions and validation rules
3. Update this README with any new requirements
4. Follow Terraform best practices for module design