# Deployment Orchestration System

This directory contains the deployment orchestration system for the Homebrew Bottles Sync System. It provides automated deployment, rollback, and monitoring capabilities across all environments.

## Overview

The deployment orchestration system consists of several components:

- **Environment-specific deployments**: Separate configurations for dev, staging, and prod
- **Deployment tracking**: Complete history and status tracking
- **Rollback mechanisms**: Safe rollback to previous successful deployments
- **Status monitoring**: Real-time deployment status and health checks
- **Notification system**: Slack and email notifications for deployment events

## Scripts

### Main Scripts

- **`deploy.sh`** - Main deployment wrapper script
- **`deploy-environment.sh`** - Environment-specific deployment orchestration
- **`rollback-deployment.sh`** - Rollback mechanism
- **`deployment-status.sh`** - Status dashboard
- **`deployment_tracker.py`** - Deployment tracking system

### Supporting Scripts

- **`config_processor.py`** - Configuration validation and processing
- **`notify_deployment.py`** - Notification system

## Quick Start

### Deploy to Development
```bash
./scripts/deploy.sh deploy -e dev
```

### Plan Staging Deployment
```bash
./scripts/deploy.sh plan -e staging
```

### Deploy to Production (with approval)
```bash
./scripts/deploy.sh deploy -e prod
```

### Check Status
```bash
./scripts/deploy.sh status
```

### Rollback Development
```bash
./scripts/deploy.sh rollback -e dev -c abc123
```

## Detailed Usage

### Deployment Commands

#### Deploy to Environment
```bash
# Basic deployment
./scripts/deploy.sh deploy -e ENVIRONMENT

# With auto-approve (skip confirmation)
./scripts/deploy.sh deploy -e ENVIRONMENT -y

# Dry run (show what would be deployed)
./scripts/deploy.sh deploy -e ENVIRONMENT -d
```

#### Plan Deployment
```bash
# Show deployment plan
./scripts/deploy.sh plan -e ENVIRONMENT

# Save plan to file
./scripts/deploy-environment.sh -e ENVIRONMENT -a plan
```

#### Destroy Environment
```bash
# Destroy environment (with confirmation)
./scripts/deploy.sh destroy -e ENVIRONMENT

# Auto-approve destruction
./scripts/deploy.sh destroy -e ENVIRONMENT -y
```

### Rollback Commands

#### List Rollback Candidates
```bash
./scripts/deploy.sh rollback -e ENVIRONMENT -l
```

#### Perform Rollback
```bash
# Rollback to specific commit
./scripts/deploy.sh rollback -e ENVIRONMENT -c COMMIT_SHA

# Rollback with auto-approve
./scripts/deploy.sh rollback -e ENVIRONMENT -c COMMIT_SHA -y

# Dry run rollback
./scripts/deploy.sh rollback -e ENVIRONMENT -c COMMIT_SHA -d
```

### Status and Monitoring

#### Check Overall Status
```bash
# All environments
./scripts/deploy.sh status

# Specific environment
./scripts/deploy.sh status -e ENVIRONMENT
```

#### View Deployment History
```bash
# Recent deployments for all environments
./scripts/deploy.sh history

# Specific environment history
./scripts/deploy.sh history -e ENVIRONMENT

# Limit number of entries
./scripts/deploy.sh history -e ENVIRONMENT -l 10
```

## Environment Configuration

Each environment has its own configuration optimized for its purpose:

### Development Environment
- **Purpose**: Development and testing
- **Features**: Auto-shutdown, cost optimization, frequent syncs
- **Resources**: Smaller allocations for cost savings
- **Region**: us-west-2

### Staging Environment
- **Purpose**: Pre-production testing
- **Features**: Production-like settings, enhanced monitoring
- **Resources**: Balanced performance and cost
- **Region**: us-east-1

### Production Environment
- **Purpose**: Production workload
- **Features**: Maximum reliability, comprehensive monitoring, backups
- **Resources**: Optimized for performance
- **Region**: us-east-1

## Deployment Flow

