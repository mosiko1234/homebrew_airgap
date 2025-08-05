# Homebrew Bottles Sync System - Deployment Guide

This guide provides step-by-step instructions for deploying the Homebrew Bottles Sync System across different environments.

## Prerequisites

Before deploying, ensure you have the following installed and configured:

### Required Tools
- **AWS CLI** v2.x with configured credentials
- **Terraform** >= 1.0
- **Python** 3.11 or higher
- **Docker** (for building ECS container images)
- **Git** (for cloning and version control)

### AWS Account Setup
1. **AWS Account** with appropriate permissions
2. **IAM User/Role** with the following managed policies:
   - `PowerUserAccess` (or custom policy with required permissions)
   - `IAMFullAccess` (for creating service roles)
3. **AWS CLI configured** with credentials:
   ```bash
   aws configure
   # or
   aws configure sso
   ```

### Verify Prerequisites
```bash
# Check tool versions
aws --version
terraform --version
python --version
docker --version

# Verify AWS access
aws sts get-caller-identity
```

## Quick Start (Production Deployment)

### 1. Clone and Setup
```bash
git clone <repository-url>
cd homebrew-bottles-sync
```

### 2. Build Lambda Packages
```bash
./scripts/build-lambda-packages.sh
```

### 3. Build and Push ECS Container (Optional)
If using ECS for large downloads:
```bash
# Build container image
docker build -t homebrew-bottles-sync:latest ./ecs/sync/

# Tag and push to ECR (replace with your ECR URI)
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin 123456789012.dkr.ecr.us-east-1.amazonaws.com
docker tag homebrew-bottles-sync:latest 123456789012.dkr.ecr.us-east-1.amazonaws.com/homebrew-bottles-sync:latest
docker push 123456789012.dkr.ecr.us-east-1.amazonaws.com/homebrew-bottles-sync:latest
```

### 4. Configure Variables
```bash
cd terraform
cp terraform.tfvars.example terraform.tfvars
```

Edit `terraform.tfvars` with your configuration:
```hcl
# Basic configuration
project_name = "homebrew-bottles-sync"
environment  = "prod"
aws_region   = "us-east-1"

# Lambda packages (from build script)
lambda_layer_zip_path             = "../build/layer.zip"
lambda_orchestrator_zip_path      = "../build/orchestrator.zip"
lambda_sync_zip_path              = "../build/sync.zip"

# ECS container image
ecs_container_image = "123456789012.dkr.ecr.us-east-1.amazonaws.com/homebrew-bottles-sync:latest"

# Slack webhook (optional)
slack_webhook_url = "https://hooks.slack.com/services/YOUR/SLACK/WEBHOOK"
```

### 5. Deploy Infrastructure
```bash
# Validate configuration
./scripts/validate-terraform.sh

# Deploy to production
./scripts/deploy-prod.sh
```

### 6. Verify Deployment
After deployment:
1. Check Terraform outputs for resource information
2. Verify EventBridge rule is enabled
3. Check CloudWatch dashboard (URL in outputs)
4. Test manual Lambda invocation if needed

## Environment-Specific Deployments

### Development Environment

Development environment uses cost-optimized settings and more frequent sync schedules for testing.

```bash
# Build packages
./scripts/build-lambda-packages.sh

# Deploy to development
./scripts/deploy-dev.sh

# Or with custom options
./scripts/deploy.sh -e dev -r us-west-2 -a
```

**Development Features:**
- Smaller ECS tasks (1 vCPU, 4GB RAM)
- Fargate Spot instances for cost savings
- 6-hour sync schedule for testing
- Shorter log retention (7 days)
- Debug logging enabled
- Only 2 macOS platforms (arm64_sonoma, arm64_ventura)

### Staging Environment

Staging environment mirrors production but with cost optimizations and different schedule.

```bash
# Build packages
./scripts/build-lambda-packages.sh

# Deploy to staging
./scripts/deploy-staging.sh

# Or with custom options
./scripts/deploy.sh -e staging -a
```

