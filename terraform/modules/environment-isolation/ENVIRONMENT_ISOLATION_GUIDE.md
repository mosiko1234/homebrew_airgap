# Environment Isolation Implementation Guide

This guide explains how the environment isolation system works and how to configure it for maximum security and separation between development, staging, and production environments.

## Overview

The environment isolation module provides comprehensive security controls to ensure that:
- Each environment (dev, staging, prod) operates independently
- Resources cannot be accessed across environments
- Consistent naming and tagging is enforced
- IAM permissions follow the principle of least privilege
- Multi-account deployment is supported for enhanced isolation

## Architecture

### Single Account Deployment
```
AWS Account
├── Development Environment (us-west-2)
│   ├── homebrew-bottles-sync-dev-* resources
│   ├── IAM Role: homebrew-bottles-sync-dev-github-actions-role
│   └── Isolated VPC: 10.1.0.0/16
├── Staging Environment (us-east-1)
│   ├── homebrew-bottles-sync-staging-* resources
│   ├── IAM Role: homebrew-bottles-sync-staging-github-actions-role
│   └── Isolated VPC: 10.2.0.0/16
└── Production Environment (us-east-1)
    ├── homebrew-bottles-sync-prod-* resources
    ├── IAM Role: homebrew-bottles-sync-prod-github-actions-role
    └── Isolated VPC: 10.0.0.0/16
```

### Multi-Account Deployment (Recommended for Production)
```
Development Account (123456789012)
├── Development Environment (us-west-2)
│   ├── homebrew-bottles-sync-dev-* resources
│   └── IAM Role: homebrew-bottles-sync-dev-github-actions-role

Staging Account (123456789013)
├── Staging Environment (us-east-1)
│   ├── homebrew-bottles-sync-staging-* resources
│   └── IAM Role: homebrew-bottles-sync-staging-github-actions-role

Production Account (123456789014)
├── Production Environment (us-east-1)
│   ├── homebrew-bottles-sync-prod-* resources
│   └── IAM Role: homebrew-bottles-sync-prod-github-actions-role
```

## Security Controls

### 1. Resource Naming Isolation
All resources follow the pattern: `{project_name}-{environment}-{resource_type}-{identifier}`

Examples:
- S3 Bucket: `homebrew-bottles-sync-prod-bottles-bucket`
- Lambda Function: `homebrew-bottles-sync-dev-orchestrator`
- ECS Cluster: `homebrew-bottles-sync-staging-cluster`
- IAM Role: `homebrew-bottles-sync-prod-github-actions-role`

### 2. IAM Policy Isolation
Each environment has its own IAM role with permissions scoped to:
- Environment-specific resource ARN patterns
- Current AWS account and region only
- Specific GitHub repository and branch patterns

### 3. Cross-Environment Access Prevention
The `deny_cross_environment_access` policy explicitly denies:
- Access to other environment S3 buckets
- Invocation of other environment Lambda functions
- Access to other environment ECS clusters
- Reading other environment secrets
- Publishing to other environment SNS topics

### 4. Resource Tagging Enforcement
The `resource_tagging_policy` requires:
- `Environment` tag matching the current environment
- `Project` tag matching the project name
- Prevents creation of untagged resources

### 5. GitHub Actions OIDC Integration
Each environment has a dedicated IAM role that can only be assumed by:
- Specific GitHub repository
- Specific branch patterns (develop for dev, main for staging/prod)
- Specific environment contexts in GitHub Actions

## Configuration

### Basic Configuration
```hcl
module "environment_isolation" {
  source = "../../modules/environment-isolation"
  
  project_name      = "homebrew-bottles-sync"
  environment       = "prod"
  github_repository = "your-org/homebrew-bottles-sync"
  
  enable_cross_environment_isolation = true
  enforce_resource_tagging          = true
  
  tags = {
    Environment = "prod"
    Project     = "homebrew-bottles-sync"
    ManagedBy   = "terraform"
  }
}
```

### Multi-Account Configuration
```hcl
module "environment_isolation" {
  source = "../../modules/environment-isolation"
  
  project_name      = "homebrew-bottles-sync"
  environment       = "prod"
  github_repository = "your-org/homebrew-bottles-sync"
  
  # Multi-account setup
  dev_aws_account_id     = "123456789012"
  staging_aws_account_id = "123456789013"
  prod_aws_account_id    = "123456789014"
  
  enable_cross_environment_isolation = true
  enforce_resource_tagging          = true
  enable_multi_account_isolation    = true
  
  # Restrict to specific regions
  allowed_regions = ["us-east-1"]
  
  tags = {
    Environment = "prod"
    Project     = "homebrew-bottles-sync"
    ManagedBy   = "terraform"
    Criticality = "high"
  }
}
```

## GitHub Actions Integration

### Environment-Specific Secrets
Configure these secrets in your GitHub repository:

```yaml
# Development Environment
AWS_ROLE_ARN_DEV: arn:aws:iam::123456789012:role/homebrew-bottles-sync-dev-github-actions-role

# Staging Environment  
AWS_ROLE_ARN_STAGING: arn:aws:iam::123456789013:role/homebrew-bottles-sync-staging-github-actions-role

# Production Environment
AWS_ROLE_ARN_PROD: arn:aws:iam::123456789014:role/homebrew-bottles-sync-prod-github-actions-role
```