1. **Validation**: Configuration and prerequisites are validated
2. **Planning**: Terraform plan is generated and reviewed
3. **Deployment**: Infrastructure is deployed with Terraform
4. **Tracking**: Deployment record is created and stored
5. **Notification**: Team is notified of deployment status
6. **Monitoring**: Ongoing health checks and alerting

## Rollback Process

1. **Candidate Selection**: List available rollback targets
2. **Validation**: Ensure rollback target is valid
3. **Confirmation**: Require approval for production rollbacks
4. **Execution**: Checkout target commit and redeploy
5. **Verification**: Confirm rollback success
6. **Notification**: Notify team of rollback completion

## Deployment Records

All deployments are tracked with the following information:
- Environment and action performed
- Timestamp and duration
- Git commit SHA and user
- Terraform version used
- Success/failure status
- Error messages (if applicable)

Records are stored in:
- Local files: `.deployment-records/`
- AWS SSM Parameter Store (if configured)

## Prerequisites

### Required Tools
- Terraform >= 1.0
- AWS CLI configured with appropriate credentials
- jq for JSON processing
- Git for version control

### AWS Permissions
Each environment requires appropriate AWS IAM permissions:
- Terraform state management (S3, DynamoDB)
- Resource creation and management
- SSM Parameter Store access (optional)

### Configuration Files
- `config.yaml` - Central configuration
- `terraform/environments/*/terraform.tfvars` - Environment-specific variables
- `terraform/environments/*/backend.hcl` - Backend configuration (optional)

## Security Considerations

### Production Deployments
- Require manual approval by default
- Use separate AWS accounts/regions
- Enable comprehensive logging and monitoring
- Implement least-privilege access

### Secrets Management
- Use AWS Secrets Manager for sensitive data
- Never commit secrets to version control
- Rotate secrets regularly

### Access Control
- Limit deployment access to authorized users
- Use IAM roles with temporary credentials
- Log all deployment activities

## Troubleshooting

### Common Issues

#### Configuration Validation Fails
```bash
# Check configuration syntax
python3 scripts/config_processor.py --validate

# Generate new tfvars files
python3 scripts/config_processor.py --generate
```

#### Terraform Initialization Fails
```bash
# Check backend configuration
cat terraform/environments/ENVIRONMENT/backend.hcl

# Reinitialize Terraform
cd terraform/environments/ENVIRONMENT
terraform init -reconfigure
```

#### Deployment Fails
```bash
# Check deployment logs
./scripts/deploy.sh status -e ENVIRONMENT

# View recent deployment history
./scripts/deploy.sh history -e ENVIRONMENT

# Check Terraform state
cd terraform/environments/ENVIRONMENT
terraform show
```

#### Rollback Issues
```bash
# List available rollback candidates
./scripts/deploy.sh rollback -e ENVIRONMENT -l

# Validate specific commit
git rev-parse --verify COMMIT_SHA

# Check deployment history
python3 scripts/deployment_tracker.py history --environment ENVIRONMENT
```

## Monitoring and Alerting

### Built-in Monitoring
- Deployment success/failure tracking
- Resource health checks
- Cost monitoring and alerts
- Performance metrics

### Notifications
- Slack notifications for deployment events
- Email alerts for critical failures
- Status updates in deployment dashboard

### Dashboards
- CloudWatch dashboards per environment
- Deployment status dashboard
- Cost and performance metrics

## Best Practices

### Development Workflow
1. Test changes in development environment first
2. Use staging for integration testing
3. Deploy to production only after staging validation
4. Always review deployment plans before applying

### Rollback Strategy
1. Keep rollback candidates available
2. Test rollback procedures regularly
3. Document rollback decisions
4. Monitor system after rollback

### Maintenance
1. Update Terraform modules regularly
2. Review and rotate secrets quarterly
3. Clean up old deployment records
4. Test disaster recovery procedures

## Support

For issues or questions:
1. Check this documentation
2. Review deployment logs and status
3. Check troubleshooting section
4. Contact the platform team