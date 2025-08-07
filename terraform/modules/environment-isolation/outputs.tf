# Outputs for Environment Isolation Module

output "github_actions_role_arn" {
  description = "ARN of the GitHub Actions IAM role"
  value       = aws_iam_role.github_actions_role.arn
}

output "github_actions_role_name" {
  description = "Name of the GitHub Actions IAM role"
  value       = aws_iam_role.github_actions_role.name
}

output "github_actions_policy_arn" {
  description = "ARN of the GitHub Actions IAM policy"
  value       = aws_iam_policy.github_actions_policy.arn
}

output "cross_environment_isolation_policy_arn" {
  description = "ARN of the cross-environment isolation policy"
  value       = var.enable_cross_environment_isolation ? aws_iam_policy.deny_cross_environment_access[0].arn : null
}

output "resource_tagging_policy_arn" {
  description = "ARN of the resource tagging enforcement policy"
  value       = var.enforce_resource_tagging ? aws_iam_policy.resource_tagging_policy[0].arn : null
}

output "environment_security_policy_arn" {
  description = "ARN of the environment security policy"
  value       = aws_iam_policy.environment_security_policy.arn
}

output "environment_isolation_config" {
  description = "Environment isolation configuration summary"
  value = {
    environment                        = var.environment
    project_name                      = var.project_name
    resource_prefix                   = local.resource_prefix
    target_account_id                 = local.target_account_id
    region                           = data.aws_region.current.name
    cross_environment_isolation      = var.enable_cross_environment_isolation
    resource_tagging_enforcement     = var.enforce_resource_tagging
    multi_account_setup             = var.enable_multi_account_isolation
    github_repository               = var.github_repository
    isolation_level                 = var.enable_cross_environment_isolation ? "strict" : "standard"
  }
}

output "environment_tags" {
  description = "Standard tags applied to all resources in this environment"
  value       = local.environment_tags
}

output "resource_naming_convention" {
  description = "Resource naming convention for this environment"
  value = {
    prefix    = local.resource_prefix
    pattern   = "${local.resource_prefix}-<resource-type>-<identifier>"
    examples = {
      s3_bucket      = "${local.resource_prefix}-bottles-bucket"
      lambda_function = "${local.resource_prefix}-orchestrator"
      ecs_cluster    = "${local.resource_prefix}-cluster"
      iam_role       = "${local.resource_prefix}-<service>-role"
    }
  }
}

output "account_isolation_summary" {
  description = "Summary of account isolation configuration"
  value = {
    current_account_id = data.aws_caller_identity.current.account_id
    target_account_id  = local.target_account_id
    environment_accounts = local.environment_accounts
    is_multi_account   = local.target_account_id != data.aws_caller_identity.current.account_id
  }
}

output "security_policies_summary" {
  description = "Summary of security policies applied"
  value = {
    github_actions_policy_attached           = true
    cross_environment_isolation_enabled      = var.enable_cross_environment_isolation
    resource_tagging_enforcement_enabled     = var.enforce_resource_tagging
    environment_security_policy_attached     = true
    total_policies_attached                  = 2 + (var.enable_cross_environment_isolation ? 1 : 0) + (var.enforce_resource_tagging ? 1 : 0)
  }
}