**Staging Features:**
- Production-like resources with Fargate Spot
- Saturday sync schedule (vs Sunday for prod)
- Email notifications enabled
- Shorter retention periods
- Full 3-platform support

### Production Environment

Production environment with full resources and monitoring.

```bash
# Build packages
./scripts/build-lambda-packages.sh

# Deploy to production
./scripts/deploy-prod.sh

# Or with custom options
./scripts/deploy.sh -e prod -r us-east-1
```

**Production Features:**
- Full ECS resources (2 vCPU, 8GB RAM)
- Sunday 03:00 UTC sync schedule
- Full monitoring and alerting
- 90-day S3 lifecycle policies
- All 3 macOS platforms

## Advanced Deployment Options

### Custom Configuration

Create environment-specific tfvars files:

```bash
# Custom production config
cp terraform/terraform.tfvars.example terraform/prod-custom.tfvars
# Edit prod-custom.tfvars with your settings

# Deploy with custom config
./scripts/deploy.sh -e prod --var-file=prod-custom.tfvars
```

### Multi-Region Deployment

Deploy to multiple regions:

```bash
# Deploy to us-east-1
./scripts/deploy.sh -e prod -r us-east-1

# Deploy to us-west-2
./scripts/deploy.sh -e prod -r us-west-2
```

### Disaster Recovery Setup

Enable cross-region backup for secrets:

```hcl
# In terraform.tfvars
enable_cross_region_backup = true
backup_region              = "us-west-2"
```

## Deployment Scripts Reference

### Main Deployment Script (`./scripts/deploy.sh`)

```bash
Usage: ./scripts/deploy.sh [OPTIONS]

OPTIONS:
    -e, --environment ENV    Environment (dev, staging, prod) [default: prod]
    -r, --region REGION      AWS region [default: us-east-1]
    -a, --auto-approve       Auto-approve Terraform apply
    -d, --destroy           Destroy infrastructure
    -p, --plan-only         Only run terraform plan
    -i, --init-only         Only run terraform init
    -v, --validate-only     Only run terraform validate
    -h, --help              Show help message
```

### Environment-Specific Scripts

- `./scripts/deploy-dev.sh` - Deploy to development (us-west-2)
- `./scripts/deploy-staging.sh` - Deploy to staging (us-east-1)
- `./scripts/deploy-prod.sh` - Deploy to production (us-east-1)

### Utility Scripts

- `./scripts/build-lambda-packages.sh` - Build Lambda deployment packages
- `./scripts/validate-terraform.sh` - Validate Terraform configuration

## Monitoring and Maintenance

### Post-Deployment Verification

1. **Check EventBridge Rule**:
   ```bash
   aws events describe-rule --name homebrew-bottles-sync-prod-schedule
   ```

2. **Verify S3 Bucket**:
   ```bash
   aws s3 ls s3://homebrew-bottles-sync-prod-{account-id}/
   ```

3. **Test Lambda Function**:
   ```bash
   aws lambda invoke --function-name homebrew-bottles-sync-prod-orchestrator response.json
   ```

4. **Check ECS Cluster**:
   ```bash
   aws ecs describe-clusters --clusters homebrew-bottles-sync-prod-cluster
   ```

### CloudWatch Monitoring

Access monitoring dashboards:
1. Go to CloudWatch Console
2. Navigate to Dashboards
3. Open "homebrew-bottles-sync-{environment}-dashboard"

Key metrics to monitor:
- Lambda function duration and errors
- ECS task success/failure rates
- S3 upload success rates
- Sync completion times

### Log Analysis

Check logs in CloudWatch:
- **Orchestrator**: `/aws/lambda/homebrew-bottles-sync-{env}-orchestrator`
- **Sync Worker**: `/aws/lambda/homebrew-bottles-sync-{env}-sync-worker`
- **ECS Tasks**: `/aws/ecs/homebrew-bottles-sync-{env}-cluster`

## Troubleshooting

### Common Issues

1. **Lambda Package Build Failures**
   ```bash
   # Check Python version
   python --version
   
   # Reinstall dependencies
   pip install -r requirements.txt
   
   # Rebuild packages
   ./scripts/build-lambda-packages.sh
   ```