### Workflow Configuration
```yaml
jobs:
  deploy:
    runs-on: ubuntu-latest
    environment: ${{ matrix.environment }}
    strategy:
      matrix:
        environment: [dev, staging, prod]
    
    permissions:
      id-token: write
      contents: read
    
    steps:
      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: ${{ secrets[format('AWS_ROLE_ARN_{0}', upper(matrix.environment))] }}
          role-session-name: GitHubActions-${{ matrix.environment }}
          aws-region: ${{ matrix.environment == 'dev' && 'us-west-2' || 'us-east-1' }}
```

## Deployment Process

### 1. Setup GitHub OIDC Provider
```bash
# Run this once per AWS account
./scripts/setup-github-oidc.sh -r us-east-1
```

### 2. Deploy Environment Infrastructure
```bash
# Deploy each environment
./scripts/deploy.sh deploy -e dev
./scripts/deploy.sh deploy -e staging  
./scripts/deploy.sh deploy -e prod
```

### 3. Verify Isolation
```bash
# Test that dev role cannot access staging resources
aws sts assume-role \
  --role-arn arn:aws:iam::ACCOUNT:role/homebrew-bottles-sync-dev-github-actions-role \
  --role-session-name test

# Try to access staging S3 bucket (should fail)
aws s3 ls s3://homebrew-bottles-sync-staging-bottles-bucket
```

## Monitoring and Compliance

### CloudTrail Integration
All IAM actions are logged to CloudTrail for audit purposes:
- Role assumptions
- Policy evaluations
- Resource access attempts
- Cross-environment access denials

### Cost Allocation
Environment-specific tags enable:
- Cost allocation by environment
- Resource usage tracking
- Budget alerts per environment

### Compliance Reporting
The module outputs provide compliance information:
```hcl
output "environment_isolation_summary" {
  value = {
    environment                     = "prod"
    isolation_level                = "strict"
    cross_environment_isolation    = true
    resource_tagging_enforcement   = true
    multi_account_setup           = true
    total_policies_attached       = 4
  }
}
```

## Troubleshooting

### Common Issues

#### 1. OIDC Trust Relationship Errors
**Error**: `AssumeRoleWithWebIdentity is not authorized`

**Solution**: 
- Verify GitHub repository name matches exactly
- Check branch patterns in trust policy
- Ensure OIDC provider exists in target account

#### 2. Cross-Environment Access Denied
**Error**: `Access Denied` when accessing resources

**Solution**:
- Verify resource names follow naming convention
- Check environment tags are correctly applied
- Review IAM policy resource patterns

#### 3. Resource Creation Blocked
**Error**: `Request failed due to missing required tags`

**Solution**:
- Ensure `Environment` and `Project` tags are included
- Verify tag values match expected environment
- Check resource tagging policy is not too restrictive

### Debugging Commands

```bash
# Check IAM role trust policy
aws iam get-role --role-name homebrew-bottles-sync-prod-github-actions-role

# List attached policies
aws iam list-attached-role-policies --role-name homebrew-bottles-sync-prod-github-actions-role

# Test policy simulation
aws iam simulate-principal-policy \
  --policy-source-arn arn:aws:iam::ACCOUNT:role/homebrew-bottles-sync-prod-github-actions-role \
  --action-names s3:GetObject \
  --resource-arns arn:aws:s3:::homebrew-bottles-sync-dev-bottles-bucket/test.txt
```

## Best Practices

### 1. Multi-Account Strategy
- Use separate AWS accounts for production workloads
- Implement cross-account roles for shared services
- Use AWS Organizations for centralized management

### 2. Least Privilege Access
- Regularly review and audit IAM policies
- Use AWS Access Analyzer to identify unused permissions
- Implement time-limited access for sensitive operations

### 3. Monitoring and Alerting
- Set up CloudWatch alarms for unusual access patterns
- Monitor cross-environment access attempts
- Implement automated compliance checking

### 4. Regular Security Reviews
- Quarterly review of IAM policies and roles
- Annual penetration testing of isolation controls
- Regular updates to security policies and procedures

## Advanced Configuration

### Custom Resource Patterns
```hcl
# Override default resource patterns
locals {
  custom_resource_patterns = {
    s3_buckets = "arn:aws:s3:::${var.project_name}-${var.environment}-*"
    lambda_functions = "arn:aws:lambda:*:*:function:${var.project_name}-${var.environment}-*"
  }
}
```

### Environment-Specific Policies
```hcl
# Additional policies for production environment
resource "aws_iam_policy" "prod_additional_security" {
  count = var.environment == "prod" ? 1 : 0
  
  name = "${local.resource_prefix}-additional-security"
  
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Deny"
        Action = ["iam:*"]
        Resource = "*"
        Condition = {
          StringNotEquals = {
            "aws:RequestedRegion" = "us-east-1"
          }
        }
      }
    ]
  })
}
```

This comprehensive environment isolation system ensures that your Homebrew Bottles Sync System operates securely across all environments while maintaining the flexibility needed for development and testing.