# Environment Isolation Module

This Terraform module provides environment isolation capabilities for the Homebrew Bottles Sync System. It creates IAM policies and roles that enforce strict boundaries between development, staging, and production environments.

## Features

- **GitHub Actions OIDC Integration**: Secure authentication for CI/CD pipelines
- **Resource-level Isolation**: Prevents cross-environment access to resources
- **Consistent Tagging**: Enforces environment-specific resource tagging
- **Least Privilege Access**: Minimal permissions required for each environment
- **Cross-Account Support**: Optional support for multi-account deployments

## Usage

```hcl
module "environment_isolation" {
  source = "./modules/environment-isolation"
  
  project_name      = "homebrew-bottles-sync"
  environment       = "dev"
  github_repository = "your-org/homebrew-bottles-sync"
  
  enable_cross_environment_isolation = true
  enforce_resource_tagging          = true
  
  tags = {
    Environment = "dev"
    Project     = "homebrew-bottles-sync"
    ManagedBy   = "terraform"
  }
}
```

## IAM Policies Created

### GitHub Actions Policy
Grants permissions for GitHub Actions to:
- Access environment-specific S3 buckets
- Invoke environment-specific Lambda functions
- Manage environment-specific ECS tasks
- Write to environment-specific CloudWatch logs
- Access environment-specific secrets
- Publish to environment-specific SNS topics

### Cross-Environment Isolation Policy
Prevents access to:
- Other environment S3 buckets
- Other environment Lambda functions
- Other environment ECS clusters
- Other environment secrets

### Resource Tagging Policy
Enforces:
- All resources must have an `Environment` tag
- The `Environment` tag must match the current environment
- Prevents creation of untagged resources

## GitHub Actions OIDC Setup

The module creates an IAM role that can be assumed by GitHub Actions using OIDC. The trust relationship is configured to only allow:

- Specific GitHub repository
- Specific branch patterns (develop for dev, main for staging/prod)
- Specific environment contexts

### Example GitHub Actions Usage

```yaml
jobs:
  deploy:
    runs-on: ubuntu-latest
    environment: dev
    permissions:
      id-token: write
      contents: read
    
    steps:
      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: ${{ secrets.AWS_ROLE_ARN }}
          role-session-name: GitHubActions
          aws-region: us-west-2
```

## Security Considerations

### Environment Separation
- Each environment has its own IAM role and policies
- Resources are isolated by naming conventions and ARN patterns
- Cross-environment access is explicitly denied

### Least Privilege
- Permissions are scoped to specific resource patterns
- Only necessary actions are allowed
- Time-limited session tokens through OIDC

### Audit and Compliance
- All actions are logged through CloudTrail
- Resource tagging enables cost allocation and governance
- IAM policies are version controlled

## Variables

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|----------|
| project_name | Name of the project | string | n/a | yes |
| environment | Environment name (dev, staging, prod) | string | n/a | yes |
| github_repository | GitHub repository for OIDC (org/repo) | string | n/a | yes |
| enable_cross_environment_isolation | Enable cross-environment access prevention | bool | true | no |
| enforce_resource_tagging | Enforce consistent resource tagging | bool | true | no |
| allowed_aws_accounts | List of allowed AWS account IDs | list(string) | [] | no |
| tags | Tags to apply to all resources | map(string) | {} | no |

## Outputs

| Name | Description |
|------|-------------|
| github_actions_role_arn | ARN of the GitHub Actions IAM role |
| github_actions_role_name | Name of the GitHub Actions IAM role |
| github_actions_policy_arn | ARN of the GitHub Actions IAM policy |
| cross_environment_isolation_policy_arn | ARN of the cross-environment isolation policy |
| resource_tagging_policy_arn | ARN of the resource tagging enforcement policy |
| environment_isolation_config | Environment isolation configuration summary |

## Multi-Account Deployment

For enhanced security, consider deploying each environment to a separate AWS account:

- **Development Account**: For development and testing
- **Staging Account**: For pre-production validation
- **Production Account**: For production workloads

This provides the strongest isolation but requires additional setup for cross-account access where needed.

## Troubleshooting

### Common Issues

#### OIDC Trust Relationship Errors
- Verify the GitHub repository name is correct
- Check that the branch patterns match your workflow
- Ensure the OIDC provider is configured in AWS

#### Permission Denied Errors
- Check that resource names follow the expected patterns
- Verify environment tags are correctly applied
- Review CloudTrail logs for detailed error information

#### Cross-Environment Access Issues
- Confirm the isolation policies are not too restrictive
- Check if legitimate cross-environment access is needed
- Consider using cross-account roles for shared resources