2. **ECS Container Image Not Found**
   ```bash
   # Check ECR repository exists
   aws ecr describe-repositories --repository-names homebrew-bottles-sync
   
   # Rebuild and push image
   docker build -t homebrew-bottles-sync:latest ./ecs/sync/
   docker tag homebrew-bottles-sync:latest {ecr-uri}:latest
   docker push {ecr-uri}:latest
   ```

3. **Terraform State Lock**
   ```bash
   # Check for existing locks
   aws dynamodb scan --table-name terraform-state-lock
   
   # Force unlock if needed (use carefully)
   terraform force-unlock {lock-id}
   ```

4. **Permission Denied Errors**
   ```bash
   # Check AWS credentials
   aws sts get-caller-identity
   
   # Verify IAM permissions
   aws iam simulate-principal-policy --policy-source-arn {user-arn} --action-names s3:CreateBucket
   ```

### Debug Mode

Enable debug logging:
```bash
export TF_LOG=DEBUG
export AWS_SDK_LOAD_CONFIG=1
./scripts/deploy.sh -e dev
```

### Recovery Procedures

1. **Partial Deployment Failure**:
   ```bash
   # Check Terraform state
   terraform show
   
   # Retry deployment
   ./scripts/deploy.sh -e {env} -a
   ```

2. **Complete Infrastructure Recovery**:
   ```bash
   # Import existing resources if needed
   terraform import aws_s3_bucket.main {bucket-name}
   
   # Re-apply configuration
   ./scripts/deploy.sh -e {env}
   ```

## Cleanup and Destruction

### Destroy Environment

```bash
# Destroy development environment
./scripts/deploy.sh -e dev -d

# Destroy with auto-approve
./scripts/deploy.sh -e prod -d -a
```

### Manual Cleanup

If automated destruction fails:

1. **Empty S3 Buckets**:
   ```bash
   aws s3 rm s3://homebrew-bottles-sync-{env}-{account-id} --recursive
   ```

2. **Delete CloudWatch Log Groups**:
   ```bash
   aws logs delete-log-group --log-group-name /aws/lambda/homebrew-bottles-sync-{env}-orchestrator
   ```

3. **Remove Terraform State**:
   ```bash
   # Only if completely starting over
   rm -rf .terraform/
   rm terraform.tfstate*
   ```

## Security Best Practices

### Secrets Management
- Store Slack webhook URLs in AWS Secrets Manager
- Use IAM roles instead of access keys where possible
- Enable CloudTrail for audit logging
- Regularly rotate secrets

### Network Security
- ECS tasks run in private subnets
- Use security groups to restrict access
- Consider VPC endpoints for AWS services
- Enable VPC Flow Logs for monitoring

### Access Control
- Follow principle of least privilege
- Use separate AWS accounts for different environments
- Implement resource tagging for cost allocation
- Regular IAM access reviews

## Cost Optimization

### Development Environment
- Use Fargate Spot instances
- Shorter log retention periods
- Smaller ECS task sizes
- Disable Container Insights

### Production Environment
- Enable S3 lifecycle policies
- Use CloudWatch cost monitoring
- Set up billing alerts
- Regular cost reviews

### Monitoring Costs
```bash
# Check current month costs
aws ce get-cost-and-usage --time-period Start=2025-07-01,End=2025-07-31 --granularity MONTHLY --metrics BlendedCost

# Set up billing alerts
aws budgets create-budget --account-id {account-id} --budget file://budget.json
```

## Support and Maintenance

### Regular Maintenance Tasks
1. **Monthly**: Review CloudWatch costs and usage
2. **Quarterly**: Update Lambda runtime versions
3. **Bi-annually**: Review and update IAM policies
4. **Annually**: Disaster recovery testing

### Getting Help
1. Check this deployment guide
2. Review CloudWatch logs for errors
3. Consult AWS documentation for service-specific issues
4. Check Terraform documentation for configuration issues

### Contributing
When making changes:
1. Test in development environment first
2. Update documentation
3. Follow infrastructure as code best practices
4. Use proper Git workflow with pull requests