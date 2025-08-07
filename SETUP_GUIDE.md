# Homebrew Bottles Sync System - Setup and Installation Guide

This comprehensive guide provides step-by-step instructions for setting up and installing the Homebrew Bottles Sync System from scratch. Follow this guide to get your system up and running quickly with minimal configuration.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Quick Setup (5 Minutes)](#quick-setup-5-minutes)
3. [Detailed Setup Process](#detailed-setup-process)
4. [Configuration Options](#configuration-options)
5. [Verification and Testing](#verification-and-testing)
6. [Troubleshooting Setup Issues](#troubleshooting-setup-issues)
7. [Next Steps](#next-steps)

## Prerequisites

### Required Tools and Accounts

Before starting, ensure you have the following:

#### 1. AWS Account and CLI
- **AWS Account** with administrative access
- **AWS CLI v2.x** installed and configured
- **Appropriate IAM permissions** (see [IAM Requirements](#iam-requirements))

```bash
# Install AWS CLI (macOS)
brew install awscli

# Install AWS CLI (Linux)
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
unzip awscliv2.zip
sudo ./aws/install

# Configure AWS CLI
aws configure
# or for SSO
aws configure sso
```

#### 2. Terraform
- **Terraform >= 1.0** for infrastructure management

```bash
# Install Terraform (macOS)
brew install terraform

# Install Terraform (Linux)
wget https://releases.hashicorp.com/terraform/1.6.0/terraform_1.6.0_linux_amd64.zip
unzip terraform_1.6.0_linux_amd64.zip
sudo mv terraform /usr/local/bin/
```

#### 3. Python Environment
- **Python 3.11+** for scripts and Lambda functions
- **pip** for package management

```bash
# Check Python version
python3 --version

# Install pip if needed
curl https://bootstrap.pypa.io/get-pip.py -o get-pip.py
python3 get-pip.py
```

#### 4. Additional Tools
```bash
# Install required utilities
# macOS
brew install jq git docker

# Linux (Ubuntu/Debian)
sudo apt update
sudo apt install jq git docker.io

# Linux (RHEL/CentOS)
sudo yum install jq git docker
```

### IAM Requirements

Your AWS user/role needs the following permissions:

#### Managed Policies (Recommended)
- `PowerUserAccess` - For resource creation and management
- `IAMFullAccess` - For creating service roles

#### Custom Policy (Minimal Permissions)
If you prefer minimal permissions, create a custom policy with these services:
- S3 (full access)
- Lambda (full access)
- ECS (full access)
- EventBridge (full access)
- CloudWatch (full access)
- VPC (full access)
- IAM (role creation and policy attachment)
- Secrets Manager (full access)

### Verify Prerequisites

Run this verification script to ensure all prerequisites are met:

```bash
# Create verification script
cat > verify-prerequisites.sh << 'EOF'
#!/bin/bash
set -e

echo "🔍 Verifying prerequisites..."

# Check AWS CLI
if ! command -v aws &> /dev/null; then
    echo "❌ AWS CLI not found. Please install AWS CLI v2.x"
    exit 1
fi

# Check AWS credentials
if ! aws sts get-caller-identity &> /dev/null; then
    echo "❌ AWS credentials not configured. Run 'aws configure'"
    exit 1
fi

# Check Terraform
if ! command -v terraform &> /dev/null; then
    echo "❌ Terraform not found. Please install Terraform >= 1.0"
    exit 1
fi

# Check Python
if ! python3 --version | grep -E "3\.(11|12)" &> /dev/null; then
    echo "❌ Python 3.11+ required. Current version: $(python3 --version)"
    exit 1
fi

# Check required tools
for tool in jq git docker; do
    if ! command -v $tool &> /dev/null; then
        echo "❌ $tool not found. Please install $tool"
        exit 1
    fi
done

echo "✅ All prerequisites verified!"
echo "AWS Account: $(aws sts get-caller-identity --query Account --output text)"
echo "AWS Region: $(aws configure get region)"
echo "Terraform: $(terraform version | head -n1)"
echo "Python: $(python3 --version)"
EOF

chmod +x verify-prerequisites.sh
./verify-prerequisites.sh
```

## Quick Setup (5 Minutes)

For users who want to get started immediately with default settings:

### 1. Clone and Initialize

```bash
# Clone the repository
git clone <repository-url>
cd homebrew-bottles-sync

# Run the quick setup script
./scripts/setup-config.sh --quick-start
```

### 2. Configure Basic Settings

The quick setup will prompt for essential settings:

```bash
# You'll be prompted for:
# - AWS Region (default: us-east-1)
# - S3 Bucket Name (auto-generated if not provided)
# - Slack Webhook URL (optional)
# - Environment (default: prod)
```

### 3. Deploy Infrastructure

```bash
# Deploy with auto-approval
./scripts/deploy-prod.sh --auto-approve
```

### 4. Verify Deployment

```bash
# Check deployment status
./scripts/deployment-status.sh

# View CloudWatch dashboard (URL will be displayed)
```

**That's it!** Your system is now deployed and will automatically sync Homebrew bottles every Sunday at 3 AM UTC.

## Detailed Setup Process

For users who want full control over the configuration:

### Step 1: Repository Setup

```bash
# Clone the repository
git clone <repository-url>
cd homebrew-bottles-sync

# Create your configuration branch (optional)
git checkout -b setup/$(whoami)-config
```

### Step 2: Configuration File Setup

#### Create Main Configuration

```bash
# Copy the example configuration
cp config.yaml.example config.yaml
```

#### Edit Configuration File

Open `config.yaml` and customize the settings:

```yaml
# Project settings
project:
  name: "homebrew-bottles-sync"
  description: "Automated Homebrew bottles sync system"
  version: "1.0.0"

# Environment configurations
environments:
  dev:
    aws_region: "us-west-2"
    size_threshold_gb: 5
    schedule_expression: "cron(0 */6 * * ? *)"  # Every 6 hours
    enable_fargate_spot: true
    auto_shutdown: true
    
  staging:
    aws_region: "us-east-1"
    size_threshold_gb: 15
    schedule_expression: "cron(0 3 ? * SAT *)"  # Saturday 3 AM
    enable_fargate_spot: true
    
  prod:
    aws_region: "us-east-1"
    size_threshold_gb: 20
    schedule_expression: "cron(0 3 ? * SUN *)"  # Sunday 3 AM
    enable_fargate_spot: false

# Resource configurations
resources:
  lambda:
    orchestrator_memory: 512
    sync_memory: 3008
    timeout: 900
    
  ecs:
    task_cpu: 2048
    task_memory: 8192
    ephemeral_storage: 100

# Notification settings
notifications:
  slack:
    enabled: true
    channel: "#platform-updates"
  email:
    enabled: true
    addresses: ["devops@company.com"]

# Cost optimization
cost_optimization:
  enable_lifecycle_policies: true
  dev_auto_shutdown: true
  monitoring_retention_days: 14
```

#### Validate Configuration

```bash
# Validate the configuration file
python3 scripts/config_processor.py --validate

# Generate environment-specific tfvars files
python3 scripts/config_processor.py --generate
```

### Step 3: AWS Infrastructure Preparation

#### Set Up S3 Backend (Optional but Recommended)

```bash
# Create S3 bucket for Terraform state
aws s3 mb s3://terraform-state-homebrew-sync-$(aws sts get-caller-identity --query Account --output text)

# Create DynamoDB table for state locking
aws dynamodb create-table \
  --table-name terraform-state-lock-homebrew-sync \
  --attribute-definitions AttributeName=LockID,AttributeType=S \
  --key-schema AttributeName=LockID,KeyType=HASH \
  --provisioned-throughput ReadCapacityUnits=5,WriteCapacityUnits=5
```

#### Configure Backend (if using remote state)

```bash
# Create backend configuration
cat > terraform/backend.hcl << EOF
bucket         = "terraform-state-homebrew-sync-$(aws sts get-caller-identity --query Account --output text)"
key            = "homebrew-bottles-sync/terraform.tfstate"
region         = "us-east-1"
dynamodb_table = "terraform-state-lock-homebrew-sync"
encrypt        = true
EOF
```

### Step 4: Build and Package Components

#### Build Lambda Packages

```bash
# Build all Lambda packages
./scripts/build-lambda-packages.sh

# Verify packages were created
ls -la build/
```

#### Build ECS Container (if using ECS for large downloads)

```bash
# Build container image
docker build -t homebrew-bottles-sync:latest ./ecs/sync/

# Create ECR repository
aws ecr create-repository --repository-name homebrew-bottles-sync

# Get ECR login token and push image
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin $(aws sts get-caller-identity --query Account --output text).dkr.ecr.us-east-1.amazonaws.com

# Tag and push image
docker tag homebrew-bottles-sync:latest $(aws sts get-caller-identity --query Account --output text).dkr.ecr.us-east-1.amazonaws.com/homebrew-bottles-sync:latest
docker push $(aws sts get-caller-identity --query Account --output text).dkr.ecr.us-east-1.amazonaws.com/homebrew-bottles-sync:latest
```

### Step 5: Environment-Specific Deployment

#### Deploy Development Environment

```bash
# Deploy to development
./scripts/deploy-dev.sh

# Monitor deployment
./scripts/deployment-status.sh --environment dev
```

#### Deploy Staging Environment

```bash
# Deploy to staging
./scripts/deploy-staging.sh

# Run integration tests
python3 -m pytest tests/integration/ -v
```

#### Deploy Production Environment

```bash
# Plan production deployment
./scripts/deploy-environment.sh --environment prod --action plan

# Review the plan, then deploy
./scripts/deploy-prod.sh
```

### Step 6: Configure Secrets

#### Set Up Slack Notifications (Optional)

```bash
# Create Slack webhook secret
aws secretsmanager create-secret \
  --name "homebrew-sync/slack-webhook" \
  --description "Slack webhook URL for notifications" \
  --secret-string "https://hooks.slack.com/services/YOUR/WEBHOOK/URL"
```

#### Configure Additional Secrets

```bash
# Set up notification email (if using SNS)
aws secretsmanager create-secret \
  --name "homebrew-sync/notification-email" \
  --description "Email address for critical notifications" \
  --secret-string "admin@yourcompany.com"
```

## Configuration Options

### Environment-Specific Settings

#### Development Environment Optimizations
```yaml
environments:
  dev:
    # Cost optimizations
    enable_fargate_spot: true
    auto_shutdown: true
    
    # Smaller resources
    size_threshold_gb: 5
    
    # More frequent sync for testing
    schedule_expression: "cron(0 */6 * * ? *)"
    
    # Shorter retention
    log_retention_days: 7
```

#### Production Environment Settings
```yaml
environments:
  prod:
    # Reliability over cost
    enable_fargate_spot: false
    
    # Full resources
    size_threshold_gb: 20
    
    # Weekly sync
    schedule_expression: "cron(0 3 ? * SUN *)"
    
    # Extended retention
    log_retention_days: 30
```

### Resource Configuration Options

#### Lambda Function Settings
```yaml
resources:
  lambda:
    # Orchestrator function
    orchestrator_memory: 512      # MB (128-10240)
    orchestrator_timeout: 300     # seconds (1-900)
    
    # Sync worker function
    sync_memory: 3008            # MB (128-10240)
    sync_timeout: 900            # seconds (1-900)
    
    # Runtime settings
    runtime: "python3.11"
    architecture: "x86_64"       # or "arm64"
```

#### ECS Task Settings
```yaml
resources:
  ecs:
    # Task resources
    task_cpu: 2048               # CPU units (256-16384)
    task_memory: 8192            # MB (512-122880)
    ephemeral_storage: 100       # GB (21-200)
    
    # Networking
    assign_public_ip: false
    enable_execute_command: true  # For debugging
```

### Notification Configuration

#### Slack Integration
```yaml
notifications:
  slack:
    enabled: true
    channel: "#platform-updates"
    webhook_secret_name: "homebrew-sync/slack-webhook"
    
    # Message customization
    include_details: true
    mention_on_failure: true
    user_mentions: ["@devops-team"]
```

#### Email Notifications
```yaml
notifications:
  email:
    enabled: true
    addresses: 
      - "devops@company.com"
      - "platform-team@company.com"
    
    # SNS topic configuration
    topic_name: "homebrew-sync-notifications"
    delivery_policy: "immediate"
```

### Advanced Configuration Options

#### External Hash File Integration
```yaml
external_hash_sources:
  # S3 source
  s3_source:
    enabled: true
    bucket: "existing-bottles-bucket"
    key: "bottles_hash.json"
    
  # HTTPS source
  https_source:
    enabled: false
    url: "https://example.com/bottles_hash.json"
    
  # Validation settings
  validation:
    require_signature: false
    max_age_hours: 24
```

#### Cost Optimization Settings
```yaml
cost_optimization:
  # S3 lifecycle policies
  enable_lifecycle_policies: true
  transition_to_ia_days: 30
  transition_to_glacier_days: 90
  expiration_days: 365
  
  # Development environment auto-shutdown
  dev_auto_shutdown: true
  shutdown_schedule: "cron(0 18 ? * MON-FRI *)"  # 6 PM weekdays
  startup_schedule: "cron(0 8 ? * MON-FRI *)"    # 8 AM weekdays
  
  # Monitoring and alerting
  cost_threshold_usd: 100
  cost_alert_email: "finance@company.com"
```

## Verification and Testing

### Post-Deployment Verification

#### 1. Infrastructure Verification

```bash
# Check all AWS resources were created
./scripts/validate-deployment.sh

# Verify Terraform state
cd terraform
terraform show | grep -E "(aws_lambda_function|aws_ecs_cluster|aws_s3_bucket)"
```

#### 2. Functional Testing

```bash
# Test Lambda orchestrator function
aws lambda invoke \
  --function-name homebrew-sync-orchestrator \
  --payload '{"source": "manual", "test": true}' \
  response.json

cat response.json
```

#### 3. Integration Testing

```bash
# Run comprehensive integration tests
python3 -m pytest tests/integration/ -v --tb=short

# Run specific test suites
python3 -m pytest tests/integration/test_aws_services.py -v
python3 -m pytest tests/integration/test_end_to_end_workflows.py -v
```

#### 4. Security Testing

```bash
# Run security tests
python3 -m pytest tests/security/ -v

# Check IAM policies
./scripts/validate-iam-policies.sh

# Scan for secrets in code
./scripts/scan-secrets.sh
```

### Manual Testing Procedures

#### Test Slack Notifications

```bash
# Test notification system
python3 scripts/notify_deployment.py \
  --type "test" \
  --environment "dev" \
  --message "Setup verification test"
```

#### Test S3 Access

```bash
# Test S3 bucket access
aws s3 ls s3://homebrew-bottles-sync-$(aws sts get-caller-identity --query Account --output text)/

# Test file upload
echo "test" > test-file.txt
aws s3 cp test-file.txt s3://homebrew-bottles-sync-$(aws sts get-caller-identity --query Account --output text)/test/
aws s3 rm s3://homebrew-bottles-sync-$(aws sts get-caller-identity --query Account --output text)/test/test-file.txt
rm test-file.txt
```

#### Test ECS Task Execution

```bash
# Run a test ECS task
aws ecs run-task \
  --cluster homebrew-sync \
  --task-definition homebrew-bottles-sync \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[subnet-xxx],securityGroups=[sg-xxx],assignPublicIp=DISABLED}"
```

## Troubleshooting Setup Issues

### Common Setup Problems

#### 1. AWS Credentials Issues

**Problem**: `Unable to locate credentials`
```bash
# Solution: Configure AWS credentials
aws configure
# or
export AWS_PROFILE=your-profile
```

**Problem**: `Access Denied` errors
```bash
# Solution: Check IAM permissions
aws iam get-user
aws iam list-attached-user-policies --user-name $(aws sts get-caller-identity --query Arn --output text | cut -d'/' -f2)
```

#### 2. Terraform Issues

**Problem**: `Backend configuration changed`
```bash
# Solution: Reinitialize Terraform
cd terraform
terraform init -reconfigure
```

**Problem**: `Resource already exists`
```bash
# Solution: Import existing resource or use different names
terraform import aws_s3_bucket.main existing-bucket-name
```

#### 3. Configuration Validation Errors

**Problem**: `Invalid configuration format`
```bash
# Solution: Validate YAML syntax
python3 -c "import yaml; yaml.safe_load(open('config.yaml'))"

# Fix common issues
python3 scripts/config_processor.py --validate --fix
```

#### 4. Build and Package Issues

**Problem**: Lambda package build fails
```bash
# Solution: Check Python dependencies
pip3 install -r requirements.txt

# Rebuild packages
rm -rf build/
./scripts/build-lambda-packages.sh
```

**Problem**: Docker build fails
```bash
# Solution: Check Docker daemon and permissions
docker info
sudo usermod -aG docker $USER
# Log out and back in
```

### Getting Help

#### Debug Mode

Enable debug logging for detailed troubleshooting:

```bash
# Enable Terraform debug logging
export TF_LOG=DEBUG

# Enable AWS CLI debug logging
export AWS_CLI_FILE_ENCODING=UTF-8
aws configure set cli_follow_redirects false

# Run setup with debug output
./scripts/setup-config.sh --debug
```

#### Log Collection

Collect logs for support:

```bash
# Create support bundle
./scripts/collect-support-info.sh

# This creates a support-bundle.tar.gz with:
# - Configuration files
# - Terraform state and plans
# - Recent CloudWatch logs
# - AWS resource information
```

#### Support Channels

1. **Check Documentation**: Review all README files in the repository
2. **Search Issues**: Look for similar problems in the issue tracker
3. **Create Support Request**: Include the support bundle and detailed error messages

## Next Steps

After successful setup, consider these next steps:

### 1. Customize for Your Environment

- **Review and adjust** resource allocations based on your needs
- **Set up monitoring dashboards** in CloudWatch
- **Configure cost alerts** to monitor spending
- **Set up backup and disaster recovery** procedures

### 2. Operational Procedures

- **Schedule regular maintenance** windows
- **Set up log rotation** and archival
- **Create runbooks** for common operational tasks
- **Train team members** on the system

### 3. Security Hardening

- **Enable CloudTrail** for audit logging
- **Set up AWS Config** for compliance monitoring
- **Implement network security** with VPC endpoints
- **Regular security reviews** and updates

### 4. Performance Optimization

- **Monitor sync performance** and adjust resources as needed
- **Optimize Lambda memory** allocation based on usage patterns
- **Consider using Reserved Instances** for cost savings
- **Implement caching strategies** where appropriate

### 5. Integration and Automation

- **Set up CI/CD pipelines** for infrastructure updates
- **Integrate with monitoring tools** like Datadog or New Relic
- **Automate certificate rotation** and secret management
- **Create automated testing** for infrastructure changes

## Configuration Reference

### Complete Configuration Example

```yaml
# Complete config.yaml example
project:
  name: "homebrew-bottles-sync"
  description: "Automated Homebrew bottles sync system"
  version: "1.0.0"
  tags:
    Environment: "production"
    Team: "platform"
    CostCenter: "engineering"

environments:
  dev:
    aws_region: "us-west-2"
    size_threshold_gb: 5
    schedule_expression: "cron(0 */6 * * ? *)"
    enable_fargate_spot: true
    auto_shutdown: true
    log_retention_days: 7
    platforms: ["arm64_sonoma", "arm64_ventura"]
    
  staging:
    aws_region: "us-east-1"
    size_threshold_gb: 15
    schedule_expression: "cron(0 3 ? * SAT *)"
    enable_fargate_spot: true
    auto_shutdown: false
    log_retention_days: 14
    platforms: ["arm64_sonoma", "arm64_ventura", "monterey"]
    
  prod:
    aws_region: "us-east-1"
    size_threshold_gb: 20
    schedule_expression: "cron(0 3 ? * SUN *)"
    enable_fargate_spot: false
    auto_shutdown: false
    log_retention_days: 30
    platforms: ["arm64_sonoma", "arm64_ventura", "monterey"]

resources:
  lambda:
    orchestrator_memory: 512
    orchestrator_timeout: 300
    sync_memory: 3008
    sync_timeout: 900
    runtime: "python3.11"
    architecture: "x86_64"
    
  ecs:
    task_cpu: 2048
    task_memory: 8192
    ephemeral_storage: 100
    enable_execute_command: true
    
  s3:
    versioning_enabled: true
    encryption_enabled: true
    lifecycle_policies_enabled: true

notifications:
  slack:
    enabled: true
    channel: "#platform-updates"
    webhook_secret_name: "homebrew-sync/slack-webhook"
    include_details: true
    mention_on_failure: true
    
  email:
    enabled: true
    addresses: ["devops@company.com"]
    topic_name: "homebrew-sync-notifications"

monitoring:
  enable_cloudwatch_dashboard: true
  enable_cost_monitoring: true
  cost_threshold_usd: 100
  enable_performance_insights: true
  
security:
  enable_vpc_endpoints: true
  enable_cloudtrail: true
  enable_config_rules: true
  secret_rotation_days: 90

cost_optimization:
  enable_lifecycle_policies: true
  transition_to_ia_days: 30
  transition_to_glacier_days: 90
  expiration_days: 365
  dev_auto_shutdown: true
```

This completes the comprehensive setup and installation guide. The system should now be fully configured and ready for operation.