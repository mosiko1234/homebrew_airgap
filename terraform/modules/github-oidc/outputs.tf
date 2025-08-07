# Outputs for GitHub OIDC module

output "oidc_provider_arn" {
  description = "ARN of the GitHub OIDC provider"
  value       = var.create_oidc_provider ? aws_iam_openid_connect_provider.github[0].arn : var.existing_oidc_provider_arn
}

output "github_actions_roles" {
  description = "Map of environment names to GitHub Actions IAM role ARNs"
  value = {
    for env_name, role in aws_iam_role.github_actions : env_name => role.arn
  }
}

output "github_actions_role_names" {
  description = "Map of environment names to GitHub Actions IAM role names"
  value = {
    for env_name, role in aws_iam_role.github_actions : env_name => role.name
  }
}

output "deployment_policy_arns" {
  description = "Map of environment names to deployment policy ARNs"
  value = {
    for env_name, policy in aws_iam_policy.github_actions_deployment : env_name => policy.arn
  }
}

output "isolation_policy_arns" {
  description = "Map of environment names to isolation policy ARNs"
  value = {
    for env_name, policy in aws_iam_policy.environment_isolation : env_name => policy.arn
  }
}

output "permission_boundary_arn" {
  description = "ARN of the permission boundary policy"
  value       = aws_iam_policy.permission_boundary.arn
}

output "github_secrets_configuration" {
  description = "GitHub Secrets that need to be configured"
  value = {
    for env_name, role in aws_iam_role.github_actions : "AWS_ROLE_ARN_${upper(env_name)}" => role.arn
  }
  sensitive = false
}

output "setup_instructions" {
  description = "Instructions for completing the GitHub OIDC setup"
  value = {
    github_secrets = {
      for env_name, role in aws_iam_role.github_actions : "AWS_ROLE_ARN_${upper(env_name)}" => {
        value       = role.arn
        description = "IAM role ARN for ${env_name} environment deployments"
      }
    }
    workflow_configuration = {
      permissions = {
        id-token = "write"
        contents = "read"
      }
      configure_aws_credentials = {
        role-to-assume    = "${{ secrets.AWS_ROLE_ARN_${upper("ENV_NAME")} }}"
        role-session-name = "GitHubActions-${{ github.run_id }}"
        aws-region        = "${{ matrix.aws_region }}"
      }
    }
  }
}